odoo.define('website_sale_wishlist.product_catalog', function (require) {
'use strict';

var core = require('web.core');
var ProductWishlist = require('website_sale_wishlist.wishlist');
var ProductCatalog = require('website_sale.product_catalog');
var WebsiteSaleUtils = require('website_sale.utils');

var Wishlist = new ProductWishlist.ProductWishlist();

ProductCatalog.ProductCatalog.include({
    xmlDependencies: ProductCatalog.ProductCatalog.prototype.xmlDependencies.concat(
        ['/website_sale_wishlist/static/src/xml/website_sale_product_catalog.xml']
    ),
    events: _.extend({}, ProductCatalog.ProductCatalog.prototype.events, {
        'click .add_to_wishlist': '_onClickAddToWishlist',
    }),

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Update wishlist.
     *
     * @override
     * @returns {Deferred}
     */
    willStart: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            if (!odoo.session_info.is_website_user) {
                $.get('/shop/wishlist', {'count': 1}).then(function (res) {
                    _.each(JSON.parse(res), function (val) {
                        self.$target.find('.add_to_wishlist[data-product-product-id="' + val + '"]').addClass('disabled').attr('disabled', 'disabled');
                        Wishlist.update_wishlist_view();
                    });
                });
            }
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Add product into wishlist.
     *
     * @private
     * @param {MouseEvent} event
     */
    _onClickAddToWishlist: function (event) {
        Wishlist.add_new_products($(event.currentTarget), event).then(function () {
            WebsiteSaleUtils.animate_clone($('#my_wish'), $(event.currentTarget).parents('[class^="col-"]'), 25, 40);
            $(event.currentTarget).prop('disabled', true).addClass('disabled');
        });
    },
});

});
