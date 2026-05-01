from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    tipe_asesi = fields.Selection(
        selection=[
            ('internal', 'Internal'),
            ('external', 'External'),
        ],
        string='Tipe Asesi',
        required=True,
        default='external',
    )
