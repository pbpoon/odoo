# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.addons.base.models.ir_mail_server import MailDeliveryException

_logger = logging.getLogger(__name__)


# TODO for future versions:
# - make all of this TZ aware: for now, all the timeframes are bound at midnight UTC
class Digest(models.Model):
    _name = 'digest.digest'
    _description = 'Digest'

    #
    # Generic digest implementation
    #

    name = fields.Char(string='Name', required=True, translate=True)
    user_ids = fields.Many2many('res.users', string='Recipients',
                                required=True, domain="[('share', '=', False)]")
    periodicity = fields.Selection([('weekly', 'Weekly'),
                                    ('monthly', 'Monthly'),
                                    ('quarterly', 'Quarterly')],
                                   string='Periodicity', default='weekly', required=True)
    active = fields.Boolean(string='Active', default=True)
    next_run_date = fields.Date(string='Next Send Date')
    template_id = fields.Many2one('mail.template', string='Email Template',
                                  domain="[('model','=','digest.digest')]",
                                  default=lambda self: self.env.ref('digest.digest_mail_template'),
                                  required=True)
    start_date = fields.Date(required=True, default=fields.Date.today())  # technical field used to compute kpis
    end_date = fields.Date(required=True, default=fields.Date.today())    # technical field used to compute kpis
    currency_id = fields.Many2one('res.currency', string='Currency')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)
    available_fields = fields.Char(compute='_compute_available_fields')

    def _compute_available_fields(self):
        for digest in self:
            kpis_values_fields = []
            for field_name, field in digest._fields.items():
                if field.type == 'boolean' and (field_name.startswith('kpi_') or field_name.startswith('x_kpi_')) and digest[field_name]:
                    kpis_values_fields += [field_name + '_value']
            digest.available_fields = ', '.join(kpis_values_fields)

    @api.onchange('periodicity')
    def onchange_periodicity(self):
        self.next_run_date = fields.Date.to_string(self._get_next_run_date(self.periodicity))

    @api.model
    def _get_next_run_date(self, periodicity):
        if periodicity == 'weekly':
            delta = relativedelta(weeks=1)
        elif periodicity == 'monthly':
            delta = relativedelta(months=1)
        elif periodicity == 'quarterly':
            delta = relativedelta(months=3)
        return date.today() + delta

    @api.model
    def _compute_timeframes(self):
        timeframes = {}
        timeframes.update(yesterday=(date.today() + relativedelta(days=-1), date.today()))
        timeframes.update(lastweek=(date.today() + relativedelta(weeks=-1), date.today()))
        timeframes.update(lastmonth=(date.today() + relativedelta(months=-1), date.today()))
        return timeframes

    def compute_kpis(self):
        self.ensure_one()
        res = {}
        for tf_name, tf in self._compute_timeframes().items():
            self.write({'start_date': tf[0], 'end_date': tf[1]})
            kpis = {}
            for field_name, field in self._fields.items():
                if field.type == 'boolean' and (field_name.startswith('kpi_') or field_name.startswith('x_kpi_')) and self[field_name]:
                    kpis.update({field_name: self[field_name + '_value']})
            res.update({tf_name: kpis})
        return res

    def send_digests_now(self):
        for digest in self:
            recipients_emails = digest.user_ids.mapped('email')
            recipients = ",".join(recipients_emails)
            try:
                mail_id = digest.template_id.with_context(email_to=recipients).send_mail(digest.id, raise_exception=True)
                if mail_id:
                    digest.next_run_date = self._get_next_run_date(digest.periodicity)
            except MailDeliveryException as e:
                _logger.error('Error while sending digest emails')
                raise e

    @api.model
    def _cron_send_digest_email(self):
        _logger.debug('Sending automatic digests')
        self.search([('next_run_date', '<=', fields.Date.today())]).send_digests_now()

    #
    # Default KPIs
    #
    # Users can add their own ones by adding the corresponding boolean +
    # computed field
    #

    kpi_res_users_connected = fields.Boolean(string='Connected Users')
    kpi_res_users_connected_value = fields.Integer(compute='_compute_kpi_res_users_connected_value')

    @api.depends('start_date', 'end_date')
    def _compute_kpi_res_users_connected_value(self):
        for record in self:
            user_connected = self.env['res.users'].search_count([("login_date", ">=", self.start_date),
                                                                 ("login_date", "<", self.end_date)])
            record.kpi_res_users_connected_value = user_connected

    kpi_mail_message_total = fields.Boolean(string='Messages')
    kpi_mail_message_total_value = fields.Integer(compute='_compute_kpi_mail_message_total_value')

    @api.depends('start_date', 'end_date')
    def _compute_kpi_mail_message_total_value(self):
        for record in self:
            total_messages = self.env['mail.message'].search_count([("create_date", ">=", self.start_date),
                                                                    ("create_date", "<", self.end_date)])
            record.kpi_mail_message_total_value = total_messages
