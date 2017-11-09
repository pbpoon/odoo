odoo.define('report.bom_cost_structure', function (require) {
'use strict';
var core = require('web.core');
var ReportAction = core.action_registry.get('report.client_action');


var BomReportAction = ReportAction.extend({
    init: function (parent, action, options){
        var option = _.extend({}, options, {
                report_url: '/report/html/' + action.report_name + '/' + action.context.active_id,
                report_name: action.report_name,
                report_file: action.report_file,
                data: action.data,
                context: action.context,
                name: action.name,
                display_name: action.display_name,
            });
        this._super(parent, action, option);
    },
    _make_table_expandable: function () {
        var $body = $(this.iframe).contents().find('html body');
        var $trExpandable = $body.find('.tr_expandable');
        $trExpandable.on('click', function (ev, collapse){
            var id = $(this).data('id');
            var $caret =  $(this).find('.td-caret');
            var $table = $(this).closest('table');
            var downDirection =  $caret.hasClass('fa-caret-down') ? false : true;
            if (downDirection && !collapse) {
                $table .find("tr[data-parent-id="+ id +"]").removeClass('hidden');
                $caret.removeClass('fa-caret-right').addClass('fa-caret-down');
            } else {
                $table.find("tr[data-parent-id="+ id +"]").addClass('hidden');
                $table.find("tr[data-parent-id="+ id +"].tr_expandable").trigger('click', true);
                $caret.removeClass('fa-caret-down').addClass('fa-caret-right');
            }
        });
    },
    _on_iframe_loaded: function () {
        this._super.apply(this, arguments);
        this._make_table_expandable();
    },
});

core.action_registry.add('mrp_bom_cost_structure_report', BomReportAction);
return BomReportAction;

});