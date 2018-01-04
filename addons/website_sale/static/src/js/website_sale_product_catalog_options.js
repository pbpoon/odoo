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
    xmlDependencies: ['/website_sale/static/src/xml/website_sale_product_catalog.xml'],
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
        var self = this;
        if (value != 'reorder_products') {
            this.$target.attr('data-sortby', value);
            this._renderProducts();
        }
        if (value == 'reorder_products') {
            var $dialog = new Dialog(null, {
                title: _t('Drag a product to re-arrange display sequence'),
                $content: $(QWeb.render('website_sale.reorderProducts', {'products': this.productCatalog.products})),
                buttons: [
                    {text: _t('Save'), classes: 'btn-primary', close: true, click: function () {
                        self.$target.attr('data-sortby', value);
                        var productIds = _.map($dialog.$content.find('ul.reorder_products > li'), function(el) {
                            return $(el).attr('data-menu-id');
                        });
                        self.$target.attr('data-productIds',productIds);
                        self.$target.attr('data-sortby', value);
                        self._renderProducts();
                    }},
                    {text: _t('Discard'), close: true}
                ]
            }).open();
            $dialog.opened().then(function () {
                $dialog.$el.find('.reorder_products').sortable();
                $dialog.$el.find('.reorder_products').disableSelection();
            });
        }
    },
    /**
     * Products selection.
     *
     * @see this.selectClass for parameters
     */
    productSelection: function (previewMode, value, $li) {
        this.$el.find('[data-product-selection]').removeClass('active');
        $li.toggleClass('active',this.$target.attr('data-product-selection') === value);
        switch (value) {
            case 'all':
                this.$target.attr('data-product-selection', value);
                this.$target.attr('data-product-domain', []);
                this._renderProducts();
                break;
            case 'category':
                this._categorySelection();
                break;
            case 'manual':
                this.manualSelection();
                break;
        }

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
     * Select products catagory wise.
     *
     * @private
     */
    _categorySelection: function () {
        var self = this;
        rpc.query({
            model: 'product.public.category',
            method: 'search_read',
            fields: ['id', 'name'],
        }).then(function (result) {
            var dialog = new Dialog(null, {
                title: _t('Select Product Category'),
                $content: $(QWeb.render('website_sale.catagorySelection')),
                buttons: [
                    {text: _t('Save'), classes: 'btn-primary', close: true, click: function () {
                        var categoryID = dialog.$content.find('[name="selection"]').val();
                        self.$target.attr('data-catagory-id', categoryID);
                        self.$target.attr('data-product-selection', 'category');
                        self._renderProducts();
                    }},
                    {text: _t('Discard'), close: true}
                ]
            });
            dialog.$content.find('[name="selection"]').val(self.$target.attr('data-catagory-id'));
            dialog.$content.find('[name="selection"]').select2({
                width: '70%',
                data: _.map(result, function (r) {
                    return {'id': r.id, 'text': r.name};
                }),
            });
            dialog.$content.find('[name="selection"]').change(function () {
                rpc.query({
                    model: 'product.template',
                    method: 'search_count',
                    args:[[['public_categ_ids', 'child_of', [parseInt($(this).val())]], ['website_published', '=', true]]]
                }).then(function (result) {
                    dialog.$('.alert-info').toggleClass('hidden', result !== 0);
                    dialog.$footer.find('.btn-primary').prop('disabled', result === 0);
                });
            });
            dialog.open();
        });
    },
    /**
     * Select products manually.
     *
     * @private
     */
    manualSelection: function () {
        var self = this;
        rpc.query({
            model: 'product.template',
            method: 'search_read',
            fields: ['id', 'name'],
            domain: [['website_published', '=', true]]
        }).then(function (result) {
            var dialog = new Dialog(null, {
                title: _t('Select Product Manually'),
                $content: $(QWeb.render('website_sale.manualSelection')),
                buttons: [
                    {text: _t('Save'), classes: 'btn-primary', close: true, click: function () {
                        var productIDS = dialog.$content.find('[name="selection"]').val().split(',');
                        self.$target.attr('data-productIds', dialog.$content.find('[name="selection"]').val());
                        self.$target.attr('data-product-selection', 'manual');
                        self._renderProducts();
                    }},
                    {text: _t('Discard'), close: true}
                ]
            });
            dialog.$content.find('[name="selection"]').val(self.productCatalog._getProductIds());
            dialog.$content.find('[name="selection"]').select2({
                width: '100%',
                multiple: true,
                maximumSelectionSize: self.productCatalog._getLimit(),
                data: _.map(result, function (r) {
                    return {'id': r.id, 'text': r.name};
                }),
            }).change(function () {
                dialog.$footer.find('.btn-primary').prop('disabled', dialog.$content.find('[name="selection"]').val() == "");
            });
            dialog.open();
        });
    },
    /**
     * @override
     */
    _setActive: function () {
        this._super.apply(this, arguments);
        var mode = this.$target.attr('data-catalog-type');
        this.$el.find('[data-grid-size]:first').parent().parent().toggle(mode === 'grid');
        this.$el.find('li[data-catalog-type]').removeClass('active')
            .filter('li[data-catalog-type=' + this.$target.attr('data-catalog-type') + ']').addClass('active');
        this.$el.find('li[data-sortby]').removeClass('active')
            .filter('li[data-sortby=' + this.$target.attr('data-sortby') + ']').addClass('active');
        this.$el.find('li[data-product-selection]').removeClass('active')
            .filter('li[data-product-selection=' + this.$target.attr('data-product-selection') + ']').addClass('active');
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
            if (self.$target.attr('data-sortby') != 'reorder_products') {
                self.$target.attr('data-productIds', self.productCatalog._getProductIds());
            }
            self.trigger_up('cover_update');
        });
    },
});
});
