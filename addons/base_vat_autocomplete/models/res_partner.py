# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import re

from odoo import api, models

from suds.client import Client

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.onchange('vat')
    def vies_vat_change(self):
        def _check_city(lines, country='BE'):
            if country == 'GB':
                ukzip = '[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}'
                if re.match(ukzip, lines[-1]):
                    cp = lines.pop()
                    city = lines.pop()
                    return (cp, city)
            else:
                result = re.match('((?:L-|AT-)?[0-9\-]+) (.+)', lines[-1])
                if result:
                    lines.pop()
                    return (result.group(1), result.group(2))
            return False

        eu_country_codes = self.env.ref('base.europe').country_ids.mapped('code')
        for partner in self:
            if not partner.vat:
                return {}
            if len(partner.vat) > 5 and partner.vat[:2].lower() in eu_country_codes:
                try:
                    partner_vat = partner.compact_vat_number(partner.vat)
                    result = partner.vies_vat_check(partner_vat[:2], partner_vat[2:], except_to_simple_check=False)
                except:
                    # Avoid blocking the client when the service is unreachable/unavailable
                    return {}

                if not result:
                    return {}

                if (not partner.name) and (result['name'] != '---'):
                    partner.name = result['name']

                #parse the address from VIES and fill the partner's data
                if result['address'] == '---': return {}

                lines = [x for x in result['address'].split("\n") if x]
                if len(lines) == 1:
                    lines = [x.strip() for x in lines[0].split(',') if x]
                if len(lines) == 1:
                    lines = [x.strip() for x in lines[0].split('   ') if x]
                partner.street = lines.pop(0)
                if len(lines) > 0:
                    res = _check_city(lines, result['countryCode'])
                    if res:
                        partner.zip = res[0]
                        partner.city = res[1]
                if len(lines) > 0:
                    partner.street2 = lines.pop(0)

                country = self.env['res.country'].search([('code', '=', result['countryCode'])], limit=1)
                partner.country_id = country and country.id or False
