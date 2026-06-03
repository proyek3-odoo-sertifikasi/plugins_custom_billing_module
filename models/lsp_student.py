from odoo import api, fields, models
import logging


_logger = logging.getLogger(__name__)


PAYMENT_STATES = [
    ('no_invoice', 'Belum Ada Invoice'),
    ('not_paid', 'Belum Bayar'),
    ('paid', 'Lunas'),
]


VERIFICATION_STATES = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('verified', 'Verified'),
    ('rejected', 'Rejected'),
]


class LSPStudent(models.Model):
    _inherit = 'lsp.student'

    verification_state = fields.Selection(
        selection=VERIFICATION_STATES,
        string='Status Verifikasi',
        default='submitted',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        related='user_id.partner_id',
        readonly=True,
    )
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', readonly=True, copy=False)
    payment_state = fields.Selection(
        selection=PAYMENT_STATES,
        string='Status Pembayaran',
        compute='_compute_payment_state',
        store=False,
    )

    @api.depends('sale_order_id', 'sale_order_id.payment_settlement_state')
    def _compute_payment_state(self):
        for student in self:
            if not student.sale_order_id:
                student.payment_state = 'no_invoice'
                continue
            state = student.sale_order_id.payment_settlement_state
            if state == 'paid':
                student.payment_state = 'paid'
            elif state == 'no_invoice':
                student.payment_state = 'no_invoice'
            else:
                student.payment_state = 'not_paid'

    def action_create_sale_order(self):
        for student in self:
            if student.sale_order_id:
                continue
            if student.verification_state != 'verified':
                _logger.info('[LSP_STUDENT] Skip SO create for %s due to state %s', student.id, student.verification_state)
                continue

            student._sync_partner_tipe_asesi()
            partner = student.user_id.partner_id if student.user_id else False
            if not partner:
                _logger.warning('[LSP_STUDENT] Missing partner for student %s', student.id)
                continue

            order = self.env['sale.order'].sudo().create({
                'partner_id': partner.id,
                'lsp_student_id': student.id,
            })
            student.sudo().write({'sale_order_id': order.id})

    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Order',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
        }

    def action_view_invoices(self):
        self.ensure_one()
        if not self.sale_order_id:
            return False
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action['domain'] = [('id', 'in', self.sale_order_id.invoice_ids.ids)]
        return action

    def _sync_partner_tipe_asesi(self):
        for student in self:
            partner = student.user_id.partner_id if student.user_id else False
            if partner:
                new_tipe = 'internal' if student.school == 'smk_negeri_1_rembang' else 'external'
                if partner.tipe_asesi != new_tipe:
                    partner.sudo().write({'tipe_asesi': new_tipe})

    @api.model_create_multi
    def create(self, vals_list):
        students = super().create(vals_list)
        students._sync_partner_tipe_asesi()
        return students

    def write(self, vals):
        result = super().write(vals)
        if 'school' in vals or 'user_id' in vals:
            self._sync_partner_tipe_asesi()
        if vals.get('verification_state') == 'verified':
            self.filtered(lambda student: not student.sale_order_id).action_create_sale_order()
        return result
