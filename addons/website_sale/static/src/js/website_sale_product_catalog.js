odoo.define('website_sale.product_catalog', function (require) {
'use strict';

var base = require('web_editor.base');
var core = require('web.core');
var rpc = require('web.rpc');
var Widget = require('web.Widget');
var config = require('web.config');
var utils = require('web.utils');
var QWeb = core.qweb;
var ProductCatalog = Widget.extend({
    template: 'website_sale.product_catalog',
    xmlDependencies: [
        '/website_sale/static/src/xml/website_sale_product_catalog.xml',
        '/website_rating/static/src/xml/website_mail.xml'
    ],
    /**
     * Initialize all options which are need to render widget.
     * @constructor
     * @override
     * @param {jQuery} $target
     */
    init: function ($target) {
        this._super.apply(this, arguments);
        this.$target = $target;
        this.catalogType = this.$target.attr('data-catalog-type');
        this.is_rating = false;
        this.size = this.catalogType === 'grid' ? 12/this.$target.attr('data-x') : 12/(config.device.size_class + 1);
        this.carouselId = _.uniqueId('product-carousel_');
    },
    /**
     * Fetch product details.
     *
     * @override
     * @returns {Deferred}
     */
    willStart: function () {
        var self = this;
        var def = rpc.query({
            route: '/get_product_catalog_details',
            params: {
                'domain': this._getDomain(),
                'sortby': this._getSortby(),
                'limit': this._getLimit(),
            }
        }).then(function (result) {
            if (self.$target.attr('data-sortby') === 'reorder_products') {
                self._reOrderingProducts(result);
            }
            self.products = result.products;
            self.is_rating = result.is_rating_active;
        });
        return $.when(this._super.apply(this, arguments), def);
    },

    /**
     * If rating option is enable then display rating.
     *
     * @override
     * @returns {Deferred}
     */
    start: function () {
        if (this.is_rating) {
            this._renderRating();
        }
        return this._super.apply(this, arguments);
    },
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------
     /**
     * formating currency for the website sale display
     *
     * @private
     * @param {float|false} value that should be formatted.
     * @param {string} currency_symbol.
     * @param {string} position should be either before or after.
     * @param {integer} currency_decimal_places the number of digits that should be used,
     *   instead of the default digits precision in the field.
     * @returns {string} Returns a string representing a float and currency symbol.
     */
    _formatCurrencyValue: function (value, currency_symbol, position, currency_decimal_places) {
        var l10n = core._t.database.parameters;
        value = _.str.sprintf('%.' + currency_decimal_places + 'f', value || 0).split('.');
        value[0] = utils.insert_thousand_seps(value[0]);
        value = value.join(l10n.decimal_point);
        if (position === "after") {
            value += currency_symbol;
        } else {
            value = currency_symbol + value;
        }
        return value;
    },
    /**
     * formating description for the website sale display
     *
     * @private
     * @param {string} get description.
     * @returns {string} Contains string with replace '\n' to '<br>'.
     */
    _formatDescriptionValue: function (description_sale) {
        return description_sale.split("\n").join("<br>");
    },
    /**
     * Get product ids.
     *
     * @private
     * @returns {Array} Contains product ids.
     */
    _getProductIds: function () {
        return _.map(this.$target.find('.product-item'), function (el) {
            return $(el).data('product-id');
        });
    },
    /**
     * It is responsible to decide how many  numbers of products
     * are display in each slide of carousel.
     *
     * @private
     * @returns {Array} Contains arrays of products.
     */
    _getProducts: function () {
        var lists = _.groupBy(this.products, function (product, index) {
            return Math.floor(index/(config.device.size_class + 1));
        });
        return _.toArray(lists);
    },
    _getDomain: function () {
        var domain = [];
        var selection = this.$target.attr('data-product-selection');
        switch (selection) {
            case 'all':
                domain = [];
                break;
            case 'category':
                domain = ['public_categ_ids', 'child_of', [parseInt(this.$target.attr('data-catagory-id'))]];
                break;
            case 'manual':
                var productIds = this.$target.attr('data-productIds').split(',').map(Number);
                domain = ['id', 'in', productIds];
                break;
        }
        return domain;
    },
    _getSortby: function () {
        var sortBy = {
            'price_asc': {name: 'list_price', asc: true},
            'price_desc': {name: 'list_price', asc: false},
            'name_asc': {name: 'name', asc: true},
            'name_desc': {name: 'name', asc: false},
            'newest_to_oldest': {name: 'create_date', asc: true},
            'oldest_to_newest': {name: 'create_date', asc: false},
            'reorder_products':{}
        };
        return utils.into(sortBy, this.$target.attr('data-sortby'));
    },
    _getLimit: function () {
        // data-carousel is not available in snippet [TO-DO]
        return this.catalogType === 'grid' ? this.$target.attr('data-x') * this.$target.attr('data-y') :  this.$target.attr('data-carousel');
    },

    /**
     * Display rating for each product.
     *
     * @private
     */
    _renderRating: function () {
        var self = this;
        this.$target.find('.product-item').each(function () {
            var productDetails = _.findWhere(self.products, {id: $(this).data('product-id')});
            if (productDetails.product_variant_count >= 1) {
                $(QWeb.render('website_rating.rating_stars_static', {val: productDetails.rating.avg})).appendTo($(this).find('.rating'));
            }
        });
    },
    /**
     * Re-ordering products while selecting re-ordering products option.
     *
     * @private
     * @param {Object} contain products detail
     */
    _reOrderingProducts: function (products) {
        var reorderIDs = this.$target.attr('data-productIds').split(',').map(Number);
        products['products'] = _.sortBy(products.products, function (product) {
            return _.indexOf(reorderIDs, product.id);
        });
        return products;
    },


});
base.ready().then(function () {
    if ($('.s_product_catalog').length) {
        $('.s_product_catalog').each(function () {
            var productCatalog = new ProductCatalog($(this));
            $(this).find('.product_grid').remove();
            productCatalog.appendTo($(this).find('.container'));
        });
    }
});
return {
    ProductCatalog: ProductCatalog,
};
});
