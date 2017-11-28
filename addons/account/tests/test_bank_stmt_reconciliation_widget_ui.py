from odoo.tests import HttpSeleniumCase

class TestUi(HttpSeleniumCase):
    post_install = True
    at_install = False

    def test_01_admin_bank_statement_reconciliation(self):
        self.selenium_run(
            "/",
            "odoo.__DEBUG__.services['web.Tour'].run('bank_statement_reconciliation', 'test')",
            ready="odoo.__DEBUG__.services['web.Tour'].tours.bank_statement_reconciliation",
            login="admin")
