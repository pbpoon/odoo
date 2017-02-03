# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError
from odoo.sql_db import TestCursor
from odoo.tools import config
from odoo.tools.misc import find_in_path
from odoo.http import request
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError

import base64
import logging
import lxml.html
import os
import re
import subprocess
import tempfile
import time

from lxml import etree
from contextlib import closing
from distutils.version import LooseVersion
from functools import partial
from pyPdf import PdfFileWriter, PdfFileReader
from reportlab.graphics.barcode import createBarcodeDrawing


# A lock occurs when the user wants to print a report having multiple barcode while the server is
# started in threaded-mode. The reason is that reportlab has to build a cache of the T1 fonts
# before rendering a barcode (done in a C extension) and this part is not thread safe. We attempt
# here to init the T1 fonts cache at the start-up of Odoo so that rendering of barcode in multiple
# thread does not lock the server.
try:
    createBarcodeDrawing('Code128', value='foo', format='png', width=100, height=100, humanReadable=1).asString('png')
except Exception:
    pass

#--------------------------------------------------------------------------
# Helpers
#--------------------------------------------------------------------------
_logger = logging.getLogger(__name__)


def _get_wkhtmltopdf_bin():
    return find_in_path('wkhtmltopdf')

#--------------------------------------------------------------------------
# Check the presence of Wkhtmltopdf and return its version at Odoo start-up
#--------------------------------------------------------------------------
wkhtmltopdf_state = 'install'
try:
    process = subprocess.Popen(
        [_get_wkhtmltopdf_bin(), '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
except (OSError, IOError):
    _logger.info('You need Wkhtmltopdf to print a pdf version of the reports.')
else:
    _logger.info('Will use the Wkhtmltopdf binary at %s' % _get_wkhtmltopdf_bin())
    out, err = process.communicate()
    match = re.search('([0-9.]+)', out)
    if match:
        version = match.group(0)
        if LooseVersion(version) < LooseVersion('0.12.0'):
            _logger.info('Upgrade Wkhtmltopdf to (at least) 0.12.0')
            wkhtmltopdf_state = 'upgrade'
        else:
            wkhtmltopdf_state = 'ok'

        if config['workers'] == 1:
            _logger.info('You need to start Odoo with at least two workers to print a pdf version of the reports.')
            wkhtmltopdf_state = 'workers'
    else:
        _logger.info('Wkhtmltopdf seems to be broken.')
        wkhtmltopdf_state = 'broken'


def drop_temporary_files(temporary_files):
    for temporary_file in temporary_files:
        try:
            os.unlink(temporary_file)
        except (OSError, IOError):
            _logger.error('Error when trying to remove file %s' % temporary_file)


def _build_wkhtmltopdf_args(paperformat, specific_paperformat_args=None):
    """Build arguments understandable by wkhtmltopdf from a report.paperformat record.

    :paperformat: report.paperformat record
    :specific_paperformat_args: a dict containing prioritized wkhtmltopdf arguments
    :returns: list of string representing the wkhtmltopdf arguments
    """
    command_args = []
    if paperformat.format and paperformat.format != 'custom':
        command_args.extend(['--page-size', paperformat.format])

    if paperformat.page_height and paperformat.page_width and paperformat.format == 'custom':
        command_args.extend(['--page-width', str(paperformat.page_width) + 'mm'])
        command_args.extend(['--page-height', str(paperformat.page_height) + 'mm'])

    if specific_paperformat_args and specific_paperformat_args.get('data-report-margin-top'):
        command_args.extend(['--margin-top', str(specific_paperformat_args['data-report-margin-top'])])
    else:
        command_args.extend(['--margin-top', str(paperformat.margin_top)])

    if specific_paperformat_args and specific_paperformat_args.get('data-report-dpi'):
        command_args.extend(['--dpi', str(specific_paperformat_args['data-report-dpi'])])
    elif paperformat.dpi:
        if os.name == 'nt' and int(paperformat.dpi) <= 95:
            _logger.info("Generating PDF on Windows platform require DPI >= 96. Using 96 instead.")
            command_args.extend(['--dpi', '96'])
        else:
            command_args.extend(['--dpi', str(paperformat.dpi)])

    if specific_paperformat_args and specific_paperformat_args.get('data-report-header-spacing'):
        command_args.extend(['--header-spacing', str(specific_paperformat_args['data-report-header-spacing'])])
    elif paperformat.header_spacing:
        command_args.extend(['--header-spacing', str(paperformat.header_spacing)])

    command_args.extend(['--margin-left', str(paperformat.margin_left)])
    command_args.extend(['--margin-bottom', str(paperformat.margin_bottom)])
    command_args.extend(['--margin-right', str(paperformat.margin_right)])
    if paperformat.orientation:
        command_args.extend(['--orientation', str(paperformat.orientation)])
    if paperformat.header_line:
        command_args.extend(['--header-line'])

    return command_args


def run_wkhtmltopdf(headers, footers, bodies, landscape, paperformat, spec_paperformat_args=None, set_viewport_size=False):
    """Execute wkhtmltopdf as a subprocess in order to convert html given in input into a pdf
    document.

    :param header: list of string containing the headers
    :param footer: list of string containing the footers
    :param bodies: list of string containing the reports
    :param landscape: boolean to force the pdf to be rendered under a landscape format
    :param paperformat: ir.actions.report.paperformat to generate the wkhtmltopf arguments
    :param specific_paperformat_args: dict of prioritized paperformat arguments
    :returns: paths to documents_paths
    """

    command_args = []
    if set_viewport_size:
        command_args.extend(['--viewport-size', landscape and '1024x1280' or '1280x1024'])

    # Passing the cookie to wkhtmltopdf in order to resolve internal links.
    try:
        if request:
            command_args.extend(['--cookie', 'session_id', request.session.sid])
    except AttributeError:
        pass

    # Wkhtmltopdf arguments
    command_args.extend(['--quiet'])  # Less verbose error messages
    if paperformat:
        # Convert the paperformat record into arguments
        command_args.extend(_build_wkhtmltopdf_args(paperformat, spec_paperformat_args))

    # Force the landscape orientation if necessary
    if landscape and '--orientation' in command_args:
        command_args_copy = list(command_args)
        for index, elem in enumerate(command_args_copy):
            if elem == '--orientation':
                del command_args[index]
                del command_args[index]
                command_args.extend(['--orientation', 'landscape'])
    elif landscape and '--orientation' not in command_args:
        command_args.extend(['--orientation', 'landscape'])

    # Execute WKhtmltopdf
    documents_paths = []
    temporary_files = []

    for index, reporthtml in enumerate(bodies):
        local_command_args = []
        pdfreport_fd, pdfreport_path = tempfile.mkstemp(suffix='.pdf', prefix='report.tmp.')

        # Wkhtmltopdf handles header/footer as separate pages. Create them if necessary.
        if headers:
            head_file_fd, head_file_path = tempfile.mkstemp(suffix='.html', prefix='report.header.tmp.')
            temporary_files.append(head_file_path)
            with closing(os.fdopen(head_file_fd, 'w')) as head_file:
                head_file.write(headers[index])
            local_command_args.extend(['--header-html', head_file_path])
        if footers:
            foot_file_fd, foot_file_path = tempfile.mkstemp(suffix='.html', prefix='report.footer.tmp.')
            temporary_files.append(foot_file_path)
            with closing(os.fdopen(foot_file_fd, 'w')) as foot_file:
                foot_file.write(footers[index])
            local_command_args.extend(['--footer-html', foot_file_path])

        # Body stuff
        content_file_fd, content_file_path = tempfile.mkstemp(suffix='.html', prefix='report.body.tmp.')
        temporary_files.append(content_file_path)
        with closing(os.fdopen(content_file_fd, 'w')) as content_file:
            content_file.write(reporthtml)

        try:
            wkhtmltopdf = [_get_wkhtmltopdf_bin()] + command_args + local_command_args
            wkhtmltopdf += [content_file_path] + [pdfreport_path]
            process = subprocess.Popen(wkhtmltopdf, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = process.communicate()

            if process.returncode not in [0, 1]:
                raise UserError(_('Wkhtmltopdf failed (error code: %s). '
                                  'Message: %s') % (str(process.returncode), err))

            documents_paths.append(pdfreport_path)
        except:
            raise

    drop_temporary_files(temporary_files)

    return documents_paths


class Report(models.Model):
    _name = "report"
    _description = "Report"

    public_user = None

    #--------------------------------------------------------------------------
    # Extension of ir_ui_view.render with arguments frequently used in reports
    #--------------------------------------------------------------------------

    @api.multi
    def render(self, template, values=None):
        """Allow to render a QWeb template python-side. This function returns the 'ir.ui.view'
        render but embellish it with some variables/methods used in reports.

        :param values: additionnal methods/variables used in the rendering
        :returns: html representation of the template
        """
        if values is None:
            values = {}

        context = dict(self.env.context, inherit_branding=True)  # Tell QWeb to brand the generated html

        # Browse the user instead of using the sudo self.env.user
        user = self.env['res.users'].browse(self.env.uid)
        website = None
        if request and hasattr(request, 'website'):
            if request.website is not None:
                website = request.website
                context = dict(context, translatable=context.get('lang') != request.website.default_lang_code)

        view_obj = self.env['ir.ui.view'].with_context(context)
        values.update(
            time=time,
            context_timestamp=lambda t: fields.Datetime.context_timestamp(self.with_context(tz=user.tz), t),
            editable=True,
            user=user,
            res_company=user.company_id,
            website=website,
            web_base_url=self.env['ir.config_parameter'].sudo().get_param('web.base.url', default='')
        )
        return view_obj.render_template(template, values)

    #--------------------------------------------------------------------------
    # Helpers report methods
    #--------------------------------------------------------------------------
    @api.model
    def _check_wkhtmltopdf(self):
        return wkhtmltopdf_state

    @api.model
    def _get_report_from_name(self, report_name):
        """Get the first record of ir.actions.report.xml having the ``report_name`` as value for
        the field report_name.
        """
        report_obj = self.env['ir.actions.report.xml']
        qwebtypes = ['qweb-pdf', 'qweb-html']
        conditions = [('report_type', 'in', qwebtypes), ('report_name', '=', report_name)]
        context = self.env['res.users'].context_get()
        return report_obj.with_context(context).search(conditions, limit=1)

    @api.model
    def _merge_pdf(self, documents):
        """Merge PDF files into one.

        :param documents: list of path of pdf files
        :returns: path of the merged pdf
        """
        writer = PdfFileWriter()
        streams = []  # We have to close the streams *after* PdfFilWriter's call to write()
        for document in documents:
            pdfreport = file(document, 'rb')
            streams.append(pdfreport)
            reader = PdfFileReader(pdfreport)
            for page in range(0, reader.getNumPages()):
                writer.addPage(reader.getPage(page))

        merged_file_fd, merged_file_path = tempfile.mkstemp(suffix='.html', prefix='report.merged.tmp.')
        with closing(os.fdopen(merged_file_fd, 'w')) as merged_file:
            writer.write(merged_file)

        for stream in streams:
            stream.close()

        return merged_file_path

    @api.model
    def _prepare_html(self, html, docids=None, model=None):
        # Preparing the minimal html pages
        headerhtml = []
        contenthtml = []
        footerhtml = []
        sorted_docids = []
        specific_paperformat_args = {}
        irconfig_obj = self.env['ir.config_parameter'].sudo()
        base_url = irconfig_obj.get_param('report.url') or irconfig_obj.get_param('web.base.url')

        # Minimal page renderer
        View = self.env['ir.ui.view']
        render_minimal = partial(View.render_template, 'report.minimal_layout')

        # The received html report must be simplified. We convert it in a xml tree
        # in order to extract headers, bodies and footers.
        try:
            root = lxml.html.fromstring(html)
            match_klass = "//div[contains(concat(' ', normalize-space(@class), ' '), ' {} ')]"

            for node in root.xpath(match_klass.format('header')):
                body = lxml.html.tostring(node)
                header = render_minimal(dict(subst=True, body=body, base_url=base_url))
                headerhtml.append(header)

            for node in root.xpath(match_klass.format('footer')):
                body = lxml.html.tostring(node)
                footer = render_minimal(dict(subst=True, body=body, base_url=base_url))
                footerhtml.append(footer)

            for node in root.xpath(match_klass.format('article')):
                # Previously, we marked some reports to be saved in attachment via their ids, so we
                # must set a relation between report ids and report's content. We use the QWeb
                # branding in order to do so: searching after a node having a data-oe-model
                # attribute with the value of the current report model and read its oe-id attribute
                if docids and len(docids) == 1:
                    sorted_docids.append(docids[0])
                else:
                    oemodelnode = node.find(".//*[@data-oe-model='%s']" % model)
                    if oemodelnode is not None:
                        reportid = oemodelnode.get('data-oe-id')
                        if reportid:
                            sorted_docids.append(int(reportid))
                    else:
                        sorted_docids.append(False)

                # Extract the body
                body = lxml.html.tostring(node)
                content = render_minimal(dict(subst=False, body=body, base_url=base_url))
                contenthtml.append(content)

            # Get paperformat arguments set in the root html tag. They are prioritized over
            # paperformat-record arguments.
            for attribute in root.items():
                if attribute[0].startswith('data-report-'):
                    specific_paperformat_args[attribute[0]] = attribute[1]

        except etree.XMLSyntaxError:
            contenthtml.append(html)

        return headerhtml, contenthtml, footerhtml, sorted_docids, specific_paperformat_args

    @api.model
    def create_attachment(self, attachment_vals):
        """Hook that can be used to modify the attachment before or directly after its creation.
        For example, for e-invoicing in some countries, the attachment must contains additional
        things like embedded files, signature of the company, etc.

        :param attachment_vals: The attachment values.
        :return: The attachment_id created or None in case of AccessError.
        """
        try:
            attachment_id = self.env['ir.attachment'].create(attachment_vals)
        except AccessError:
            _logger.info("Cannot save PDF report %r as attachment", attachment_vals['name'])
            return None
        else:
            _logger.info('The PDF document %s is now saved in the database', attachment_vals['name'])
        return attachment_id

    #--------------------------------------------------------------------------
    # Main report methods
    #--------------------------------------------------------------------------
    @api.model
    def barcode(self, barcode_type, value, width=600, height=100, humanreadable=0):
        if barcode_type == 'UPCA' and len(value) in (11, 12, 13):
            barcode_type = 'EAN13'
            if len(value) in (11, 12):
                value = '0%s' % value
        try:
            width, height, humanreadable = int(width), int(height), bool(int(humanreadable))
            barcode = createBarcodeDrawing(
                barcode_type, value=value, format='png', width=width, height=height,
                humanReadable=humanreadable
            )
            return barcode.asString('png')
        except (ValueError, AttributeError):
            raise ValueError("Cannot convert into barcode.")

    @api.model
    def get_html(self, docids, report_name, data=None):
        """This method generates and returns html version of a report.
        """
        # If the report is using a custom model to render its html, we must use it.
        # Otherwise, fallback on the generic html rendering.
        report_model_name = 'report.%s' % report_name
        report_model = self.env.get(report_model_name)

        if report_model is not None:
            return report_model.render_html(docids, data=data)
        else:
            report = self._get_report_from_name(report_name)
            docs = self.env[report.model].browse(docids)
            docargs = {
                'doc_ids': docids,
                'doc_model': report.model,
                'docs': docs,
            }
            return self.render(report.report_name, docargs)

    @api.model
    def get_pdf(self, docids, report_name, html=None, data=None, attachment_name=None):
        """This method generates and returns pdf version of a report.

        :param docids: The record ids.
        :param report_name: The report name.
        :param html:
        :param data:
        :param report_as_attachment:
        :return:
        """

        if self._check_wkhtmltopdf() == 'install':
            # wkhtmltopdf is not installed
            # the call should be catched before (cf /report/check_wkhtmltopdf) but
            # if get_pdf is called manually (email template), the check could be
            # bypassed
            raise UserError(_("Unable to find Wkhtmltopdf on this system. The PDF can not be created."))

        # As the assets are generated during the same transaction as the rendering of the
        # templates calling them, there is a scenario where the assets are unreachable: when
        # you make a request to read the assets while the transaction creating them is not done.
        # Indeed, when you make an asset request, the controller has to read the `ir.attachment`
        # table.
        # This scenario happens when you want to print a PDF report for the first time, as the
        # assets are not in cache and must be generated. To workaround this issue, we manually
        # commit the writes in the `ir.attachment` table. It is done thanks to a key in the context.
        context = dict(self.env.context)
        if not config['test_enable']:
            context['commit_assetsbundle'] = True

        # Disable the debug mode in the PDF rendering in order to not split the assets bundle
        # into separated files to load. This is done because of an issue in wkhtmltopdf
        # failing to load the CSS/Javascript resources in time.
        # Without this, the header/footer of the reports randomly disapear
        # because the resources files are not loaded in time.
        # https://github.com/wkhtmltopdf/wkhtmltopdf/issues/2083
        context['debug'] = False

        # Get the html
        if html is None:
            html = self.with_context(context).get_html(docids, report_name, data=data)

        # The test cursor prevents the use of another environnment while the current
        # transaction is not finished, leading to a deadlock when the report requests
        # an asset bundle during the execution of test scenarios. In this case, return
        # the html version.
        if isinstance(self.env.cr, TestCursor):
            return html

        html = html.decode('utf-8')  # Ensure the current document is utf-8 encoded.

        # Get the ir.actions.report.xml record we are working on.
        report = self._get_report_from_name(report_name)

        # Get the paperformat associated to the report, otherwise fallback on the company one.
        if not report.paperformat_id:
            user = self.env['res.users'].browse(self.env.uid)  # Rebrowse to avoid sudo user from self.env.user
            paperformat = user.company_id.paperformat_id
        else:
            paperformat = report.paperformat_id

        # Preparing the minimal html pages
        headerhtml, contenthtml, footerhtml, sorted_docids, specific_paperformat_args = self.with_context(context)._prepare_html(html, docids, report.model)

        # Run wkhtmltopdf process
        documents_paths = run_wkhtmltopdf(
            headerhtml, footerhtml, contenthtml, context.get('landscape'),
            paperformat, specific_paperformat_args,
            context.get('set_viewport_size'),
        )

        # Look for attachment_name both in the context and parameter
        attachment_name = attachment_name or context.get('attachment_name')

        # Save in attachment
        if attachment_name:
            model = report.model
            for it, docid in enumerate(sorted_docids):
                if not docid:
                    continue
                with open(documents_paths[it], 'rb') as pdfdocument:
                    datas = base64.encodestring(pdfdocument.read())
                attachment_vals = {
                    'name': attachment_name,
                    'datas': datas,
                    'datas_fname': attachment_name,
                    'res_model': model,
                    'res_id': docid,
                }
                self.create_attachment(attachment_vals)

        temporary_file = []
        if len(documents_paths) > 1:
            documents_paths = [self._merge_pdf(documents_paths)]
            temporary_file.append(documents_paths[0])

        with open(documents_paths[0], 'rb') as pdfdocument:
            content = pdfdocument.read()

        drop_temporary_files(temporary_file)

        return content

    @api.noguess
    def get_action(self, docids, report_name, data=None, config=True):
        """Return an action of type ir.actions.report.xml.

        :param docids: id/ids/browserecord of the records to print (if not used, pass an empty list)
        :param report_name: Name of the template to generate an action for
        """
        if (self.env.uid == SUPERUSER_ID) and ((not self.env.user.company_id.external_report_layout) or (not self.env.user.company_id.logo)) and config:
            template = self.env.ref('report.view_company_report_form', False)
            return {
                'name': _('Choose Your Report Layout'),
                'type': 'ir.actions.act_window',
                'context': {'default_report_name': report_name},
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': self.env.user.company_id.id,
                'res_model': 'res.company',
                'views': [(template.id, 'form')],
                'view_id': template.id,
                'target': 'new',
            }

        context = self.env.context
        if docids:
            if isinstance(docids, models.Model):
                active_ids = docids.ids
            elif isinstance(docids, int):
                active_ids = [docids]
            elif isinstance(docids, list):
                active_ids = docids
            context = dict(self.env.context, active_ids=active_ids)

        report = self.env['ir.actions.report.xml'].with_context(context).search([('report_name', '=', report_name)])
        if not report:
            raise UserError(_("Bad Report Reference") + _("This report is not loaded into the database: %s.") % report_name)

        return {
            'context': context,
            'data': data,
            'type': 'ir.actions.report.xml',
            'report_name': report.report_name,
            'report_type': report.report_type,
            'report_file': report.report_file,
            'name': report.name,
        }
