# -*- coding: utf-8 -*-
import re
from odoo import api, models
from odoo.addons.iap import jsonrpc, InsufficientCreditError

DEFAULT_ENDPOINT = 'http://localhost:8069'

class RevealIAP(models.Model):
    _inherit = 'crm.lead.rule'

    def test_rule(self, path = "/", ip=None):
        
        new_user = self.env['reveal.ip.history'].create({
            'ip': ip
        })

        if new_user:
            active_rules = self.search([['active', '=', True]])
            rules = []
            for active_rule in active_rules:
                try:
                    if re.match(active_rule.url, path, re.I | re.M):
                        rules.append(active_rule)
                except:
                    pass

            rules = [{
                'rule_id': active_rule.id,
                'lead_for': active_rule.lead_for,
                'countries': [{'name': x.name, 'country_code': x.code} for x in active_rule.country_ids],
                'url': active_rule.url,
                'company_size_min': active_rule.company_size_min,
                'company_size_max': active_rule.company_size_max,
                'industry_tags': [x.name for x in active_rule.industry_tags],
                'preferred_role': active_rule.preferred_role.name,
                'other_role': [x.name for x in active_rule.other_role],
                'seniority': active_rule.seniority.name,
            } for active_rule in rules]

            if len(rules) > 0:
                user_token = self.env['iap.account'].get('cb')
                params = {
                    'account_token': user_token.account_token,
                    'ip': ip,
                    'rules': rules
                }

                endpoint = self.env['ir.config_parameter'].sudo().get_param('reveal.endpoint', DEFAULT_ENDPOINT)

                try:
                    responce = jsonrpc(endpoint + '/reveal', params=params)
                    for data in responce:
                        if data['reveal_data']:
                            rule = self.search([['id', '=', data['rule_id']]])
                            lead_data = {
                                'type': 'opportunity' if rule['lead_type'] == "opportunity" else "lead",
                                'name': 'Lead generated by reveal',
                                'partner_name': data['reveal_data']['company_name'],
                                'phone': data['reveal_data']['phone'],
                                'website': data['reveal_data']['website'],
                                'street': data['reveal_data']['address'],
                                'team_id': rule.team_id.id,
                                'tag_ids': [(6, 0, [x.id for x in rule.tag_ids])],
                                'user_id': rule.user_id.id,
                                'priority': rule.priority,
                                'stage_id': rule.stage_id.id,
                            }

                            if rule['lead_for'] == 'people' and data['people_data']:
                                lead_data.update({
                                    'contact_name': data['people_data']['fullname'],
                                    'email_from': data['people_data']['email'],
                                    'function': data['people_data']['role'],
                                })
                            lead = self.env['crm.lead'].create(lead_data)
                            rule.write({
                                'lead_ids': [(4, lead.id)]
                            })
                except InsufficientCreditError as e:
                    raise e # Here Send Email to Admin
                except Exception as e:
                    pass

        return True
