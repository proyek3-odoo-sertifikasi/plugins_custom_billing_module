from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


PAYMENT_SETTLEMENT_STATES = [
    ('no_invoice', 'No Invoice'),
    ('not_paid', 'Not Paid'),
    ('in_payment', 'In Payment'),
    ('partial', 'Partially Paid'),
    ('paid', 'Paid'),
    ('reversed', 'Reversed'),
    ('blocked', 'Blocked'),
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    lsp_student_id = fields.Many2one(
        'lsp.student',
        string='Asesi (Student)',
        ondelete='set null',
        copy=False,
    )

    def _is_student_verified(self):
        self.ensure_one()
        if not self.lsp_student_id:
            return True
        return self.lsp_student_id.verification_state == 'verified'

    def _get_assessment_receivable_account(self):
        """Return a dedicated receivable account for assessment invoices, creating it if needed."""
        account = self.env['account.account'].sudo().search([
            ('code_store', '=', 'MYCUST_ASSESSMENT_REC'),
        ], limit=1)
        if account:
            return account

        return self.env['account.account'].sudo().create({
            'name': 'Assessment Receivable',
            'account_type': 'asset_receivable',
            'code_store': 'MYCUST_ASSESSMENT_REC',
        })

    def _ensure_partner_receivable_account(self):
        """Assign the assessment receivable account to the order partner when missing."""
        receivable_account = self._get_assessment_receivable_account()
        for order in self:
            if order.partner_id and not order.partner_id.property_account_receivable_id:
                _logger.info(
                    '[ASSESSMENT_RECEIVABLE] Setting receivable account for partner %s',
                    order.partner_id.display_name,
                )
                order.partner_id.write({
                    'property_account_receivable_id': receivable_account.id,
                })

    payment_settlement_state = fields.Selection(
        selection=PAYMENT_SETTLEMENT_STATES,
        string='Payment Settlement Status',
        compute='_compute_payment_settlement_state',
        store=False,
    )

    def _get_assessment_product(self):
        """Return the shared assessment product variant."""
        product_template = self.env.ref(
            'my_custom_modul.product_assessment_service',
            raise_if_not_found=False,
        )
        if not product_template:
            product_template = self.env['product.template'].search([
                ('default_code', '=', 'MYCUST_ASSESSMENT'),
            ], limit=1)
        return product_template.product_variant_id if product_template else self.env['product.product']

    def _has_assessment_line(self):
        self.ensure_one()
        return any(
            line.product_id and line.product_id.default_code == 'MYCUST_ASSESSMENT'
            for line in self.order_line
            if not line.display_type
        )

    def _ensure_assessment_line(self):
        """Add the assessment product automatically when an order has no lines yet."""
        for order in self:
            if not order.partner_id:
                continue
            if order.state not in ('draft', 'sent'):
                continue
            if order._has_assessment_line():
                continue
            if order.order_line.filtered(lambda line: not line.display_type):
                continue

            product = order._get_assessment_product()
            if not product:
                _logger.warning('[ASSESSMENT_PRODUCT] Missing assessment product for SO %s', order.name)
                continue

            _logger.info(
                '[ASSESSMENT_PRODUCT] Auto-adding assessment product %s to SO %s',
                product.display_name,
                order.name,
            )
            self.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'product_uom_id': product.uom_id.id,
                'name': product.display_name,
            })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            student_id = vals.get('lsp_student_id')
            if student_id and not vals.get('partner_id'):
                student = self.env['lsp.student'].sudo().browse(student_id)
                if student.user_id and student.user_id.partner_id:
                    vals['partner_id'] = student.user_id.partner_id.id
        orders = super().create(vals_list)
        orders._ensure_partner_receivable_account()
        orders._ensure_assessment_line()
        for order in orders:
            if order._has_assessment_line() and order.state in ('draft', 'sent') and order._is_student_verified():
                _logger.info('[AUTO_CONFIRM] Confirming assessment SO %s', order.name)
                order.action_confirm()
            if order.lsp_student_id and order.lsp_student_id.sale_order_id != order:
                order.lsp_student_id.sudo().write({'sale_order_id': order.id})
        return orders

    def write(self, vals):
        result = super().write(vals)
        if {'partner_id', 'company_id'} & set(vals):
            self._ensure_assessment_line()
        if 'lsp_student_id' in vals:
            for order in self.filtered('lsp_student_id'):
                if order.lsp_student_id.sale_order_id != order:
                    order.lsp_student_id.sudo().write({'sale_order_id': order.id})
        return result

    @api.depends('invoice_ids.payment_state', 'invoice_ids.move_type')
    def _compute_payment_settlement_state(self):
        """Compute payment settlement status from invoices."""
        for order in self:
            invoices = order.invoice_ids.filtered(
                lambda move: move.move_type in ('out_invoice', 'out_refund')
            )
            if not invoices:
                order.payment_settlement_state = 'no_invoice'
                continue

            states = set(invoices.mapped('payment_state'))
            # Check priority: blocked ? not_paid ? partial ? in_payment ? paid ? reversed
            if 'blocked' in states:
                order.payment_settlement_state = 'blocked'
            elif states == {'paid'}:
                order.payment_settlement_state = 'paid'
            elif 'in_payment' in states:
                order.payment_settlement_state = 'in_payment'
            elif 'partial' in states:
                order.payment_settlement_state = 'partial'
            elif states == {'reversed'}:
                order.payment_settlement_state = 'reversed'
            else:
                order.payment_settlement_state = 'not_paid'

    def action_confirm(self):
        """Confirm the order and auto-create the regular invoice."""
        for order in self:
            if not order._is_student_verified():
                raise ValidationError('Asesi belum terverifikasi. Konfirmasi SO dan invoice tidak diizinkan.')
        self._ensure_partner_receivable_account()
        self._ensure_assessment_line()
        result = super().action_confirm()
        for order in self.filtered(lambda so: so.state == 'sale'):
            if order.invoice_ids.filtered(lambda move: move.move_type in ('out_invoice', 'out_refund')):
                continue
            lines = order.order_line.filtered(lambda line: not line.display_type and line.product_id)
            if not lines:
                _logger.warning('[AUTO_INVOICE] No invoiceable lines for SO %s', order.name)
                continue
            _logger.info('[AUTO_INVOICE] Creating invoice for SO %s', order.name)
            order._create_invoices()
        return result
