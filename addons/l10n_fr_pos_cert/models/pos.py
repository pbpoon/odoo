from datetime import datetime
from hashlib import sha256
from json import dumps

from openerp import models, api, fields
from fields.DateTime import context_timestamp, from_string as date_from_string
from openerp.tools.translate import _
from openerp.exceptions import UserError

NOT_SAME_DAY_ERROR = _("This session has been opened another day. To comply with the French law, you should close sessions on a daily basis. Please close session %s and open a new one.")


def ctx_tz(record, field):
    return context_timestamp(record, date_from_string(record[field]))


class pos_config(models.Model):
    _inherit = 'pos.config'

    @api.multi
    def open_ui(self):
        date_today = datetime.utcnow()
        for config in self.filtered(lambda c: c.company_id._is_accounting_unalterable()):
            if config.current_session_id:
                session_start = date_from_string(config.current_session_id.start_at)
                if session_start.date() != date_today.date():
                    raise UserError(NOT_SAME_DAY_ERROR % config.current_session_id.name)
        return super(pos_config, self).open_ui()


class pos_session(models.Model):
    _inherit = 'pos.session'

    @api.multi
    def open_frontend_cb(self):
        date_today = datetime.utcnow()
        for session in self.filtered(lambda s: s.config_id.company_id._is_accounting_unalterable()):
            session_start = date_from_string(session.start_at)
            if session_start.date() != date_today.date():
                raise UserError(NOT_SAME_DAY_ERROR % session.name)
        return super(pos_session, self).open_frontend_cb()


ORDER_FIELDS = ['date_order', 'user_id', 'lines', 'statement_ids', 'pricelist_id', 'partner_id', 'session_id', 'pos_reference', 'sale_journal', 'fiscal_position_id']
LINE_FIELDS = ['notice', 'product_id', 'qty', 'price_unit', 'discount', 'tax_ids', 'tax_ids_after_fiscal_position']
ERR_MSG = _('According to the French law, you cannot modify a %s. Forbidden fields: %s.')


