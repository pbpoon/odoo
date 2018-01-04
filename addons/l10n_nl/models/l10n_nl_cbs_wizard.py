#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (C) 2013-2015 Akretion (http://www.akretion.com)

import base64

from datetime import datetime

from odoo import api, fields, models, release, _


class L10nNlCBS(models.TransientModel):
    _name = 'l10n_nl.cbs'
    _description = 'Centraal Bureau voor de Statistiek'

    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    data = fields.Binary('CBS File', readonly=True)
    filename = fields.Char(string='Filename', size=256, readonly=True)

    @api.multi
    def generate_cbs_file(self, invoices):
        ''' The CBS file is a file containing lines of 115 characters exactly.
        Each information must be sized/positioned in the right way.

        Documentation found in:
        https://www.cbs.nl/en-gb/deelnemers%20enquetes/overzicht/bedrijven/onderzoek/lopend/international-trade-in-goods/idep-code-lists
        :param invoices: The impacted invoices in the period.
        :return: The content of the file as str.
        '''
        self.ensure_one()

        company = self.env.user.company_id
        vat = company.vat
        now = datetime.now()
        registration_number = company.l10n_nl_cbs_reg_number or ''
        software_version = release.version

        # The software_version looks like saas~11.1+e but we have maximum 5 characters allowed
        software_version = software_version.replace('saas~', '').replace('+e', '')

        # HEADER LINE
        file_content = ''.join([
            '9801',                                                             # Record type           length=4
            vat and vat[2:].replace(' ', '').ljust(12) or ''.ljust(12),         # VAT number            length=12
            self.date_from[:4] + self.date_from[5:7],                           # Review perior         length=6
            (company.name or '').ljust(40),                                     # Company name          length=40
            registration_number.ljust(6),                                       # Registration number   length=6
            software_version.ljust(5),                                          # Version number        length=5
            now.strftime('%Y%m%d'),                                             # Creation date         length=8
            now.strftime('%H%M%S'),                                             # Creation time         length=6
            company.phone and\
                company.phone.replace(' ', '')[:15].ljust(15) or ''.ljust(15),  # Telephone number      length=15
            ''.ljust(13),                                                       # Reserve               length=13
        ]) + '\n'

        # CONTENT LINES
        i = 1
        for inv in invoices:
            country = inv.partner_id.country_id
            vat = inv.company_id.vat
            num = len(inv.number) < 8 and inv.number or inv.number[:8]
            for line in inv.invoice_line_ids:
                product = line.product_id and line.product_id.intrastat_id and line.product_id.intrastat_id.name or ''
                mass = line.product_id and line.quantity * line.product_id.weight or 0
                file_content += ''.join([
                    inv.date_invoice[:4] + inv.date_invoice[5:7],               # Transaction period    length=6
                    '7',                                                        # Commodity flow        length=1
                    vat and vat[2:].replace(' ', '').ljust(12) or ''.ljust(12), # VAT number            length=12
                    str(i).zfill(5),                                            # Line number           length=5
                    ''.ljust(3),                                                # Country of origin     length=3
                    (country and country.code or '').ljust(3),                  # Destination country   length=3
                    '3',                                                        # Mode of transport     length=1
                    '0',                                                        # Container             length=1
                    '00',                                                       # Traffic region/port   length=2
                    '00',                                                       # Statistical procedure length=2
                    '1',                                                        # Transaction           length=1
                    product.replace(' ', '')[:8].ljust(8),                      # Commodity code        length=8
                    '00',                                                       # Taric                 length=2
                    mass >= 0 and '+' or '-',                                   # Mass sign             length=1
                    str(int(mass)).zfill(10),                                   # Mass                  length=10
                    '+',                                                        # Supplementary sign    length=1
                    '0000000000',                                               # Supplementary unit    length=10
                    inv.amount_total_signed >= 0 and '+' or '-',                # Invoice sign          length=1
                    str(int(line.price_subtotal)).zfill(10),                    # Invoice value         length=10
                    '+',                                                        # Statistical sign      length=1
                    '0000000000',                                               # Statistical value     length=10
                    (num + str(i).zfill(2)).ljust(10),                          # Administration number length=10
                    ''.ljust(3),                                                # Reserve               length=3
                    ' ',                                                        # Correction items      length=1
                    '000',                                                      # Preference            length=3
                    ''.ljust(7),                                                # Reserve               length=7
                ]) + '\n'
                i += 1

        # FOOTER LINE
        file_content += ''.join([
            '9899',                                                             # Record type           length=4
            ''.ljust(111)                                                       # Reserve               length=111
        ])

        return file_content

    @api.multi
    def generate_cbs(self):
        self.ensure_one()

        company = self.env.user.company_id
        intrastat_countries = self.env.ref('base.europe').country_ids - self.env.ref('base.nl')
        invoices = self.env['account.invoice'].search([
            ('type', '=', 'out_invoice'),
            ('state', 'in', ['open', 'paid']),
            ('company_id', '=', company.id),
            ('partner_id.country_id', 'in', intrastat_countries.ids),
            ('date_invoice', '>=', self.date_from),
            ('date_invoice', '<=', self.date_to),
        ])

        file_content = self.generate_cbs_file(invoices)

        self.write({
            'data': base64.encodestring(file_content.encode()),
            'filename': '%s_%s.csv' % (self.date_from[5:7], self.date_from[:4]),
        })

        return {
            'name': 'CBS',
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=l10n_nl.cbs&id=" + str(self.id) + "&filename_field=filename&field=data&download=true&filename=" + self.filename,
            'target': 'self',
        }
