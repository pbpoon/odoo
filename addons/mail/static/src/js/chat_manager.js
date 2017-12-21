odoo.define('mail.ChatManager', function (require) {
"use strict";

var bus = require('bus.bus').bus;
var utils = require('mail.utils');
var config = require('web.config');
var Bus = require('web.Bus');
var core = require('web.core');
var session = require('web.session');
var time = require('web.time');
var web_client = require('web.web_client');
var Class = require('web.Class');
var Mixins = require('web.mixins');
var ServicesMixin = require('web.ServicesMixin');

var _t = core._t;
var _lt = core._lt;

var LIMIT = 25;
var PREVIEW_MSG_MAX_SIZE = 350;  // optimal for native english speakers
var ODOOBOT_ID = "ODOOBOT";

var ChatManager =  Class.extend(Mixins.EventDispatcherMixin, ServicesMixin, {

    /**
     * @override
     */
    init: function (parent) {
        var self = this;

        this.messages = [];
        this.channels = [];
        this.channelsPreviewDef;
        this.channelDefs = {};
        this.unreadConversationCounter = 0;
        this.emojis = [];
        this.emojiSubstitutions = {};
        this.emojiUnicodes = {};
        this.needactionCounter = 0;
        this.starredCounter = 0;
        this.mentionPartnerSuggestions = [];
        this.cannedResponses = [];
        this.commands = [];
        this.discussMenuId;
        this.globalUnreadCounter = 0;
        this.pinnedDmPartners = [];  // partner_ids we have a pinned DM with
        this.clientActionOpen = false;

        Mixins.EventDispatcherMixin.init.call(this);

        this.bus = new Bus();
        this.bus.on('client_action_open', null, function (open) {
            self.clientActionOpen = open;
        });

        bus.on('notification', this, this._onNotification);

        // Global unread counter and notifications
        bus.on("window_focus", null, function () {
            self.globalUnreadCounter = 0;
            web_client.set_title_part("_chat");
        });

        this.channelSeen = _.throttle(function (channel) {
            return self._rpc({
                    model: 'mail.channel',
                    method: 'channel_seen',
                    args: [[channel.id]],
                }, {
                    shadow: true
                });
        }, 3000);

        this.setParent(parent);
    },
    /**
     * @override
     */
    start: function () {
        this.isReady = session.is_bound.then(function (){
                var context = _.extend({isMobile: config.device.isMobile}, session.user_context);
                return session.rpc('/mail/init_messaging', {context: context});
            }).then(this._onMailClientAction.bind(this));

        this.addChannel({
            id: "channel_inbox",
            name: _lt("Inbox"),
            type: "static",
        }, { displayNeedactions: true });

        this.addChannel({
            id: "channel_starred",
            name: _lt("Starred"),
            type: "static"
        });
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * [description]
     *
     * @param  {Object} data [description]
     * @param  {string|integer} data.id id of channel or 'channel_inbox', 'channel_starred', ...
     * @param  {string|Object} data.name name of channel, e.g. 'general'
     * @param  {string} data.type type of channel, e.g. 'static'
     * @param  {string} [data.channel_type] [description]
     * @param  {boolean} [data.group_based_subscription] [description]
     * @param  {boolean} [data.is_minimized] [description]
     * @param  {boolean} [data.mass_mailing] [description]
     * @param  {integer} [data.message_needaction_counter] [description]
     * @param  {integer} [data.message_unread_counter] [description]
     * @param  {string} [data.public] e.g. 'groups'
     * @param  {integer|false} [data.seen_message_id] [description]
     * @param  {string} [data.state] e.g. 'open'
     * @param  {string} [data.uuid] [description]
     * @param  {Object|integer} [options=undefined] [description]
     * @param  {boolean} [options.displayNeedactions]
     * @return {Object|string} channel
     */
    addChannel: function (data, options) {
        options = typeof options === "object" ? options : {};
        var channel = this.getChannel(data.id);
        if (channel) {
            if (channel.is_folded !== (data.state === "folded")) {
                channel.is_folded = (data.state === "folded");
                this.bus.trigger("channel_toggle_fold", channel);
            }
        } else {
            channel = this._makeChannel(data, options);
            this.channels.push(channel);
            if (data.last_message) {
                channel.last_message = this._addMessage(data.last_message);
            }
            // In case of a static channel (Inbox, Starred), the name is translated thanks to _lt
            // (lazy translate). In this case, channel.name is an object, not a string.
            this.channels = _.sortBy(this.channels, function (channel) {
                return _.isString(channel.name) ? channel.name.toLowerCase() : '';
            });
            if (!options.silent) {
                this.bus.trigger("new_channel", channel);
            }
            if (channel.is_detached) {
                this.bus.trigger("open_chat", channel);
            }
        }
        return channel;
    },
    /**
     * [description]
     * Called when fetching messages from cache
     *
     * @param  {Object} channel [description]
     * @param  {boolean} channel.all_history_loaded [description]
     * @param  {Array} domain  [description]
     * @return {Object}
     */
    allHistoryLoaded: function (channel, domain) {
        return this._getChannelCache(channel, domain).all_history_loaded;
    },
    /**
     * [description]
     * @param  {[type]} channelID [description]
     */
    closeChatSession: function (channelID) {
        var channel = this.getChannel(channelID);
        this._rpc({
                model: 'mail.channel',
                method: 'channel_fold',
                kwargs: {uuid : channel.uuid, state : 'closed'},
            }, {shadow: true});
    },
    /**
     * [description]
     *
     * @param  {[type]} name [description]
     * @param  {[type]} type [description]
     * @return {[type]}      [description]
     */
    createChannel: function (name, type) {
        var method = type === "dm" ? "channel_get" : "channel_create";
        var args = type === "dm" ? [[name]] : [name, type];
        var context = _.extend({isMobile: config.device.isMobile}, session.user_context);
        return this._rpc({
                model: 'mail.channel',
                method: method,
                args: args,
                kwargs: {context: context},
            })
            .then(this.addChannel.bind(this));
    },
    /**
     * [description]
     *
     * @param  {[type]} channel [description]
     * @return {Deferred}
     */
    detachChannel: function (channel) {
        return this._rpc({
                model: 'mail.channel',
                method: 'channel_minimize',
                args: [channel.uuid, true],
            }, {
                shadow: true,
            });
    },

    /**
     * [description]
     *
     * @param  {[type]} channelID [description]
     * @param  {[type]} folded    [description]
     * @return {Deferred}
     */
    foldChannel: function (channelID, folded) {
        var args = {
            uuid: this.getChannel(channelID).uuid,
        };
        if (_.isBoolean(folded)) {
            args.state = folded ? 'folded' : 'open';
        }
        return this._rpc({
                model: 'mail.channel',
                method: 'channel_fold',
                kwargs: args,
            }, {shadow: true});
    },
    /**
     * [description]
     *
     * @return {Array}
     */
    getCannedResponses: function () {
        return this.cannedResponses;
    },
    /**
     * [description]
     *
     * @param  {string|integer} id e.g. 'channel_inbox', 'channel_starred'
     * @return {Object|undefined} channel
     */
    getChannel: function (id) {
        return _.findWhere(this.channels, {id: id});
    },
    /**
     * [description]
     *
     * @return {Object[]} list of channels
     */
    getChannels: function () {
        return _.clone(this.channels);
    },
    /**
     * [description]
     *
     * @param  {[type]} channels [description]
     * @return {[type]}          [description]
     */
    getChannelsPreview: function (channels) {
        var self = this;
        var channelsPreview = _.map(channels, function (channel) {
            var info;
            if (channel.channel_ids && _.contains(channel.channel_ids,"channel_inbox")) {
                // map inbox(mail_message) data with existing channel/chat template
                info = _.pick(channel,
                    'id', 'body', 'avatar_src', 'res_id', 'model', 'module_icon',
                    'subject','date', 'record_name', 'status', 'displayed_author',
                    'email_from', 'unread_counter');
                info.last_message = {
                    body: info.body,
                    date: info.date,
                    displayed_author: info.displayed_author || info.email_from,
                };
                info.name = info.record_name || info.subject || info.displayed_author;
                info.image_src = info.module_icon || info.avatar_src;
                info.message_id = info.id;
                info.id = 'channel_inbox';
                return info;
            }
            info = _.pick(channel, 'id', 'is_chat', 'name', 'status', 'unread_counter');
            info.last_message = channel.last_message || _.last(channel.cache['[]'].messages);
            if (!info.is_chat) {
                info.image_src = '/web/image/mail.channel/'+channel.id+'/image_small';
            } else if (channel.directPartnerID) {
                info.image_src = '/web/image/res.partner/'+channel.directPartnerID+'/image_small';
            } else {
                info.image_src = '/mail/static/src/img/smiley/avatar.jpg';
            }
            return info;
        });
        var missingChannels = _.where(channelsPreview, {last_message: undefined});
        if (!this.channelsPreviewDef) {
            if (missingChannels.length) {
                var missingChannelIDs = _.pluck(missingChannels, 'id');
                this.channelsPreviewDef = this._rpc({
                        model: 'mail.channel',
                        method: 'channel_fetch_preview',
                        args: [missingChannelIDs],
                    }, {
                        shadow: true,
                    });
            } else {
                this.channelsPreviewDef = $.when();
            }
        }
        return this.channelsPreviewDef.then(function (channels) {
            _.each(missingChannels, function (channelPreview) {
                var channel = _.findWhere(channels, {id: channelPreview.id});
                if (channel) {
                    channelPreview.last_message = self._addMessage(channel.last_message);
                }
            });
            // sort channels: 1. unread, 2. chat, 3. date of last msg
            channelsPreview.sort(function (c1, c2) {
                return Math.min(1, c2.unread_counter) - Math.min(1, c1.unread_counter) ||
                       c2.is_chat - c1.is_chat ||
                       !!c2.last_message - !!c1.last_message ||
                       (c2.last_message && c2.last_message.date.diff(c1.last_message.date));
            });

            // generate last message preview (inline message body and compute date to display)
            _.each(channelsPreview, function (channel) {
                if (channel.last_message) {
                    channel.last_message_preview = self._getMessageBodyPreview(channel.last_message.body);
                    channel.last_message_date = channel.last_message.date.fromNow();
                }
            });
            return channelsPreview;
        });
    },
    /**
     * [description]
     * called when clicking on arrow next to comment
     *
     * @param  {Object} channel
     * @return {Deferred} [description]
     */
    getCommands: function (channel) {
        return _.filter(this.commands, function (command) {
            return !command.channel_types || _.contains(command.channel_types, channel.server_type);
        });
    },
    /**
     * [description]
     *
     * @return {[type]} [description]
     */
    getDiscussMenuID: function () {
        return this.discussMenuId;
    },
    /**
     * [description]
     *
     * @param  {[type]} partnerID [description]
     * @return {[type]}           [description]
     */
    getDmFromPartnerID: function (partnerID) {
        return _.findWhere(this.channels, {directPartnerID: partnerID});
    },
    /**
     * [description]
     *
     * @return {[type]} [description]
     */
    getEmojis: function () {
        return this.emojis;
    },
    /**
     * [description]
     *
     * @param  {[type]} channel [description]
     * @return {[type]}         [description]
     */
    getLastSeenMessage: function (channel) {
        if (channel.last_seen_message_id) {
            var messages = channel.cache['[]'].messages;
            var msg = _.findWhere(messages, {id: channel.last_seen_message_id});
            if (msg) {
                var i = _.sortedIndex(messages, msg, 'id') + 1;
                while (i < messages.length &&
                    (messages[i].is_author || messages[i].is_system_notification)) {
                        msg = messages[i];
                        i++;
                }
                return msg;
            }
        }
    },
    /**
     * [description]
     *
     * @param  {[type]} channel [description]
     * @return {[type]}         [description]
     */
    getMentionPartnerSuggestions: function (channel) {
        var self = this;
        if (!channel) {
            return this.mentionPartnerSuggestions;
        }
        if (!channel.membersDeferred) {
            channel.membersDeferred = this._rpc({
                    model: 'mail.channel',
                    method: 'channel_fetch_listeners',
                    args: [channel.uuid],
                }, {
                    shadow: true
                })
                .then(function (members) {
                    var suggestions = [];
                    _.each(self.mentionPartnerSuggestions, function (partners) {
                        suggestions.push(_.filter(partners, function (partner) {
                            return !_.findWhere(members, { id: partner.id });
                        }));
                    });

                    return [members];
                });
        }
        return channel.membersDeferred;
    },
    /**
     * [description]
     *
     * @param  {[type]} id [description]
     * @return {[type]}    [description]
     */
    getMessage: function (id) {
        return _.findWhere(this.messages, {id: id});
    },
    /**
     * [description]
     *
     * @param  {[type]} options [description]
     * @return {[type]}         [description]
     */
    getMessages: function (options) {
        var channel;
        var self = this;

        if ('channelID' in options && options.load_more) {
            // get channel messages, force load_more
            channel = this.getChannel(options.channelID);
            return this._fetchFromChannel(channel, {domain: options.domain || {}, loadMore: true});
        }
        if ('channelID' in options) {
            // channel message, check in cache first
            channel = this.getChannel(options.channelID);
            var channelCache = this._getChannelCache(channel, options.domain);
            if (channelCache.loaded) {
                return $.when(channelCache.messages);
            } else {
                return this._fetchFromChannel(channel, {domain: options.domain});
            }
        }
        if ('ids' in options) {
            // get messages from their ids (chatter is the main use case)
            return this._fetchDocumentMessages(options.ids, options).then(function (result) {
                self.markAsRead(options.ids);
                return result;
            });
        }
        if ('model' in options && 'res_id' in options) {
            // get messages for a chatter, when it doesn't know the ids (use
            // case is when using the full composer)
            var domain = [['model', '=', options.model], ['res_id', '=', options.res_id]];
            this._rpc({
                    model: 'mail.message',
                    method: 'message_fetch',
                    args: [domain],
                    kwargs: {limit: 30},
                })
                .then(function (msgs) {
                    return _.map(msgs, self._addMessage.bind(self));
                });
        }
    },
    /**
     * [description]
     *
     * @return {[type]} [description]
     */
    getNeedactionCounter: function () {
        return this.needactionCounter;
    },
    /**
     * [description]
     *
     * @return {[type]} [description]
     */
    getStarredCounter: function () {
        return this.starredCounter;
    },
    /**
     * [description]
     *
     * @return {[type]} [description]
     */
    getUnreadConversationCounter: function () {
        return this.unreadConversationCounter;
    },
    /**
     * [description]
     *
     * @param  {[type]} channelID [description]
     * @param  {[type]} options   [description]
     * @return {[type]}           [description]
     */
    joinChannel: function (channelID, options) {
        var self = this;
        if (channelID in this.channelDefs) {
            // prevents concurrent calls to channel_join_and_get_info
            return this.channelDefs[channelID];
        }
        var channel = this.getChannel(channelID);
        if (channel) {
            // channel already joined
            this.channelDefs[channelID] = $.when(channel);
        } else {
            this.channelDefs[channelID] = this._rpc({
                    model: 'mail.channel',
                    method: 'channel_join_and_get_info',
                    args: [[channelID]],
                })
                .then(function (result) {
                    return self.addChannel(result, options);
                });
        }
        return this.channelDefs[channelID];
    },
    /**
     * [description]
     *
     * @param  {[type]} channel [description]
     * @param  {[type]} domain  [description]
     * @return {[type]}         [description]
     */
    markAllAsRead: function (channel, domain) {
        if ((channel.id === "channel_inbox" && this.needactionCounter) ||
            (channel && channel.needactionCounter)) {
            return this._rpc({
                    model: 'mail.message',
                    method: 'mark_all_as_read',
                    kwargs: {
                        channel_ids: channel.id !== "channel_inbox" ? [channel.id] : [],
                        domain: domain,
                    },
                });
        }
        return $.when();
    },
    /**
     * [description]
     *
     * @param  {[type]} msgIDs [description]
     * @return {[type]}        [description]
     */
    markAsRead: function (msgIDs) {
        var self = this;
        var ids = _.filter(msgIDs, function (id) {
            var message = _.findWhere(self.messages, {id: id});
            // If too many messages, not all are fetched, and some might not be found
            return !message || message.is_needaction;
        });
        if (ids.length) {
            return this._rpc({
                    model: 'mail.message',
                    method: 'set_message_done',
                    args: [ids],
                });
        } else {
            return $.when();
        }
    },
    /**
     * [description]
     *
     * @param  {[type]} channel [description]
     * @return {[type]}         [description]
     */
    markChannelAsSeen: function (channel) {
        if (channel.unread_counter > 0 && channel.type !== 'static') {
            this._updateChannelUnreadCounter(channel, 0);
            this.channelSeen(channel);
        }
    },
    /**
     * [description]
     *
     * @param  {[type]} partnerID [description]
     * @return {[type]}           [description]
     */
    openAndDetachDm: function (partnerID) {
        return this._rpc({
                model: 'mail.channel',
                method: 'channel_get_and_minimize',
                args: [[partnerID]],
            })
            .then(this.addChannel.bind(this));
    },
    /**
     * [description]
     *
     * @param  {[type]} channel [description]
     * @return {[type]}         [description]
     */
    openChannel: function (channel) {
        this.bus.trigger(this.clientActionOpen ? 'open_channel' : 'detach_channel', channel);
    },
    /**
     * [description]
     *
     * @param  {[type]} data    [description]
     * @param  {[type]} options [description]
     * @return {Deferred}         [description]
     */
    postMessage: function (data, options) {
        var self = this;
        options = options || {};

        // This message will be received from the mail composer as html content subtype
        // but the urls will not be linkified. If the mail composer takes the responsibility
        // to linkify the urls we end up with double linkification a bit everywhere.
        // Ideally we want to keep the content as text internally and only make html
        // enrichment at display time but the current design makes this quite hard to do.
        var body = utils.parse_and_transform(_.str.trim(data.content), utils.add_link);

        var msg = {
            partner_ids: data.partner_ids,
            body: body,
            attachment_ids: data.attachment_ids,
        };

        // Replace emojis by their unicode character
        _.each(_.keys(this.emojiUnicodes), function (key) {
            var escapedKey = String(key).replace(/([.*+?=^!:${}()|[\]/\\])/g, '\\$1');
            var regexp = new RegExp("(\\s|^)(" + escapedKey + ")(?=\\s|$)", "g");
            msg.body = msg.body.replace(regexp, "$1" + self.emojiUnicodes[key]);
        });
        if ('subject' in data) {
            msg.subject = data.subject;
        }
        if ('channelID' in options) {
            // post a message in a channel or execute a command
            return this._rpc({
                    model: 'mail.channel',
                    method: data.command ? 'execute_command' : 'message_post',
                    args: [options.channelID],
                    kwargs: _.extend(msg, {
                        message_type: 'comment',
                        content_subtype: 'html',
                        subtype: 'mail.mt_comment',
                        command: data.command,
                    }),
                });
        }
        if ('model' in options && 'res_id' in options) {
            // post a message in a chatter
            _.extend(msg, {
                content_subtype: data.content_subtype,
                context: data.context,
                message_type: data.message_type,
                subtype: data.subtype,
                subtype_id: data.subtype_id,
            });

            return this._rpc({
                    model: options.model,
                    method: 'message_post',
                    args: [options.res_id],
                    kwargs: msg,
                })
                .then(function (msg_id) {
                    return self._rpc({
                            model: 'mail.message',
                            method: 'message_format',
                            args: [msg_id],
                        })
                        .then(function (msgs) {
                            msgs[0].model = options.model;
                            msgs[0].res_id = options.res_id;
                            self._addMessage(msgs[0]);
                        });
                });
        }
        return $.when();
    },
    /**
     * Special redirection handling for given model and id
     *
     * If the model is res.partner, and there is a user associated with this
     * partner which isn't the current user, open the DM with this user.
     * Otherwhise, open the record's form view, if this is not the current user's.
     *
     * @param  {[type]} resModel              [description]
     * @param  {[type]} resID                 [description]
     * @param  {[type]} dmRedirectionCallback [description]
     * @return {[type]}                       [description]
     */
    redirect: function (resModel, resID, dmRedirectionCallback) {
        var self = this;
        var redirectToDocument = function (resModel, resID, viewID) {
            web_client.do_action({
                type:'ir.actions.act_window',
                view_type: 'form',
                view_mode: 'form',
                res_model: resModel,
                views: [[viewID || false, 'form']],
                res_id: resID,
            });
        };
        if (resModel === "res.partner") {
            var domain = [["partner_id", "=", resID]];
            this._rpc({
                    model: 'res.users',
                    method: 'search',
                    args: [domain],
                })
                .then(function (userIDs) {
                    if (userIDs.length && userIDs[0] !== session.uid && dmRedirectionCallback) {
                        self.createChannel(resID, 'dm').then(dmRedirectionCallback);
                    } else {
                        redirectToDocument(resModel, resID);
                    }
                });
        } else {
            this._rpc({
                    model: resModel,
                    method: 'get_formview_id',
                    args: [[resID], session.user_context],
                })
                .then(function (viewID) {
                    redirectToDocument(resModel, resID, viewID);
                });
        }
    },
    /**
     * [description]
     *
     * @param  {[type]} model [description]
     * @return {[type]}       [description]
     */
    removeChatterMessages: function (model) {
        this.messages = _.reject(this.messages, function (message) {
            return message.channel_ids.length === 0 && message.model === model;
        });
    },
    /**
     * [description]
     *
     * @param  {[type]} searchVal [description]
     * @param  {[type]} limit     [description]
     * @return {[type]}           [description]
     */
    searchPartner: function (searchVal, limit) {
        var def = $.Deferred();
        var values = [];
        // search among prefetched partners
        var searchRegexp = new RegExp(_.str.escapeRegExp(utils.unaccent(searchVal)), 'i');
        _.each(this.mentionPartnerSuggestions, function (partners) {
            if (values.length < limit) {
                values = values.concat(_.filter(partners, function (partner) {
                    return session.partner_id !== partner.id && searchRegexp.test(partner.name);
                })).splice(0, limit);
            }
        });
        if (!values.length) {
            // extend the research to all users
            def = this._rpc({
                    model: 'res.partner',
                    method: 'im_search',
                    args: [searchVal, limit || 20],
                }, {
                    shadow: true,
                });
        } else {
            def = $.when(values);
        }
        return def.then(function (values) {
            var autocompleteData = _.map(values, function (value) {
                return { id: value.id, value: value.name, label: value.name };
            });
            return _.sortBy(autocompleteData, 'label');
        });
    },
    /**
     * [description]
     *
     * @param  {[type]} msgID [description]
     * @return {[type]}       [description]
     */
    toggleStarStatus: function (msgID) {
        return this._rpc({
                model: 'mail.message',
                method: 'toggle_message_starred',
                args: [[msgID]],
            });
    },
    /**
     * [description]
     *
     * @return {[type]} [description]
     */
    unstarAll: function () {
        return this._rpc({
                model: 'mail.message',
                method: 'unstar_all',
                args: [[]]
            });
    },
    /**
     * [description]
     *
     * @param  {[type]} channel [description]
     * @return {[type]}         [description]
     */
    unsubscribe: function (channel) {
        if (_.contains(['public', 'private'], channel.type)) {
            return this._rpc({
                    model: 'mail.channel',
                    method: 'action_unfollow',
                    args: [[channel.id]],
                });
        } else {
            return this._rpc({
                    model: 'mail.channel',
                    method: 'channel_pin',
                    args: [channel.uuid, false],
                });
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * [description]
     *
     * @private
     * @param  {[type]} message   [description]
     * @param  {[type]} channelID [description]
     * @return {[type]}           [description]
     */
    _addChannelToMessage: function (message, channelID) {
        message.channel_ids.push(channelID);
        message.channel_ids = _.uniq(message.channel_ids);
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} data    [description]
     * @param  {[type]} options [channel_id, silent]
     * @return {[type]}         [description]
     */
    _addMessage: function (data, options) {
        var self = this;
        options = options || {};
        var msg = _.findWhere(this.messages, { id: data.id });

        if (!msg) {
            msg = this._makeMessage(data);
            // Keep the array ordered by id when inserting the new message
            this.messages.splice(_.sortedIndex(this.messages, msg, 'id'), 0, msg);
            _.each(msg.channel_ids, function (channelID) {
                var channel = self.getChannel(channelID);
                if (channel) {
                    // update the channel's last message (displayed in the channel
                    // preview, in mobile)
                    if (!channel.last_message || msg.id > channel.last_message.id) {
                        channel.last_message = msg;
                    }
                    self._addToCache(msg, []);
                    if (options.domain && options.domain !== []) {
                        self._addToCache(msg, options.domain);
                    }
                    if (channel.hidden) {
                        channel.hidden = false;
                        self.bus.trigger('new_channel', channel);
                    }
                    if (channel.type !== 'static' && !msg.is_author && !msg.is_system_notification) {
                        if (options.increment_unread) {
                            self._updateChannelUnreadCounter(channel, channel.unread_counter+1);
                        }
                        if (channel.is_chat && options.show_notification) {
                            if (!self.clientActionOpen && !config.device.isMobile) {
                                // automatically open chat window
                                self.bus.trigger('open_chat', channel, { passively: true });
                            }
                            var query = {is_displayed: false};
                            self.bus.trigger('anyone_listening', channel, query);
                            self._notifyIncomingMessage(msg, query);
                        }
                    }
                }
            });
            if (!options.silent) {
                this.bus.trigger('new_message', msg);
            }
        } else if (options.domain && options.domain !== []) {
            this._addToCache(msg, options.domain);
        }
        return msg;
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} message [description]
     * @param  {[type]} domain  [description]
     * @return {[type]}         [description]
     */
    _addToCache: function (message, domain) {
        var self = this;
        _.each(message.channel_ids, function (channelID) {
            var channel = self.getChannel(channelID);
            if (channel) {
                var channelCache = self._getChannelCache(channel, domain);
                var index = _.sortedIndex(channelCache.messages, message, 'id');
                if (channelCache.messages[index] !== message) {
                    channelCache.messages.splice(index, 0, message);
                }
            }
        });
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} msgIDs  [description]
     * @param  {[type]} options [description]
     * @return {[type]}         [description]
     */
    _fetchDocumentMessages : function (msgIDs, options) {
        var self = this;
        var loadedMsgs = _.filter(this.messages, function (message) {
            return _.contains(msgIDs, message.id);
        });
        var loadedMsgIDs = _.pluck(loadedMsgs, 'id');

        options = options || {};
        if (options.forceFetch || _.difference(msgIDs.slice(0, LIMIT), loadedMsgIDs).length) {
            var idsToLoad = _.difference(msgIDs, loadedMsgIDs).slice(0, LIMIT);
            return this._rpc({
                    model: 'mail.message',
                    method: 'message_format',
                    args: [idsToLoad],
                    context: session.user_context,
                })
                .then(function (msgs) {
                    var processedMsgs = [];
                    _.each(msgs, function (msg) {
                        processedMsgs.push(self._addMessage(msg, {silent: true}));
                    });
                    return _.sortBy(loadedMsgs.concat(processedMsgs), function (msg) {
                        return msg.id;
                    });
                });
        } else {
            return $.when(loadedMsgs);
        }
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} channel [description]
     * @param  {[type]} options [domain, load_more]
     * @return {[type]}         [description]
     */
    _fetchFromChannel: function (channel, options) {
        var self = this;
        options = options || {};
        var domain =
            (channel.id === "channel_inbox") ? [['needaction', '=', true]] :
            (channel.id === "channel_starred") ? [['starred', '=', true]] :
                                                [['channel_ids', 'in', channel.id]];
        var cache = this._getChannelCache(channel, options.domain);

        if (options.domain) {
            domain = domain.concat(options.domain || []);
        }
        if (options.loadMore) {
            var minMessageId = cache.messages[0].id;
            domain = [['id', '<', minMessageId]].concat(domain);
        }

        return this._rpc({
                model: 'mail.message',
                method: 'message_fetch',
                args: [domain],
                kwargs: {limit: LIMIT, context: session.user_context},
            })
            .then(function (msgs) {
                if (!cache.all_history_loaded) {
                    cache.all_history_loaded =  msgs.length < LIMIT;
                }
                cache.loaded = true;

                _.each(msgs, function (msg) {
                    self._addMessage(msg, {
                        channel_id: channel.id,
                        silent: true,
                        domain: options.domain,
                    });
                });
                var channelCache = self._getChannelCache(channel, options.domain || []);
                return channelCache.messages;
            });
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} channel [description]
     * @param  {[type]} domain  [description]
     * @return {[type]}         [description]
     */
    _getChannelCache: function (channel, domain) {
        var stringifiedDomain = JSON.stringify(domain || []);
        if (!channel.cache[stringifiedDomain]) {
            channel.cache[stringifiedDomain] = {
                all_history_loaded: false,
                loaded: false,
                messages: [],
            };
        }
        return channel.cache[stringifiedDomain];
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} messageBody [description]
     * @return {[type]}             [description]
     */
    _getMessageBodyPreview: function (messageBody) {
        return utils.parse_and_transform(messageBody, utils.inline);
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} channelIDs [description]
     * @return {[type]}            [description]
     */
    _invalidateCaches: function (channelIDs) {
        var self = this;
        _.each(channelIDs, function (channelID) {
            var channel = self.getChannel(channelID);
            if (channel) {
                channel.cache = { '[]': channel.cache['[]']};
            }
        });
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} data    [description]
     * @param  {[type]} options [description]
     * @return {[type]}         [description]
     */
    _makeChannel: function (data, options) {
        var channel = {
            id: data.id,
            name: data.name,
            server_type: data.channel_type,
            type: data.type || data.channel_type,
            all_history_loaded: false,
            uuid: data.uuid,
            is_detached: data.is_minimized,
            is_folded: data.state === "folded",
            autoswitch: 'autoswitch' in options ? options.autoswitch : true,
            hidden: options.hidden,
            display_needactions: options.displayNeedactions,
            mass_mailing: data.mass_mailing,
            group_based_subscription: data.group_based_subscription,
            needactionCounter: data.message_needaction_counter || 0,
            unread_counter: 0,
            last_seen_message_id: data.seen_message_id,
            cache: {'[]': {
                all_history_loaded: false,
                loaded: false,
                messages: [],
            }},
        };
        if (channel.type === "channel") {
            channel.type = data.public !== "private" ? "public" : "private";
        }
        if (_.size(data.direct_partner) > 0) {
            channel.type = "dm";
            channel.name = data.direct_partner[0].name;
            channel.directPartnerID = data.direct_partner[0].id;
            channel.status = data.direct_partner[0].im_status;
            this.pinnedDmPartners.push(channel.directPartnerID);
            bus.update_option('bus_presence_partner_ids', this.pinnedDmPartners);
        } else if ('anonymous_name' in data) {
            channel.name = data.anonymous_name;
        }
        if (data.last_message_date) {
            channel.last_message_date = moment(time.str_to_datetime(data.last_message_date));
        }
        channel.is_chat = !channel.type.match(/^(public|private|static)$/);
        if (data.message_unread_counter) {
            this._updateChannelUnreadCounter(channel, data.message_unread_counter);
        }
        return channel;
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} data [description]
     * @return {Object} msg
     */
    _makeMessage: function (data) {
        var self = this;
        var msg = {
            id: data.id,
            author_id: data.author_id,
            body: data.body || "",
            date: moment(time.str_to_datetime(data.date)),
            message_type: data.message_type,
            subtype_description: data.subtype_description,
            is_author: data.author_id && data.author_id[0] === session.partner_id,
            is_note: data.is_note,
            is_system_notification: (data.message_type === 'notification' && data.model === 'mail.channel')
                || data.info === 'transient_message',
            attachment_ids: data.attachment_ids || [],
            subject: data.subject,
            email_from: data.email_from,
            customer_email_status: data.customer_email_status,
            customer_email_data: data.customer_email_data,
            record_name: data.record_name,
            tracking_value_ids: data.tracking_value_ids,
            channel_ids: data.channel_ids,
            model: data.model,
            res_id: data.res_id,
            url: session.url("/mail/view?message_id=" + data.id),
            module_icon:data.module_icon,
        };

        _.each(_.keys(this.emojiSubstitutions), function (key) {
            var escaped_key = String(key).replace(/([.*+?=^!:${}()|[\]/\\])/g, '\\$1');
            var regexp = new RegExp("(?:^|\\s|<[a-z]*>)(" + escaped_key + ")(?=\\s|$|</[a-z]*>)", "g");
            msg.body = msg.body.replace(regexp, ' <span class="o_mail_emoji">'+self.emojiSubstitutions[key]+'</span> ');
        });

        function propertyDescr(channel) {
            return {
                enumerable: true,
                get: function () {
                    return _.contains(msg.channel_ids, channel);
                },
                set: function (bool) {
                    if (bool) {
                        self._addChannelToMessage(msg, channel);
                    } else {
                        msg.channel_ids = _.without(msg.channel_ids, channel);
                    }
                }
            };
        }

        Object.defineProperties(msg, {
            is_starred: propertyDescr("channel_starred"),
            is_needaction: propertyDescr("channel_inbox"),
        });

        if (_.contains(data.needaction_partner_ids, session.partner_id)) {
            msg.is_needaction = true;
        }
        if (_.contains(data.starred_partner_ids, session.partner_id)) {
            msg.is_starred = true;
        }
        if (msg.model === 'mail.channel') {
            var realChannels = _.without(msg.channel_ids, 'channel_inbox', 'channel_starred');
            var origin = realChannels.length === 1 ? realChannels[0] : undefined;
            var channel = origin && this.getChannel(origin);
            if (channel) {
                msg.origin_id = origin;
                msg.origin_name = channel.name;
            }
        }

        // Compute displayed author name or email
        if ((!msg.author_id || !msg.author_id[0]) && msg.email_from) {
            msg.mailto = msg.email_from;
        } else {
            msg.displayed_author = (msg.author_id === ODOOBOT_ID) && "OdooBot" ||
                                   msg.author_id && msg.author_id[1] ||
                                   msg.email_from || _t('Anonymous');
        }

        // Don't redirect on author clicked of self-posted or OdooBot messages
        msg.author_redirect = !msg.is_author && msg.author_id !== ODOOBOT_ID;

        // Compute the avatar_url
        if (msg.author_id === ODOOBOT_ID) {
            msg.avatar_src = "/mail/static/src/img/odoo_o.png";
        } else if (msg.author_id && msg.author_id[0]) {
            msg.avatar_src = "/web/image/res.partner/" + msg.author_id[0] + "/image_small";
        } else if (msg.message_type === 'email') {
            msg.avatar_src = "/mail/static/src/img/email_icon.png";
        } else {
            msg.avatar_src = "/mail/static/src/img/smiley/avatar.jpg";
        }

        // add anchor tags to urls
        msg.body = utils.parse_and_transform(msg.body, utils.add_link);

        // Compute url of attachments
        _.each(msg.attachment_ids, function (a) {
            a.url = '/web/content/' + a.id + '?download=true';
        });

        // format date to the local only once by message
        // can not be done in preprocess, since it alter the original value
        if (msg.tracking_value_ids && msg.tracking_value_ids.length) {
            var format;
            _.each(msg.tracking_value_ids, function (f) {
                if (f.field_type === 'datetime') {
                    format = 'LLL';
                    if (f.old_value) {
                        f.old_value = moment.utc(f.old_value).local().format(format);
                    }
                    if (f.new_value) {
                        f.new_value = moment.utc(f.new_value).local().format(format);
                    }
                } else if (f.field_type === 'date') {
                    format = 'LL';
                    if (f.old_value) {
                        f.old_value = moment(f.old_value).local().format(format);
                    }
                    if (f.new_value) {
                        f.new_value = moment(f.new_value).local().format(format);
                    }
                }
            });
        }

        return msg;
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} msg     [description]
     * @param  {[type]} options [description]
     */
    _notifyIncomingMessage: function (msg, options) {
        if (bus.is_odoo_focused() && options.is_displayed) {
            // no need to notify
            return;
        }
        var title = _t('New message');
        if (msg.author_id[1]) {
            title = _.escape(msg.author_id[1]);
        }
        var content = utils.parse_and_transform(msg.body, utils.strip_html)
            .substr(0, PREVIEW_MSG_MAX_SIZE);

        if (!bus.is_odoo_focused()) {
            this.globalUnreadCounter++;
            var tabTitle = _.str.sprintf(_t("%d Messages"), this.globalUnreadCounter);
            web_client.set_title_part("_chat", tabTitle);
        }

        utils.send_notification(web_client, title, content);
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} data [description]
     */
    _onActivityUpdateNotification: function (data) {
        this.bus.trigger('activity_updated', data);
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} message [description]
     * @return {[type]}         [description]
     */
    _onChannelNotification: function (message) {
        var self = this;
        var def;
        var channelAlreadyInCache = true;
        if (message.channel_ids.length === 1) {
            channelAlreadyInCache = !!this.getChannel(message.channel_ids[0]);
            def = this.joinChannel(message.channel_ids[0], {autoswitch: false});
        } else {
            def = $.when();
        }
        def.then(function () {
            // don't increment unread if channel wasn't in cache yet as
            // its unread counter has just been fetched
            self._addMessage(message, {
                show_notification: true,
                increment_unread: channelAlreadyInCache
            });
            self._invalidateCaches(message.channel_ids);
        });
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} data [description]
     * @return {[type]}      [description]
     */
    _onChannelSeenNotification: function (data) {
        var channel = this.getChannel(data.id);
        if (channel) {
            channel.last_seen_message_id = data.last_message_id;
            if (channel.unread_counter) {
                this._updateChannelUnreadCounter(channel, 0);
            }
        }
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} chatSession [description]
     * @return {[type]}             [description]
     */
    _onChatSessionNotification: function (chatSession) {
        var channel;
        if ((chatSession.channel_type === "channel") && (chatSession.state === "open")) {
            this.addChannel(chatSession, {autoswitch: false});
            if (!chatSession.is_minimized && chatSession.info !== 'creation') {
                web_client.do_notify(_t("Invitation"), _t("You have been invited to: ") + chatSession.name);
            }
        }
        // partner specific change (open a detached window for example)
        if ((chatSession.state === "open") || (chatSession.state === "folded")) {
            channel = chatSession.is_minimized && this.getChannel(chatSession.id);
            if (channel) {
                channel.is_detached = true;
                channel.is_folded = (chatSession.state === "folded");
                this.bus.trigger("open_chat", channel);
            }
        } else if (chatSession.state === "closed") {
            channel = this.getChannel(chatSession.id);
            if (channel) {
                channel.is_detached = false;
                this.bus.trigger("close_chat", channel, {keep_open_if_unread: true});
            }
        }
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} result [description]
     * @return {[type]}        [description]
     */
    _onMailClientAction: function (result) {
        var self = this;
        _.each(result.channel_slots, function (channels) {
            _.each(channels, self.addChannel.bind(self));
        });
        this.needactionCounter = result.needaction_inbox_counter;
        this.starredCounter = result.starredCounter;
        this.commands = _.map(result.commands, function (command) {
            return _.extend({ id: command.name }, command);
        });
        this.mentionPartnerSuggestions = result.mention_partner_suggestions;
        this.discussMenuId = result.menu_id;

        // Shortcodes: canned responses and emojis
        _.each(result.shortcodes, function (s) {
            if (s.shortcode_type === 'text') {
                self.cannedResponses.push(_.pick(s, ['id', 'source', 'substitution']));
            } else {
                self.emojis.push(
                    _.pick(s, ['id', 'source', 'unicode_source', 'substitution', 'description'])
                );
                self.emojiSubstitutions[_.escape(s.source)] = s.substitution;
                if (s.unicode_source) {
                    self.emojiSubstitutions[_.escape(s.unicode_source)] = s.substitution;
                    self.emojiUnicodes[_.escape(s.source)] = s.unicode_source;
                }
            }
        });
        bus.start_polling();
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} data [description]
     * @return {[type]}      [description]
     */
    _onMarkAsReadNotification: function (data) {
        var self = this;
        _.each(data.message_ids, function (msgID) {
            var message = _.findWhere(self.messages, { id: msgID });
            if (message) {
                self._invalidateCaches(message.channel_ids);
                self._removeMessageFromChannel("channel_inbox", message);
                self.bus.trigger('update_message', message, data.type);
            }
        });
        if (data.channel_ids) {
            _.each(data.channel_ids, function (channelID) {
                var channel = self.getChannel(channelID);
                if (channel) {
                    channel.needactionCounter = Math.max(channel.needactionCounter - data.message_ids.length, 0);
                }
            });
        } else { // if no channel_ids specified, this is a 'mark all read' in the inbox
            _.each(this.channels, function (channel) {
                channel.needactionCounter = 0;
            });
        }
        this.needactionCounter = Math.max(this.needactionCounter - data.message_ids.length, 0);
        this.bus.trigger('update_needaction', this.needactionCounter);
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} message [description]
     * @return {[type]}         [description]
     */
    _onNeedactionNotification: function (message) {
        var self = this;
        message = this._addMessage(message, {
            channel_id: 'channel_inbox',
            increment_unread: true,
            show_notification: true,
        });
        this._invalidateCaches(message.channel_ids);
        if (message.channel_ids.length !== 0) {
            this.needactionCounter++;
        }
        _.each(message.channel_ids, function (channelID) {
            var channel = self.getChannel(channelID);
            if (channel) {
                channel.needactionCounter++;
            }
        });
        this.bus.trigger('update_needaction', this.needactionCounter);
    },
    /**
     * Notification handlers
     *
     * @private
     * @param  {[type]} notifications [description]
     * @return {[type]}               [description]
     */
    _onNotification: function (notifications) {
        // sometimes, the web client receives unsubscribe notification and an extra
        // notification on that channel.  This is then followed by an attempt to
        // rejoin the channel that we just left.  The next few lines remove the
        // extra notification to prevent that situation to occur.
        var self = this;
        var unsubscribedNotif = _.find(notifications, function (notif) {
            return notif[1].info === "unsubscribe";
        });
        if (unsubscribedNotif) {
            notifications = _.reject(notifications, function (notif) {
                return notif[0][1] === "mail.channel" && notif[0][2] === unsubscribedNotif[1].id;
            });
        }
        _.each(notifications, function (notification) {
            var model = notification[0][1];
            if (model === 'ir.needaction') {
                // new message in the inbox
                self._onNeedactionNotification(notification[1]);
            } else if (model === 'mail.channel') {
                // new message in a channel
                self._onChannelNotification(notification[1]);
            } else if (model === 'res.partner') {
                // channel joined/left, message marked as read/(un)starred, chat open/closed
                self._onPartnerNotification(notification[1]);
            } else if (model === 'bus.presence') {
                // update presence of users
                self._onPresenceNotification(notification[1]);
            }
        });
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} data [description]
     * @return {[type]}      [description]
     */
    _onPartnerNotification: function (data) {
        if (data.info === "unsubscribe") {
            var channel = this.getChannel(data.id);
            if (channel) {
                var msg;
                if (_.contains(['public', 'private'], channel.type)) {
                    msg = _.str.sprintf(_t('You unsubscribed from <b>%s</b>.'), channel.name);
                } else {
                    msg = _.str.sprintf(_t('You unpinned your conversation with <b>%s</b>.'), channel.name);
                }
                this._removeChannel(channel);
                this.bus.trigger("unsubscribe_from_channel", data.id);
                web_client.do_notify(_("Unsubscribed"), msg);
            }
        } else if (data.type === 'toggle_star') {
            this._onToggleStarNotification(data);
        } else if (data.type === 'mark_as_read') {
            this._onMarkAsReadNotification(data);
        } else if (data.info === 'channel_seen') {
            this._onChannelSeenNotification(data);
        } else if (data.info === 'transient_message') {
            this._onTransientMessageNotification(data);
        } else if (data.type === 'activity_updated') {
            this._onActivityUpdateNotification(data);
        } else {
            this._onChatSessionNotification(data);
        }
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} data [description]
     * @return {[type]}      [description]
     */
    _onPresenceNotification: function (data) {
        var dm = this.getDmFromPartnerID(data.id);
        if (dm) {
            dm.status = data.im_status;
            this.bus.trigger('update_dm_presence', dm);
        }
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} data [description]
     * @return {[type]}      [description]
     */
    _onToggleStarNotification: function (data) {
        var self = this;
        _.each(data.message_ids, function (msgID) {
            var message = _.findWhere(self.messages, { id: msgID });
            if (message) {
                self._invalidateCaches(message.channel_ids);
                message.is_starred = data.starred;
                if (!message.is_starred) {
                    self._removeMessageFromChannel("channel_starred", message);
                    self.starredCounter--;
                } else {
                    self._addToCache(message, []);
                    var channelStarred = self.getChannel('channel_starred');
                    channelStarred.cache = _.pick(channelStarred.cache, "[]");
                    self.starredCounter++;
                }
                self.bus.trigger('update_message', message);
            }
        });
        this.bus.trigger('update_starred', this.starredCounter);
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} data [description]
     * @return {[type]}      [description]
     */
    _onTransientMessageNotification: function (data) {
        var lastMessage = _.last(this.messages);
        data.id = (lastMessage ? lastMessage.id : 0) + 0.01;
        data.author_id = data.author_id || ODOOBOT_ID;
        this._addMessage(data);
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} channel [description]
     * @return {[type]}         [description]
     */
    _removeChannel: function (channel) {
        if (!channel) { return; }
        if (channel.type === 'dm') {
            var index = this.pinnedDmPartners.indexOf(channel.directPartnerID);
            if (index > -1) {
                this.pinnedDmPartners.splice(index, 1);
                bus.update_option('bus_presence_partner_ids', this.pinnedDmPartners);
            }
        }
        this.channels = _.without(this.channels, channel);
        delete this.channelDefs[channel.id];
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} channelID [description]
     * @param  {[type]} message   [description]
     * @return {[type]}           [description]
     */
    _removeMessageFromChannel: function (channelID, message) {
        message.channel_ids = _.without(message.channel_ids, channelID);
        var channel = _.findWhere(this.channels, { id: channelID });
        _.each(channel.cache, function (cache) {
            cache.messages = _.without(cache.messages, message);
        });
    },
    /**
     * [description]
     *
     * @private
     * @param  {[type]} channel [description]
     * @param  {[type]} counter [description]
     * @return {[type]}         [description]
     */
    _updateChannelUnreadCounter: function (channel, counter) {
        if (channel.unread_counter > 0 && counter === 0) {
            this.unreadConversationCounter = Math.max(0, this.unreadConversationCounter-1);
        } else if (channel.unread_counter === 0 && counter > 0) {
            this.unreadConversationCounter++;
        }
        channel.unread_counter = counter;
        this.bus.trigger("update_channel_unread_counter", channel);
    },
});

return ChatManager;

});