class pos_order(models.Model):
    _inherit = 'pos.order'

    l10n_fr_pos_cert_hash = fields.Char(string="Inalteralbility Hash", readonly=True, copy=False)
    l10n_fr_pos_cert_sequence_number = fields.Integer(string="Inalteralbility No Gap Sequence #", readonly=True, copy=False)
    l10n_fr_pos_cert_string_to_hash = fields.Char(compute='_compute_string_to_hash', readonly=True, store=False)

    def _get_new_hash(self, secure_seq_number):
        """ Returns the hash to write on pos orders when they get posted"""
        self.ensure_one()
        #get the only one exact previous order in the securisation sequence
        prev_order = self.search([('state', 'in', ['paid', 'done', 'invoiced']),
                                 ('company_id', '=', self.company_id.id),
                                 ('l10n_fr_pos_cert_sequence_number', '!=', 0),
                                 ('l10n_fr_pos_cert_sequence_number', '=', int(secure_seq_number) - 1)])
        if prev_order and len(prev_order) != 1:
            raise UserError(
               _('An error occured when computing the inalterability. Impossible to get the unique previous posted point of sale order.'))

        #build and return the hash
        return self._compute_hash(prev_order.l10n_fr_pos_cert_hash if prev_order else '')

    def _compute_hash(self, previous_hash):
        """ Computes the hash of the browse_record given as self, based on the hash
        of the previous record in the company's securisation sequence given as parameter"""
        self.ensure_one()
        hash_string = sha256(previous_hash + self.l10n_fr_pos_cert_string_to_hash)
        return hash_string.hexdigest()

    def _compute_string_to_hash(self):
        def _getattrstring(obj, field_str):
            field_value = obj[field_str]
            if obj._fields[field_str].type == 'many2one':
                field_value = field_value.id
            if obj._fields[field_str].type in ['many2many', 'one2many']:
                field_value = field_value.ids
            return str(field_value)

        for order in self:
            values = {}
            for field in ORDER_FIELDS:
                values[field] = _getattrstring(order, field)

            for line in order.lines:
                for field in LINE_FIELDS:
                    k = 'line_%d_%s' % (line.id, field)
                    values[k] = _getattrstring(line, field)
            #make the json serialization canonical
            #  (https://tools.ietf.org/html/draft-staykov-hu-json-canonical-form-00)
            order.l10n_fr_pos_cert_string_to_hash = dumps(values, sort_keys=True, encoding="utf-8",
                                                ensure_ascii=True, indent=None,
                                                separators=(',',':'))

    @api.multi
    def write(self, vals):
        has_been_posted = False
        for order in self:
            if order.company_id._is_accounting_unalterable(raise_on_nocountry=True):
                # write the hash and the secure_sequence_number when posting or invoicing an pos.order
                if vals.get('state') in ['paid', 'done', 'invoiced']:
                    has_been_posted = True

                # restrict the operation in case we are trying to write a forbidden field
                if (order.state in ['paid', 'done', 'invoiced'] and set(vals).intersection(ORDER_FIELDS)):
                    raise UserError(ERR_MSG % ('point of sale order', ', '.join(ORDER_FIELDS)))
                # restrict the operation in case we are trying to overwrite existing hash
                if (order.l10n_fr_pos_cert_hash and 'l10n_fr_pos_cert_hash' in vals) or (order.l10n_fr_pos_cert_sequence_number and 'l10n_fr_pos_cert_sequence_number' in vals):
                    raise UserError(_('You cannot overwrite the values ensuring the inalterability of the point of sale.'))
        res = super(pos_order, self).write(vals)
        # write the hash and the secure_sequence_number when posting or invoicing a pos order
        if has_been_posted:
            for order in self.filtered(lambda o: o.company_id._is_accounting_unalterable() and
                                                not (o.l10n_fr_pos_cert_sequence_number or o.l10n_fr_pos_cert_hash)):
                new_number = order.company_id.l10n_fr_pos_cert_sequence_id.next_by_id()
                vals_hashing = {'l10n_fr_pos_cert_sequence_number': new_number,
                                'l10n_fr_pos_cert_hash': order._get_new_hash(new_number)}
                res |= super(pos_order, order).write(vals_hashing)
        return res

    @api.model
    def _check_hash_integrity(self, company_id):
        """Checks that all posted or invoiced pos orders have still the same data as when they were posted
        and raises an error with the result.
        """
        def build_order_info(order):
            entry_reference = _('(Receipt ref.: %s)')
            order_reference_string = order.pos_reference and entry_reference % order.pos_reference or ''
            return [ctx_tz(order, 'date_order'), order.l10n_fr_pos_cert_sequence_number, order.name, order_reference_string, ctx_tz(order, 'write_date')]

        orders = self.search([('state', 'in', ['paid', 'done', 'invoiced']),
                             ('company_id', '=', company_id),
                             ('l10n_fr_pos_cert_sequence_number', '!=', 0)],
                            order="l10n_fr_pos_cert_sequence_number ASC")

        if not orders:
            raise UserError(_('There isn\'t any order flagged for data inalterability yet for the company %s. This mechanism only runs for point of sale orders generated after the installation of the module France - Certification CGI 286 I-3 bis. - POS') % self.env.user.company_id.name)
        previous_hash = ''
        start_order_info = []
        for order in orders:
            if order.l10n_fr_pos_cert_hash != order._compute_hash(previous_hash=previous_hash):
                raise UserError(_('Corrupted data on point of sale order with id %s.') % order.id)
            previous_hash = order.l10n_fr_pos_cert_hash

        orders_sorted_date = orders.sorted(lambda o: o.date_order)
        start_order_info = build_order_info(orders_sorted_date[0])
        end_order_info = build_order_info(orders_sorted_date[-1])

        # Raise on success
        raise UserError(_('''Successful test !

                         The point of sale orders are guaranteed to be in their original and inalterable state
                         From: %s %s recorded on %s
                         To: %s %s recorded on %s

                         For this report to be legally meaningful, please download your certification from your customer account on Odoo.com (Only for Odoo Enterprise users).'''
                         ) % (start_order_info[2],
                              start_order_info[3],
                              start_order_info[0],
                              end_order_info[2],
                              end_order_info[3],
                              end_order_info[0]))

    @api.model
    def check_global_inalterability(self, user_id):
        check_string = 'Pos Orders:\n'
        try:
            self.env['pos.order']._check_hash_integrity(user_id)
        except UserError as order_res:
            check_string += order_res[0] + "\n\nJournal Entries:\n"

        try:
            self.env['account.move']._check_hash_integrity(user_id)
        except UserError as move_res:
            check_string += move_res[0]

        raise UserError(check_string)


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    @api.multi
    def write(self, vals):
        # restrict the operation in case we are trying to write a forbidden field
        if set(vals).intersection(LINE_FIELDS):
            if any(l.company_id._is_accounting_unalterable(raise_on_nocountry=True) and l.order_id.state in ['done', 'invoiced'] for l in self):
                raise UserError(ERR_MSG % ('point of sale order line', ', '.join(LINE_FIELDS)))
        return super(PosOrderLine, self).write(vals)
