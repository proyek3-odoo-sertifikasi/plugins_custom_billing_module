from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_assessee_tarif(self):
        """Calculate tariff based on partner type and product tariffs."""
        self.ensure_one()
        partner = self.order_id.partner_id if self.order_id else None
        partner_type = partner.tipe_asesi if partner else 'external'
        product_tmpl = self.product_id.product_tmpl_id if self.product_id else None

        if not product_tmpl:
            return 0.0

        if partner_type == 'internal':
            tarif_value = product_tmpl.tarif_internal or 0.0
        else:
            tarif_value = product_tmpl.tarif_eksternal or 0.0

        _logger.info(
            "[ASSESSEE_TARIF] Product: %s, Partner: %s, Type: %s, Tarif: %.2f",
            product_tmpl.name,
            partner.name if partner else 'N/A',
            partner_type,
            tarif_value,
        )
        return tarif_value

    def _sync_assessee_price(self):
        """Sync SO line price_unit to calculated assessee tariff."""
        for line in self:
            if line.product_id and line.order_id and not line.display_type:
                tarif = line._get_assessee_tarif()
                _logger.info(
                    "[SYNC_PRICE] SO Line %s: old=%.2f, new=%.2f",
                    line.id,
                    line.price_unit,
                    tarif,
                )
                # Update price without triggering recursion
                super(type(line), line.with_context(skip_assessee_sync=True)).write({
                    'price_unit': tarif,
                })

    @api.onchange('product_id', 'order_id.partner_id', 'order_id.partner_id.tipe_asesi')
    def _onchange_assessee_price(self):
        """Recalculate price when product or partner changes."""
        if self.product_id and self.order_id and not self.display_type:
            self.price_unit = self._get_assessee_tarif()

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("[CREATE_SOL] Creating %d SO lines", len(vals_list))
        lines = super().create(vals_list)
        lines._sync_assessee_price()
        return lines

    def write(self, vals):
        if self.env.context.get('skip_assessee_sync'):
            return super().write(vals)

        result = super().write(vals)
        if {'product_id', 'order_id'} & set(vals):
            self._sync_assessee_price()
        return result

    def _prepare_invoice_line(self, **optional_values):
        """Use assessee tariff when creating invoice lines."""
        vals = super()._prepare_invoice_line(**optional_values)
        if self.product_id and self.order_id and not self.display_type:
            assessee_tarif = self._get_assessee_tarif()
            income_account = (
                self.product_id.product_tmpl_id.property_account_income_id
                or self.product_id.categ_id.property_account_income_categ_id
            )
            _logger.info(
                "[PREPARE_INVOICE] Original: %.2f, New: %.2f",
                vals.get('price_unit', 0),
                assessee_tarif,
            )
            vals['price_unit'] = assessee_tarif
            if income_account:
                vals['account_id'] = income_account.id
        return vals
