# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import uuid

from hashlib import md5
from werkzeug import urls

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare
from odoo.addons.payment_alipay.controllers.main import AlipayController
from odoo.addons.payment.models.payment_acquirer import ValidationError

_logger = logging.getLogger(__name__)


class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('alipay', 'Alipay')])
    alipay_payment_method = fields.Selection([
        ('standard_checkout', 'Standard Checkout'),
        ('express_checkout', 'Express Checkout'),
    ], string='Payment Method', default='standard_checkout',
        help="  * Standard Checkout: For the Overseas seller \n  * Express Checkout: For the Chinese Seller")
    alipay_merchant_partner_id = fields.Char(
        string='Merchant Partner ID', required_if_provider='alipay', groups='base.group_user',
        help='The Merchant Partner ID is used to ensure communications coming from Alipay are valid and secured.')
    alipay_md5_signature_key = fields.Char(
        string='MD5 Signature key', required_if_provider='alipay', groups='base.group_user',
        help="The MD5 private key is the 32-byte string which is composed of English letters and numbers.")
    alipay_seller_email = fields.Char(string='Alipay seller Email', groups='base.group_user')

    def _get_feature_support(self):
        """Get advanced feature support by provider.

        Each provider should add its technical in the corresponding
        key for the following features:
            * fees: support payment fees computations
            * authorize: support authorizing payment (separates
                         authorization and capture)
            * md5 decryption : support saving payment data by md5 decryption
        """
        res = super(PaymentAcquirer, self)._get_feature_support()
        res['fees'].append('alipay')
        return res

    @api.model
    def _get_alipay_urls(self, environment):
        """ Alipay URLS """
        if environment == 'prod':
            return 'https://mapi.alipay.com/gateway.do'
        return 'https://openapi.alipaydev.com/gateway.do'

    @api.multi
    def alipay_compute_fees(self, amount, currency_id, country_id):
        """ Compute alipay fees.

            :param float amount: the amount to pay
            :param integer country_id: an ID of a res.country, or None. This is
                                       the customer's country, to be compared to
                                       the acquirer company country.
            :return float fees: computed fees
        """
        fees = 0.0
        if self.fees_active:
            country = self.env['res.country'].browse(country_id)
            if country and self.company_id.country_id.id == country.id:
                percentage = self.fees_dom_var
                fixed = self.fees_dom_fixed
            else:
                percentage = self.fees_int_var
                fixed = self.fees_int_fixed
            fees = (percentage / 100.0 * amount + fixed) / (1 - percentage / 100.0)
        return fees

    def get_trade_no(self):
        return str(uuid.uuid4())

    @api.multi
    def build_sign(self, val):
        data_string = '&'.join(["{}={}".format(k, v) for k, v in sorted(val.items()) if k not in ['sign', 'sign_type', 'reference']]) + self.alipay_md5_signature_key
        return md5(data_string.encode('utf-8')).hexdigest()

    @api.multi
    def _get_alipay_tx_values(self, values):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        tx = self.env['payment.transaction'].search([('reference', '=', values.get('reference'))])
        product_name = ", ".join(tx.sale_order_id.order_line.mapped('product_id.name')) if tx else "product: odoo"
        product_desc = ", ".join(tx.sale_order_id.order_line.filtered('product_id.description_sale').mapped('product_id.description_sale')).replace('\n', ',') if tx else "payment: odoo"

        alipay_tx_values = ({
            '_input_charset': 'utf-8',
            'body': product_desc[:400],  # support only 400 char (except special char) in body (product description)
            'notify_url': urls.url_join(base_url, AlipayController._notify_url),
            'out_trade_no': self.get_trade_no(),
            'partner': self.alipay_merchant_partner_id,
            'return_url': urls.url_join(base_url, AlipayController._return_url),
            'subject': product_name[:256],  # support only 256 char.
            'total_fee': values.get('amount') + values.get('fees'),
        })
        tx.write({'out_trade_no': alipay_tx_values['out_trade_no']})
        if self.alipay_payment_method == 'standard_checkout':
            alipay_tx_values.update({
                'service': 'create_forex_trade',
                'product_code': 'NEW_OVERSEAS_SELLER',
                'currency': values.get('currency').name,
            })
        else:
            alipay_tx_values.update({
                'service': 'create_direct_pay_by_user',
                'payment_type': 1,
                'seller_email': self.alipay_seller_email,
            })
        sign = self.build_sign(alipay_tx_values)
        alipay_tx_values.update({
            'sign_type': 'MD5',
            'sign': sign,
        })
        return alipay_tx_values

    @api.multi
    def alipay_form_generate_values(self, values):
        values.update(self._get_alipay_tx_values(values))
        return values

    @api.multi
    def alipay_get_form_action_url(self):
        return self._get_alipay_urls(self.environment)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    out_trade_no = fields.Char(string='Trade Number', readonly=True)
    provider = fields.Selection(related='acquirer_id.provider')

    # --------------------------------------------------
    # FORM RELATED METHODS
    # --------------------------------------------------

    @api.model
    def _alipay_form_get_tx_from_data(self, data):
        reference, txn_id, sign = data.get('reference'), data.get('trade_no'), data.get('sign')
        if not reference or not txn_id:
            error_msg = _('Alipay: received data with missing reference (%s) or txn_id (%s)') % (reference, txn_id)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        txs = self.env['payment.transaction'].search([('reference', '=', reference)])
        if not txs or len(txs) > 1:
            error_msg = 'Alipay: received data for reference %s' % (reference)
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        # verify sign
        sign_check = txs.acquirer_id.build_sign(data)
        if sign != sign_check:
            error_msg = _('Alipay: invalid sign, received %s, computed %s, for data %s') % (sign, sign_check, data)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        return txs

    @api.multi
    def _alipay_form_get_invalid_parameters(self, data):
        invalid_parameters = []

        if float_compare(float(data.get('total_fee', '0.0')), (self.amount + self.fees), 2) != 0:
            invalid_parameters.append(('total_fee', data.get('total_fee'), '%.2f' % self.amount))  # mc_gross is amount + fees
        if self.acquirer_id.alipay_payment_method == 'standard_checkout':
            if data.get('currency') != self.currency_id.name:
                invalid_parameters.append(('currency', data.get('currency'), self.currency_id.name))
        else:
            if data.get('seller_email') != self.acquirer_id.alipay_seller_email:
                invalid_parameters.append(('seller_email', data.get('seller_email'), self.acquirer_id.alipay_seller_email))
        return invalid_parameters

    @api.multi
    def _alipay_form_validate(self, data):
        status = data.get('trade_status')
        res = {
            'acquirer_reference': data.get('trade_no'),
        }
        if status in ['TRADE_FINISHED', 'TRADE_SUCCESS']:
            _logger.info('Validated Alipay payment for tx %s: set as done' % (self.reference))
            date_validate = fields.Datetime.now()
            res.update(state='done', date_validate=date_validate)
            return self.write(res)
        elif status == 'TRADE_CLOSED':
            _logger.info('Received notification for Alipay payment %s: set as Canceled' % (self.reference))
            res.update(state='cancel', state_message=data.get('close_reason', ''))
            return self.write(res)
        else:
            error = 'Received unrecognized status for Alipay payment %s: %s, set as error' % (self.reference, status)
            _logger.info(error)
            res.update(state='error', state_message=error)
            return self.write(res)
