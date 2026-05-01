from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_assessment_income_account(self):
        """Return a dedicated income account for assessment invoices, creating it if needed."""
        account = self.env['account.account'].sudo().search([
            ('code_store', '=', 'MYCUST_ASSESSMENT_REV'),
        ], limit=1)
        if account:
            return account

        return self.env['account.account'].sudo().create({
            'name': 'Assessment Revenue',
            'account_type': 'income',
            'code_store': 'MYCUST_ASSESSMENT_REV',
        })

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

    def _get_assessee_price(self):
        """Get assessee tariff for invoice line based on partner type."""
        self.ensure_one()
        move = self.move_id
        partner = move.partner_id if move else None
        product = self.product_id

        if not product or not move or move.move_type not in ('out_invoice', 'out_refund'):
            return self.price_unit

        partner_type = partner.tipe_asesi if partner else 'external'
        product_tmpl = product.product_tmpl_id

        if partner_type == 'internal':
            tarif = product_tmpl.tarif_internal or self.price_unit
        else:
            tarif = product_tmpl.tarif_eksternal or self.price_unit

        _logger.info(
            "[INVOICE_PRICE] Invoice %s, Line %s: Partner=%s, Type=%s, Tarif=%.2f",
            move.name,
            self.id,
            partner.name if partner else 'N/A',
            partner_type,
            tarif,
        )
        return tarif

    def _apply_assessee_price(self):
        """Apply assessee tariff to invoice line."""
        for line in self:
            if line.product_id and line.move_id and not line.display_type:
                new_price = line._get_assessee_price()
                if new_price != line.price_unit:
                    _logger.info(
                        "[APPLY_PRICE] Line %s: old=%.2f, new=%.2f",
                        line.id,
                        line.price_unit,
                        new_price,
                    )
                    super(type(line), line.with_context(skip_assessee_price=True)).write({
                        'price_unit': new_price,
                    })

    @api.onchange('product_id', 'move_id.partner_id', 'move_id.partner_id.tipe_asesi')
    def _onchange_assessee_price(self):
        """Update price when product or partner changes."""
        if self.product_id and self.move_id and not self.display_type:
            self.price_unit = self._get_assessee_price()

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("[CREATE_MOVE_LINE] Creating %d invoice lines", len(vals_list))
        income_account = self._get_assessment_income_account()
        receivable_account = self._get_assessment_receivable_account()
        for vals in vals_list:
            if vals.get('display_type') in ('line_section', 'line_note'):
                continue
            if not vals.get('account_id'):
                if vals.get('product_id'):
                    vals['account_id'] = income_account.id
                else:
                    vals['account_id'] = receivable_account.id
            if vals.get('product_id') and not vals.get('account_id'):
                vals['account_id'] = income_account.id
        lines = super().create(vals_list)
        lines._apply_assessee_price()
        return lines

    def write(self, vals):
        if self.env.context.get('skip_assessee_price'):
            return super().write(vals)

        result = super().write(vals)
        if {'product_id', 'move_id'} & set(vals):
            self._apply_assessee_price()
        return result
