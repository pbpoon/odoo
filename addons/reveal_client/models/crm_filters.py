from odoo import api, fields, models

from odoo.addons.crm.models import crm_stage
class CRMLeadRule(models.Model):
    _name = 'crm.lead.rule'
    _description = 'CRM Lead Rules'

    name = fields.Char(string='Rule Name', required=True, translate=True)
    active = fields.Boolean(default=True)

    # Website Filters
    country_ids = fields.Many2many('res.country', string='Countries')
    url = fields.Char(string='URL(Regex)')

    # Company Filters
    company_size_min = fields.Integer(string='Company Size Minimum')
    company_size_max = fields.Integer(string='Company Size Maximum')
    industry_tags = fields.Many2many('reveal.industry.tag',string="Industry Tags")

    # People Filters
    preferred_role = fields.Many2one('reveal.people.role', string="Preferred Roles")
    other_role = fields.Many2many('reveal.people.role', string="Other Roles")
    seniority = fields.Many2one('reveal.people.seniority', string="Seniority")

    # Lead / Opportunity Data
    lead_type = fields.Selection([('lead', 'Lead'), ('opportunity', 'Opportunity')],string='Lead Type', required=True, default="opportunity")
    lead_for = fields.Selection([('companies', 'Companies'), ('people', 'People')], string='Lead For', required=True)

    team_id = fields.Many2one('crm.team', string='Sales Channel')
    stage_id = fields.Many2one('crm.stage', string='Stage')
    tag_ids = fields.Many2many('crm.lead.tag', string='Tags')
    user_id = fields.Many2one('res.users', string='Salesperson', default=lambda self: self.env.user)
    priority = fields.Selection(crm_stage.AVAILABLE_PRIORITIES, string='Priority', default=crm_stage.AVAILABLE_PRIORITIES[0][0])

    lead_ids = fields.Many2many('crm.lead', string="Generated Lead / Opportunity")

class IndustryTag(models.Model):
    """ Tags of Acquisition Rules """
    _name = 'reveal.industry.tag'
    _description = 'Industry Tag'

    name = fields.Char(string='Tag Name', required=True, translate=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists!"),
    ]

class PeopleRole(models.Model):
    """ Roles for People Rules """
    _name = 'reveal.people.role'
    _description = 'People Role'

    name = fields.Char(string='Role Name', required=True, translate=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Role name already exists!"),
    ]

class PeopleSeniority(models.Model):
    """ Seniority for People Rules """
    _name = 'reveal.people.seniority'
    _description = 'People Seniority'

    name = fields.Char(string='Name', required=True, translate=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Name already exists!"),
    ]
