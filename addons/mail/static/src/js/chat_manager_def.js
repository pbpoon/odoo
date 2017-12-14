odoo.define('mail.chatManager', function (require) {
"use strict";

var ChatManager = require('mail.ChatManager');
var Class = require('web.Class');
var Mixins = require('web.mixins');
var ServiceProviderMixin = require('web.ServiceProviderMixin');

var CallService = Class.extend(Mixins.EventDispatcherMixin, ServiceProviderMixin, {
    init: function () {
        Mixins.EventDispatcherMixin.init.call(this);
        ServiceProviderMixin.init.call(this);
    },
});

var chatManager = new ChatManager(new CallService());
chatManager.start();

return chatManager;

});
