odoo.define('web.KanbanStageRegistry', function (require) {
"use strict";

var Class = require('web.Class');

var KanbanStageRegistry = Class.extend({
    /**
     * @constructor
     * @param {Object} [mapping] the initial data in the registry
     */
    init: function (mapping) {
        this.map = Object.create(mapping || null);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Add a key (and a value) to the registry.
     *
     * @param {string} key
     * @param {any} value
     * @returns {Registry} can be used to chain add calls.
     */
    add: function (key, value) {
        if (!this.contains(key)) {
            this.map[key] = [];
        }
        _.mapObject(value.exampleStages, function(stage) {
            stage.id = 'stage_'+_.uniqueId();
            return stage;
        });
        this.map[key] = value;
        return this;
    },
    /**
     * Check if the registry contains the value
     *
     * @param {string} key
     * @returns {boolean}
     */
    contains: function (key) {
        return (key in this.map);
    },
    /**
     * Returns the value associated to the given key.
     *
     * @param {string} key
     * @returns {any}
     */
    get: function (key) {
        return this.map[key];
    }
});

return new KanbanStageRegistry;

});

