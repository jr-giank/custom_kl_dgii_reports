from odoo import models, fields


class DgiiReportConfirmationWizard(models.TransientModel):
    """
    This wizard only objective is to show a messege of confirmation when a dgii report
    sent.
    """
    _name = 'dgii.report.confirmation.wizard'
    _description = "DGII Report Confirmation Wizard"

    report_id = fields.Many2one('dgii.reports', 'Report')

    def confirmation(self):
        self.report_id.state_sent()
