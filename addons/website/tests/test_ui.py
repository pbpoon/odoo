# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
import odoo.tests

class TestUiTranslate(odoo.tests.HttpSeleniumCase):
    def test_admin_tour_rte_translator(self):
        self.selenium_run(
            "/",
            "odoo.__DEBUG__.services['web_tour.tour'].run('rte_translator')",
            ready="odoo.__DEBUG__.services['web_tour.tour'].tours.rte_translator.ready",
            login='admin',
            max_tries=30)

class TestUi(odoo.tests.HttpSeleniumCase):
    post_install = True
    at_install = False

    def test_02_admin_tour_banner(self):
        self.selenium_run(
            "/",
            "odoo.__DEBUG__.services['web_tour.tour'].run('banner')",
            ready="odoo.__DEBUG__.services['web_tour.tour'].tours.banner.ready",
            login='admin')

class TestUiNotLogged(odoo.tests.HttpSeleniumCase):
    post_install = True
    at_install = False

    def test_01_public_homepage(self):
        self.selenium_run(
            "/",
            r"window.document.body.classList.add('test-success')",
            ready="'website.content.snippets.animation' in odoo.__DEBUG__.services")

    # def test_03_public_homepage(self):
    #    """Pure selenium test"""
    #    self.browser_get('/')
    #    self.assert_find_element_by_id('oe_main_menu_navbar')
    #    self.assertIn('Home', self.driver.title)