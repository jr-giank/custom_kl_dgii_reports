# Part of Domincana Premium.
# See LICENSE file for full copyright and licensing details.
# © 2018 José López <jlopez@indexa.do>
# © 2018 Gustavo Valverde <gustavo@iterativo.do>
# © 2018 Eneldo Serrata <eneldo@marcos.do>

{
    'name': "Custom Declaraciones DGII",
    'summary': """
        This module adds the functionality of the fiscal reporting of the Dominican Republic
        """,
    'author': "Indexa, SRL, "
              "iterativo SRL",
    'license': 'LGPL-3',
    'category': 'Accounting',
    'version': '15.0.1.27.28',
    'depends': ['base', 'custom_l10n_do_accounting'],
    'data': [
        'data/invoice_service_type_detail_data.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/res_partner_views.xml',
        'views/account_account_views.xml',
        'views/account_invoice_views.xml',
        'views/dgii_report_views.xml',
        'views/menu.xml',
        'wizard/dgii_report_regenerate_wizard_views.xml',
        'wizard/dgii_report_confirmation_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # '/custom_kl_dgii_reports/static/src/js/widget.js',
            '/custom_kl_dgii_reports/static/src/less/dgii_reports.css',
        ],
    },
}
