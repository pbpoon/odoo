# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests

class TestUi(odoo.tests.HttpSeleniumCase):

    post_install = True
    at_install = False

    def test_01_admin_shop_customize_tour(self):
        self.selenium_run(
            "/",
            "odoo.__DEBUG__.services['web_tour.tour'].run('shop_customize')",
            ready="odoo.__DEBUG__.services['web_tour.tour'].tours.shop_customize.ready",
            login="admin")
