# Part of Domincana Premium.
# See LICENSE file for full copyright and licensing details.
import json
from odoo import models, fields, api, _
from datetime import datetime as dt

PAYMENT_DICT = {
    'cash': '01',
    'bank': '02',
    'card': '03',
    'credit': '04',
    'swap': '05',
    'credit_note': '06',
    'mixed': '07',
}

DEFAULT_PAYMENT_FORM = '04'


class InvoiceServiceTypeDetail(models.Model):
    _name = 'invoice.service.type.detail'
    _description = "Invoice Service Type Detail"

    name = fields.Char()
    code = fields.Char(size=2)
    parent_code = fields.Char()

    _sql_constraints = [
        ('code_unique', 'unique(code)', _('Code must be unique')),
    ]


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    payment_date = fields.Date(compute='_compute_invoice_payment_date', store=True)
    withholding_date = fields.Date(compute='_compute_invoice_payment_date', store=True)

    service_total_amount = fields.Monetary(
        compute='_compute_amount_fields',
        store=True,
        currency_field='company_currency_id',
    )

    good_total_amount = fields.Monetary(
        compute='_compute_amount_fields',
        store=True,
        currency_field='company_currency_id',
    )
    invoiced_itbis = fields.Monetary(
        compute='_compute_taxes_fields',
        store=True,
        help='Account fiscal type (A52)',
        currency_field='company_currency_id',
    )
    withholded_itbis = fields.Monetary(
        compute='_compute_withheld_taxes',
        help='Account fiscal type (A34, A36)',
        store=True,
        currency_field='company_currency_id',
    )
    proportionality_tax = fields.Monetary(
        compute='_compute_taxes_fields',
        store=True,
        help='Account fiscal type (A29, A30)',
        currency_field='company_currency_id',
    )
    cost_itbis = fields.Monetary(
        compute='_compute_taxes_fields',
        store=True,
        help='Account fiscal type (A51)',
        currency_field='company_currency_id',
    )
    advance_itbis = fields.Monetary(
        compute='_compute_advance_itbis',
        store=True,
        currency_field='company_currency_id',
    )
    isr_withholding_type = fields.Char(
        compute='_compute_isr_withholding_type',
        store=True,
        size=2
    )
    income_withholding = fields.Monetary(
        compute='_compute_withheld_taxes',
        store=True,
        help='Account fiscal type (ISR, A38)',
        currency_field='company_currency_id',
    )
    selective_tax = fields.Monetary(
        compute='_compute_taxes_fields',
        store=True,
        help='Account fiscal type (A53)',
        currency_field='company_currency_id',
    )
    other_taxes = fields.Monetary(
        compute='_compute_taxes_fields',
        store=True,
        help='Account fiscal type (A54)',
        currency_field='company_currency_id',
    )
    legal_tip = fields.Monetary(
        compute='_compute_taxes_fields',
        store=True,
        help='Account fiscal type (A55)',
        currency_field='company_currency_id',
    )
    payment_form = fields.Selection(
        [
            ('01', 'Cash'),
            ('02', 'Check / Transfer / Deposit'),
            ('03', 'Credit Card / Debit Card'),
            ('04', 'Credit'),
            ('05', 'Swap'),
            ('06', 'Credit Note'),
            ('07', 'Mixed'),
        ],
        compute='_compute_in_invoice_payment_form',
    )
    third_withheld_itbis = fields.Monetary(
        compute='_compute_withheld_taxes',
        help='Account fiscal type (A34, A36)',
        store=True,
        currency_field='company_currency_id',
    )
    third_income_withholding = fields.Monetary(
        compute='_compute_withheld_taxes',
        help='Account fiscal type (ISR, A38)',
        store=True,
        currency_field='company_currency_id',
    )
    is_exterior = fields.Boolean(compute='_compute_is_exterior')
    service_type_detail = fields.Many2one('invoice.service.type.detail')
    fiscal_status = fields.Selection(
        [('normal', 'Partial'), ('done', 'Reported'), ('blocked', 'Not Sent')],
        copy=False,
        help="* The \'Grey\' status means ...\n"
        "* The \'Green\' status means ...\n"
        "* The \'Red\' status means ...\n"
        "* The blank status means that the invoice have"
        "not been included in a report.",
    )

    def _get_invoice_payment_widget(self):
        j = self.invoice_payments_widget
        return j['content'] if j else []

    @api.depends('payment_state')
    def _compute_invoice_payment_date(self):
        for inv in self:
            if inv.payment_state in ['paid', 'in_payment'] and inv.amount_total > 0:
                payments = inv._get_invoice_payment_widget()
                inv.payment_date = (
                    payments[0]['date']
                    if payments[0]['date'] >= inv.invoice_date
                    else inv.invoice_date
                )
                if self._is_customer_invoice(inv) and any(
                    [inv.third_withheld_itbis, inv.third_income_withholding]
                ):
                    inv.withholding_date = inv.payment_date

    def _convert_to_local_currency(self, amount):
        sign = -1 if self.move_type in ['in_refund', 'out_refund'] else 1
        amount = self.currency_id._convert(
            amount, self.company_id.currency_id, self.company_id, self.date
        )
        return abs(amount * sign)

    def _get_tax_line_ids(self):
        return self.line_ids.filtered(lambda line: line.tax_ids is not False)

    @api.depends('line_ids', 'line_ids.price_unit', 'state')
    def _compute_taxes_fields(self):
        """Compute invoice common taxes fields"""
        for inv in self:

            line = inv._get_tax_line_ids()

            if inv.state != 'draft':

                inv.invoiced_itbis = inv._convert_to_local_currency(
                    sum(
                        line.filtered(
                            lambda tax: tax.tax_line_id.tax_group_id.name in ('ITBIS', 'ITBIS 18%'))
                        .mapped('price_unit')))

                inv.selective_tax = inv._convert_to_local_currency(
                    sum(
                        line.filtered(
                            lambda tax: tax.tax_line_id.tax_group_id.name == 'ISC').mapped('price_unit')))

                # Monto Otros Impuestos/Tasas
                inv.other_taxes = inv._convert_to_local_currency(
                    sum(
                        line.filtered(
                            lambda tax: tax.tax_line_id.tax_group_id.name ==
                            "Otros Impuestos").mapped('price_unit')))

                # Monto Propina Legal
                inv.legal_tip = inv._convert_to_local_currency(
                    sum(
                        line.filtered(
                            lambda tax: tax.tax_line_id.tax_group_id.name ==
                            'Propina').mapped('price_unit')))

                # ITBIS sujeto a proporcionalidad
                inv.proportionality_tax = inv._convert_to_local_currency(
                    sum(
                        line.filtered(
                            lambda tax: tax.account_id.account_fiscal_type in
                            ['A29', 'A30']).mapped('price_unit')))

                # ITBIS llevado al Costo
                inv.cost_itbis = inv._convert_to_local_currency(
                    sum(
                        line.filtered(
                            lambda tax: tax.account_id.account_fiscal_type ==
                            'A51').mapped('price_unit')))

    def _is_vendor_invoice(self, inv):
        return inv.move_type == 'in_invoice'

    def _is_customer_invoice(self, inv):
        return inv.move_type == 'out_invoice'

    def _invoice_paid(self, inv):
        return inv.payment_state == 'paid'

    @api.depends('invoice_line_ids', 'invoice_line_ids.product_id', 'state')
    def _compute_amount_fields(self):
        """Compute Purchase amount by product type"""
        for inv in self:
            if inv.move_type in ['in_invoice', 'in_refund'] and inv.state != 'draft':
                service_amount = 0
                good_amount = 0

                for line in inv.invoice_line_ids:

                    # Calculated amount in goods
                    if line.product_id.type not in ['product', 'consu']:
                        service_amount += line.price_subtotal
                    else:
                        good_amount += line.price_subtotal
                inv.service_total_amount = inv._convert_to_local_currency(service_amount)
                inv.good_total_amount = inv._convert_to_local_currency(good_amount)

    @api.depends('line_ids', 'payment_state')
    def _compute_isr_withholding_type(self):
        """Compute ISR Withholding Type
        Keyword / Values:
        01 -- Alquileres
        02 -- Honorarios por Servicios
        03 -- Otras Rentas
        04 -- Rentas Presuntas
        05 -- Intereses Pagados a Personas Jurídicas
        06 -- Intereses Pagados a Personas Físicas
        07 -- Retención por Proveedores del Estado
        08 -- Juegos Telefónicos
        """
        for inv in self.filtered(
                lambda i: i.move_type == "in_invoice" and i.payment_state in ['in_payment', 'paid']):

            tax_line_id = inv.line_ids.filtered(
                lambda t: t.account_id.account_fiscal_type == 'ISR')
            if tax_line_id:  # invoice tax lines use case
                inv.isr_withholding_type = tax_line_id[0].account_id.isr_retention_type
            else:  # in payment/journal entry use case
                aml_ids = self.env["account.move"].browse(
                    p["move_id"] for p in inv._get_invoice_payment_widget()
                ).mapped("line_ids").filtered(
                    lambda aml: aml.account_id.isr_retention_type)
                if aml_ids:
                    inv.isr_withholding_type = aml_ids[0].account_id.isr_retention_type
                else:
                    inv.isr_withholding_type = ''

    def _get_payment_string(self):
        """Compute Vendor Bills payment method string
        Keyword / Values:
        cash        -- Efectivo
        bank        -- Cheques / Transferencias / Depósitos
        card        -- Tarjeta Crédito / Débito
        credit      -- Compra a Crédito
        swap        -- Permuta
        credit_note -- Notas de Crédito
        mixed       -- Mixto
        """
        payments = []
        payment_string = ""
        for payment in self._get_invoice_payment_widget():
            payment_id = self.env['account.payment'].browse(payment['account_payment_id'])
            if payment_id:
                if payment_id.journal_id.type in ['cash', 'bank']:
                    payment_string = payment_id.journal_id.l10n_do_payment_form

            if not payment_id:
                move_id = self.env['account.move'].browse(payment['move_id'])
                if move_id:
                    payment_string = 'swap'

            # If invoice is paid, but the payment doesn't come from
            # a journal, assume it is a credit note
            payment = payment_string if payment_id or move_id else 'credit_note'
            payments.append(payment)

        if len(payments) > 1:
            return 'mixed'
        return payments[0]

    @api.depends('payment_state')
    def _compute_in_invoice_payment_form(self):
        for inv in self:
            if self._invoice_paid(inv) and inv.amount_total > 0:
                inv.payment_form = PAYMENT_DICT.get(inv._get_payment_string())
            else:
                inv.payment_form = DEFAULT_PAYMENT_FORM

    def _get_payment_move_iterator(self, payment, inv_type, witheld_type):
        payment_id = self.env['account.payment'].browse(payment['account_payment_id'])
        if payment_id:
            if inv_type == 'out_invoice':
                return [
                    move_line.debit
                    for move_line in payment_id.move_id.line_ids
                    if move_line.account_id.account_fiscal_type in witheld_type
                ]
            else:
                return [
                    move_line.credit
                    for move_line in payment_id.move_id.line_ids
                    if move_line.account_id.account_fiscal_type in witheld_type
                ]
        else:
            move_id = self.env['account.move'].browse(payment.get('move_id'))
            if move_id:
                if inv_type == 'out_invoice':
                    return [
                        move_line.debit
                        for move_line in move_id.line_ids
                        if move_line.account_id.account_fiscal_type in witheld_type
                    ]
                else:
                    return [
                        move_line.credit
                        for move_line in move_id.line_ids
                        if move_line.account_id.account_fiscal_type in witheld_type
                    ]

    @api.depends('payment_state')
    def _compute_withheld_taxes(self):
        for inv in self:
            inv.third_withheld_itbis = 0
            inv.third_income_withholding = 0
            if inv.amount_total > inv.amount_residual and inv.payment_state in ['paid', 'in_payment']:
                witheld_itbis_types = ['A34', 'A36']
                witheld_isr_types = ['ISR', 'A38']

                if self._is_vendor_invoice(inv):
                    inv.income_withholding = 0
                    inv.withholded_itbis = 0

                    #  ITBIS amount withheld for tax (Purchase)
                    for tax in inv._get_tax_line_ids():
                        withholded_line_balance = abs(tax.credit - tax.debit)

                        if tax.account_id.account_fiscal_type in witheld_itbis_types:
                            inv.withholded_itbis += withholded_line_balance

                    #  Income withholding amount for tax (Purchase)
                        if tax.account_id.account_fiscal_type in witheld_isr_types:
                            inv.income_withholding += withholded_line_balance

                for payment in inv._get_invoice_payment_widget():

                    witheld_itbis_line = sum(self._get_payment_move_iterator(
                        payment, inv.move_type,  witheld_itbis_types
                    ))

                    witheld_isr_line = sum(self._get_payment_move_iterator(
                        payment, inv.move_type,  witheld_isr_types
                    ))

                    if self._is_customer_invoice(inv):

                        if witheld_itbis_line:
                            # ITBIS Retenido por Terceros
                            inv.third_withheld_itbis = witheld_itbis_line
                        if witheld_isr_line:
                            # Retención de Renta por Terceros
                            inv.third_income_withholding = witheld_isr_line

                    elif self._is_vendor_invoice(inv):

                        if witheld_itbis_line:
                            # ITBIS Retenido a Terceros
                            inv.withholded_itbis = witheld_itbis_line
                        if witheld_isr_line:
                            # Retención de Renta a Terceros
                            inv.income_withholding = witheld_isr_line

    @api.depends('invoiced_itbis', 'cost_itbis', 'state')
    def _compute_advance_itbis(self):
        for inv in self:
            if inv.state != 'draft':
                inv.advance_itbis = inv.invoiced_itbis - inv.cost_itbis

    @api.depends('l10n_do_expense_type')
    def _compute_is_exterior(self):
        for inv in self:
            inv.is_exterior = (
                True
                if inv.partner_id.l10n_do_dgii_tax_payer_type == 'foreigner'
                else False
            )

    @api.onchange('l10n_do_expense_type')
    def onchange_service_type(self):
        self.service_type_detail = False
        return {
            'domain': {
                'service_type_detail': [('parent_code', '=', self.l10n_do_expense_type)]
            }
        }

    @api.onchange('journal_id')
    def ext_onchange_journal_id(self):
        self.service_type_detail = False

    @api.model
    def norma_recompute(self):
        """
        This method add all compute fields into []env
        add_todo and then recompute
        all compute fields in case dgii config change and need to recompute.
        :return:
        """
        active_ids = self._context.get("active_ids")
        invoice_ids = self.browse(active_ids)
        for k, v in self.fields_get().items():
            if v.get("store") and v.get("depends"):
                self.env.add_to_compute(self._fields[k], invoice_ids)

        self.recompute()
