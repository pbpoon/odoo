odoo.define('o_has_portal_frontend.o_has_portal_frontend', function (require) {
'use strict';

require('web.dom_ready');
var config = require('web.config');
var time = require('web.time');

if(!$('.o_has_portal_frontend').length) {
    return $.Deferred().reject("DOM doesn't contain '.o_has_portal_frontend'");
}

$('timeago.timeago').each(function(index, el){
        var datetime = $(el).attr('datetime'),
            datetime_obj = time.str_to_date(datetime),
            // if presentation 7 days, 24 hours, 60 min, 60 second, 1000 millis old(one week)
            // then return fix formate string else timeago
            display_str = "";
        if (datetime_obj && datetime_obj.getTime() - new Date().getTime() > 365 * 24 * 60 * 60 * 1000) {
            display_str = datetime_obj.toDateString();
        } else {
            display_str = moment(datetime_obj).fromNow();
        }
        $(el).text(display_str);
})

var $bs_sidebar = $(".o_has_portal_frontend .bs-sidebar");
    $(window).on('resize', _.throttle(adapt_sidebar_position, 200, {leading: false}));
    adapt_sidebar_position();

    function adapt_sidebar_position() {
        $bs_sidebar.css({
            position: "relative",
            width: "",
        });
        if (config.device.size_class >= config.device.SIZES.MD) {
            $bs_sidebar.css({
                position: "fixed",
                width: $bs_sidebar.outerWidth(),
            });
        }
    }

    $bs_sidebar.affix({
        offset: {
            top: 0,
            bottom: $('body').height() - $('#wrapwrap').outerHeight() + $("footer").outerHeight(),
        },
    });
});