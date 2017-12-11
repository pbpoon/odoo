odoo.define('mass_mailing.tour', function(require) {
"use strict";

var core = require('web.core');
var tour = require('web_tour.tour');

var _t = core._t;

tour.register('mass_mailing_tour', {
    url: "/web",
}, [tour.STEPS.MENU_MORE, {
    trigger: '.o_app[data-menu-xmlid="mass_mailing.mass_mailing_menu_root"], .oe_menu_toggler[data-menu-xmlid="mass_mailing.mass_mailing_menu_root"]',
    content: _t('Let\'s design your first mailing!'),
    position: 'bottom',
}]);

});
