from odoo import api, fields, models


ASSESSMENT_PRODUCT_XMLID = 'my_custom_modul.product_assessment_service'
ASSESSMENT_INCOME_ACCOUNT_XMLID = 'my_custom_modul.account_assessment_income'
ASSESSMENT_PRODUCT_VALUES = {
    'name': 'Produk Asesmen',
    'default_code': 'MYCUST_ASSESSMENT',
    'type': 'service',
    'invoice_policy': 'order',
    'sale_ok': True,
    'purchase_ok': False,
    'list_price': 0.0,
    'tarif_internal': 100000.0,
    'tarif_eksternal': 200000.0,
}


ASSESSMENT_INCOME_ACCOUNT_VALUES = {
    'name': 'Assessment Revenue',
    'account_type': 'income',
    'code_store': 'MYCUST_ASSESSMENT_REV',
}


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    tarif_internal = fields.Float(string='Tarif Internal')
    tarif_eksternal = fields.Float(string='Tarif Eksternal')

    @api.model
    def sync_assessment_product(self):
        """Restore the assessment product to its expected standard values."""
        income_account = self._get_or_create_assessment_income_account()
        product_values = dict(ASSESSMENT_PRODUCT_VALUES)
        product_values['property_account_income_id'] = income_account.id

        product = self.env.ref(ASSESSMENT_PRODUCT_XMLID, raise_if_not_found=False)

        if product and product.exists():
            product.write(product_values)
            return product

        product = self.search([('default_code', '=', ASSESSMENT_PRODUCT_VALUES['default_code'])], limit=1)
        if product:
            product.write(product_values)
            xmlid = self.env['ir.model.data'].sudo().search([
                ('module', '=', 'my_custom_modul'),
                ('name', '=', 'product_assessment_service'),
            ], limit=1)
            if xmlid:
                xmlid.res_id = product.id
            else:
                self.env['ir.model.data'].sudo().create({
                    'module': 'my_custom_modul',
                    'name': 'product_assessment_service',
                    'model': 'product.template',
                    'res_id': product.id,
                    'noupdate': False,
                })
            return product

            product = self.create(product_values)
        xmlid = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'my_custom_modul'),
            ('name', '=', 'product_assessment_service'),
        ], limit=1)
        if xmlid:
            xmlid.res_id = product.id
        else:
            self.env['ir.model.data'].sudo().create({
                'module': 'my_custom_modul',
                'name': 'product_assessment_service',
                'model': 'product.template',
                'res_id': product.id,
                'noupdate': False,
            })
        return product

    @api.model
    def _get_or_create_assessment_income_account(self):
        """Create the dedicated income account used by the assessment product if needed."""
        account_model = self.env['account.account'].sudo()
        account = self.env.ref(ASSESSMENT_INCOME_ACCOUNT_XMLID, raise_if_not_found=False)

        if account and account.exists():
            account.write(ASSESSMENT_INCOME_ACCOUNT_VALUES)
            return account

        account = account_model.search([
            ('code_store', '=', ASSESSMENT_INCOME_ACCOUNT_VALUES['code_store']),
        ], limit=1)
        if account:
            account.write(ASSESSMENT_INCOME_ACCOUNT_VALUES)
        else:
            account = account_model.create(ASSESSMENT_INCOME_ACCOUNT_VALUES)

        xmlid = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'my_custom_modul'),
            ('name', '=', 'account_assessment_income'),
        ], limit=1)
        if xmlid:
            xmlid.res_id = account.id
        else:
            self.env['ir.model.data'].sudo().create({
                'module': 'my_custom_modul',
                'name': 'account_assessment_income',
                'model': 'account.account',
                'res_id': account.id,
                'noupdate': False,
            })
        return account
