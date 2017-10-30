odoo.define('website_sale.product_catalog_options', function (require) {
'use strict';

var core = require('web.core');
var Dialog = require('web.Dialog');
var options = require('web_editor.snippets.options');
var rpc = require('web.rpc');

var _t = core._t;
var QWeb = core.qweb;

options.registry.product_catalog = options.Class.extend({
    /**
     * @override
     */
    start: function () {
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Options
    //--------------------------------------------------------------------------

    /**
     * Select catalog type.
     *
     * @see this.selectClass for parameters
     */
    catalogType: function (previewMode, value) {
        this.$target.attr('data-catalog-type', value);
    },
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _setActive: function () {
        this.$el.find('li[data-catalog-type]').removeClass('active')
            .filter('li[data-catalog-type=' + this.$target.attr('data-catalog-type') + ']').addClass('active');
    },
});
});