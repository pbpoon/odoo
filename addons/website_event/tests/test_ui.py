import odoo.tests


@odoo.tests.common.at_install(False)
@odoo.tests.common.post_install(True)
class TestUi(odoo.tests.HttpSeleniumCase):
    def test_admin(self):
        self.selenium_run(
            "/",
            "odoo.__DEBUG__.services['web_tour.tour'].run('event')",
            ready="odoo.__DEBUG__.services['web_tour.tour'].tours.event.ready",
            login='admin')
