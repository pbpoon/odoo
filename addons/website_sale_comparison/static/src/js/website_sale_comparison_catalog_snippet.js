odoo.define('website_sale_comparison.product_catalog', function (require) {
'use strict';

var ProductComparison = require('website_sale_comparison.comparison');
var ProductCatalog = require('website_sale.product_catalog');
var WebsiteSaleUtils = require('website_sale.utils');

var Comparison = new ProductComparison.ProductComparison();

ProductCatalog.ProductCatalog.include({
    xmlDependencies: ProductCatalog.ProductCatalog.prototype.xmlDependencies.concat(
        ['/website_sale_comparison/static/src/xml/website_sale_comparison_product_catalog.xml']
    ),
    events: _.extend({}, ProductCatalog.ProductCatalog.prototype.events, {
        'click .add_to_compare': '_onClickAddToCompare',
    }),
    /**
     * Append the comparison block append to body.
     *
     * @override
     */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function() {
            Comparison.appendTo('body');
        });
    },
    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Add product into compare list.
     *
     * @private
     * @param {MouseEvent} event
     */
    _onClickAddToCompare: function (event) {
        event.preventDefault();
        var variantID = $(event.currentTarget).data('product-variant-id');
        if (Comparison.comparelist_product_ids.length < Comparison.product_compare_limit) {
            Comparison.add_new_products(variantID);
            WebsiteSaleUtils.animate_clone($('#comparelist .o_product_panel_header'), $(event.currentTarget).parents('[class^="col-md"]'), -50, 10);
        } else {
            Comparison.$el.find('.o_comparelist_limit_warning').show();
            Comparison.show_panel(true);
        }
    },
});

});
