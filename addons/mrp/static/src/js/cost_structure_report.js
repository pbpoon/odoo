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
    _on_iframe_loaded: function () {
        this._super.apply(this, arguments);
        var $body = $(this.iframe).contents().find('html body');
    },
});

core.action_registry.add('mrp_bom_cost_structure_report', BomReportAction);
return BomReportAction;

});