odoo.define('portal.share_document', function (require) {
'use strict';

var data_manager = require('web.data_manager');
var SystrayMenu = require('web.SystrayMenu');
var ViewManager = require('web.ViewManager');
var WebClient = require('web.WebClient');
var Widget = require('web.Widget');


var ProtalShareDoc = Widget.extend({
    events: {
        "click": "_onClick",
    },
    template: 'portal.sharing_icon',
    xmlDependencies: ['/portal/static/src/xml/portal_share_document.xml'],

    /**
     * @override
     */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.update();
        });
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Update the system tray icon for share document, based on view type hides/shows icon
     * Show Share Icon only if share_icon is True in action context
     */
    update: function (tag, descriptor, widget) {
        switch (tag) {
            case 'action':
                if (!(widget instanceof ViewManager)) {
                    var self = this;
                    this._active_view = null;
                    this._view_manager = null;
                    this.getSession().user_has_group('base.group_erp_manager').then(
                        function(has_group) {
                        if (has_group) {
                            if (widget && widget.action && widget.action.context.share_icon) {
                                self.share_action = widget.action.context.share_action ? widget.action.context.share_action : 'portal.mail_share_document_action';
                                self.$el.removeClass('o_hidden');
                            }
                        }
                    });
                    break;
                }
                this._view_manager = widget;
                widget.on('switch_mode', this, function () {
                    this.update('view', null, widget);
                });
            case 'view':
                this._active_view = widget.active_view;
                this.share_action = widget.env.context.share_action ? widget.env.context.share_action : 'portal.mail_share_document_action';
                if (widget.env.context.share_icon && widget.active_view && widget.active_view.type === 'form') {
                    this.$el.removeClass('o_hidden');
                } else {
                    this.$el.addClass('o_hidden');
                }
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /*
     * Opens Share document wizard, loads action and call that action with additional context(active_id and active_model)
     */
    _onClick: function (ev) {
        ev.preventDefault();
        var self = this;
        var additional_context = {};
        if (this._active_view) {
            var renderer = this._active_view.controller.renderer;
            var res_id = renderer.state.data.id;
            additional_context = {
                'active_id': res_id,
                'active_model': this._view_manager.dataset.model,
            };
        }
        return data_manager.load_action(this.share_action, additional_context).then(function (result) {
            return self.do_action(result, {
                additional_context: additional_context,
                on_close: function () {
                    if (self._active_view) {
                        self._active_view.controller.reload();
                    }
                },
            });
        });
    },
});

WebClient.include({
    current_action_updated: function (action) {
        this._super.apply(this, arguments);
        var action_descr = action && action.action_descr;
        var action_widget = action && action.widget;
        var portal_share_doc = _.find(this.systray_menu.widgets, function (item) {return item instanceof ProtalShareDoc; });
        portal_share_doc.update('action', action_descr, action_widget);
    },
    instanciate_menu_widgets: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.systray_menu = self.menu.systray_menu;
        });
    },
});

SystrayMenu.Items.push(ProtalShareDoc);

});
