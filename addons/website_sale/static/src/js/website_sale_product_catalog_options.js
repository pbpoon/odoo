odoo.define('website_sale.product_catalog_options', function (require) {
'use strict';

var core = require('web.core');
var Dialog = require('web.Dialog');
var options = require('web_editor.snippets.options');
var productCatalog = require('website_sale.product_catalog');
var rpc = require('web.rpc');

var _t = core._t;
var QWeb = core.qweb;

options.registry.product_catalog = options.Class.extend({
    /**
     * @override
     */
    start: function () {
        this._setGrid();
        this._bindGridEvents();
        this._renderProducts();
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
        this._renderProducts();
    },
    /**
     * Set Grid size.
     */
    gridSize: function () {
        this._setGrid();
        this._renderProducts();
    },
    sortby: function (previewMode, value, $li) {
        this.$target.attr('data-sortby', value);
        this._renderProducts();
    },
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------
    /**
     * Bind events of grid option.
     *
     * @private
     */
    _bindGridEvents: function () {
        var self = this;
        this.$el.on('mouseenter', 'ul[name="size"] table', function (event) {
            $(event.currentTarget).addClass('oe_hover');
        });
        this.$el.on('mouseleave', 'ul[name="size"] table', function (event) {
            $(event.currentTarget).removeClass('oe_hover');
        });
        this.$el.on('mouseover', 'ul[name="size"] td', function (event) {
            var $td = $(event.currentTarget);
            var $table = $td.closest('table');
            var x = $td.index() + 1;
            var y = $td.parent().index() + 1;

            var tr = [];
            for (var yi = 0; yi < y; yi++) {
                tr.push('tr:eq(' + yi + ')');
            }
            var $select_tr = $table.find(tr.join(','));
            var td = [];
            for (var xi = 0; xi < x; xi++) {
                td.push('td:eq(' + xi + ')');
            }
            var $select_td = $select_tr.find(td.join(','));
            $table.find('td').removeClass('select');
            $select_td.addClass('select');
        });
    },
    /**
     * @override
     */
    _setActive: function () {
        var mode = this.$target.attr('data-catalog-type');
        this.$el.find('[data-grid-size]:first').parent().parent().toggle(mode === 'grid');
        this.$el.find('li[data-catalog-type]').removeClass('active')
            .filter('li[data-catalog-type=' + this.$target.attr('data-catalog-type') + ']').addClass('active');
    },

    /**
     * Set selected size on grid option.
     *
     * @private
     */
    _setGrid: function () {
        var $td = this.$el.find('.select:last');
        if ($td.length) {
            this.$target.attr('data-x', $td.index() + 1);
            this.$target.attr('data-y', $td.parent().index() + 1);
        }
        var x = this.$target.attr('data-x');
        var y = this.$target.attr('data-y');
        var $grid = this.$el.find('ul[name="size"]');
        var $selected = $grid.find('tr:eq(0) td:lt(' + x + ')');
        if (y >= 2) {
            $selected = $selected.add($grid.find('tr:eq(1) td:lt(' + x + ')'));
        }
        if (y >= 3) {
            $selected = $selected.add($grid.find('tr:eq(2) td:lt(' + x + ')'));
        }
        if (y >= 4) {
            $selected = $selected.add($grid.find('tr:eq(3) td:lt(' + x + ')'));
        }
        $grid.find('td').removeClass('selected');
        $selected.addClass('selected');
    },
    /**
     * Render products by initialize 'productCatalog' widget.
     *
     * @private
     */
    _renderProducts: function () {
        var self = this;
        this.productCatalog = new productCatalog.ProductCatalog(this.$target);
        this.$target.find('.product_grid').remove();
        this.productCatalog.appendTo(this.$target.find('.container')).then(function () {
            self.trigger_up('cover_update');
        });
    },
});
});
