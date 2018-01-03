odoo.define('o_portal_sidebar.o_portal_sidebar', function (require) {
'use strict';

    require('web.dom_ready');
    var config = require('web.config');
    var time = require('web.time');
    var Widget = require("web.Widget");
    var ajax = require('web.ajax');

    if(!$('.o_portal_sidebar').length) {
        return $.Deferred().reject("DOM doesn't contain '.o_portal_sidebar'");
    }

    $('timeago.timeago').each(function(index, el){
            var datetime = $(el).attr('datetime'),
                datetime_obj = time.str_to_date(datetime),
                // if presentation 365 days, 24 hours, 60 min, 60 second, 1000 millis old(one week)
                // then return fix formate string else timeago
                display_str = "";
            if (datetime_obj && datetime_obj.getTime() - new Date().getTime() > 365 * 24 * 60 * 60 * 1000) {
                display_str = datetime_obj.toDateString();
            } else {
                display_str = moment(datetime_obj).fromNow();
            }
            $(el).text(display_str);
    });   

    // Nav Menu ScrollSpy
    var NavigationSpyMenu = Widget.extend({
        start: function(watched_selector){
            this.authorized_text_tag = ['em', 'b', 'i', 'u'];
            this.spy_watched = $(watched_selector);
            this.generateMenu();
        },
        generateMenu: function(){
            var self = this;
            // reset ids
            $("[id^=quote_header_], [id^=quote_]", this.spy_watched).attr("id", "");
            // generate the new spy menu
            var last_li = false;
            var last_ul = null;
            _.each(this.spy_watched.find("h1, h2"), function(el){
                var id, text;
                switch (el.tagName.toLowerCase()) {
                    case "h1":
                        id = self.setElementId('quote_header_', el);
                        text = self.extractText($(el));
                        if (!text) {
                            break;
                        }
                        last_li = $("<li>").append($('<a href="#'+id+'"/>').text(text)).appendTo(self.$el);
                        last_ul = false;
                        break;
                    case "h2":
                        id = self.setElementId('quote_', el);
                        text = self.extractText($(el));
                        if (!text) {
                            break;
                        }
                        if (last_li) {
                            if (!last_ul) {
                                last_ul = $("<ul class='nav'>").appendTo(last_li);
                            }
                            $("<li>").append($('<a href="#'+id+'"/>').text(text)).appendTo(last_ul);
                        }
                        break;
                }
            });
        },
        setElementId: function(prefix, $el){
            var id = _.uniqueId(prefix);
            this.spy_watched.find($el).attr('id', id);
            return id;
        },
        extractText: function($node){
            var self = this;
            var raw_text = [];
            _.each($node.contents(), function(el){
                var current = $(el);
                if($.trim(current.text())){
                    var tagName = current.prop("tagName");
                    if(_.isUndefined(tagName) || (!_.isUndefined(tagName) && _.contains(self.authorized_text_tag, tagName.toLowerCase()))){
                        raw_text.push($.trim(current.text()));
                    }
                }
            });
            return raw_text.join(' ');
        }
    });

    var nav_menu = new NavigationSpyMenu();
    nav_menu.setElement($('[data-id="quote_sidebar"]'));
    nav_menu.start($('body[data-target=".navspy"]'));

    var $bs_sidebar = $(".o_portal_sidebar .bs-sidebar");
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