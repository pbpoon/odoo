odoo.define('im_livechat.chat_discuss', function (require) {
"use strict";

require('mail.chat_discuss');
var chatManager = require('mail.chatManager');
var core = require('web.core');

core.action_registry.get('mail.chat.instant_messaging').include({
    _renderSidebar: function (options) {
        // Override to sort livechat channels by last message's date
        var channel_partition = _.partition(options.channels, function (channel) {
            return channel.type === 'livechat';
        });
        channel_partition[0].sort(function (c1, c2) {
            return c2.last_message_date.diff(c1.last_message_date);
        });
        options.channels = channel_partition[0].concat(channel_partition[1]);
        return this._super(options);
    },
});

chatManager.bus.on('new_message', null, function (msg) {
    _.each(msg.channel_ids, function (channel_id) {
        var channel = chatManager.getChannel(channel_id);
        if (channel) {
            channel.last_message_date = msg.date; // update the last message's date of the channel
        }
    });
});

});