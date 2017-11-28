# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests

class TestUi(odoo.tests.HttpSeleniumCase):

    post_install = True
    at_install = False

    def test_01_admin_forum_tour(self):
        self.selenium_run(
            "/",
            "odoo.__DEBUG__.services['web_tour.tour'].run('question')",
            ready="odoo.__DEBUG__.services['web_tour.tour'].tours.question.ready",
            max_tries=25,
            login="admin")

    def test_02_demo_question(self):
        with self.cursor() as test_cr:
            env = self.env(cr=test_cr)
            forum = env.ref('website_forum.forum_help')
            demo = env.ref('base.user_demo')
            demo.karma = forum.karma_post + 1
        self.selenium_run(
            "/",
            "odoo.__DEBUG__.services['web_tour.tour'].run('forum_question')",
            ready="odoo.__DEBUG__.services['web_tour.tour'].tours.forum_question.ready",
            max_tries=25,
            login="demo")
