odoo.define('website_quote.website_quote', function (require) {
'use strict';

require('web.dom_ready');
var ajax = require('web.ajax');
var config = require('web.config');
var Widget = require('web.Widget');

if(!$('.o_website_quote').length) {
    return $.Deferred().reject("DOM doesn't contain '.o_website_quote'");
}

    // Add to SO button
    var UpdateLineButton = Widget.extend({
        events: {
            'click' : 'onClick',
        },
        onClick: function(ev){
            ev.preventDefault();
            var self = this;
            var href = this.$el.attr("href");
            var order_id = href.match(/order_id=([0-9]+)/);
            var line_id = href.match(/update_line\/([0-9]+)/);
            var token = href.match(/token=(.*)/);
            ajax.jsonRpc("/quote/update_line", 'call', {
                'line_id': line_id[1],
                'order_id': parseInt(order_id[1]),
                'token': token[1],
                'remove': self.$el.is('[href*="remove"]'),
                'unlink': self.$el.is('[href*="unlink"]')
            }).then(function (data) {
                if(!data){
                    window.location.reload();
                }
                self.$el.parents('.input-group:first').find('.js_quantity').val(data[0]);
                $('[data-id="total_amount"]>span').html(data[1]);
            });
            return false;
        },
    });

    var update_button_list = [];
    $('a.js_update_line_json').each(function( index ) {
        var button = new UpdateLineButton();
        button.setElement($(this)).start();
        update_button_list.push(button);
    });
});
