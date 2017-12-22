odoo.define('wysiwyg_editor.wysiwyg_editor', function (require) {
'use strict';

var basic_fields = require('web.basic_fields');
var core = require('web.core');
var field_registry = require('web.field_registry');

var TranslatableFieldMixin = basic_fields.TranslatableFieldMixin;

var QWeb = core.qweb;

var MyHtmlEditor = basic_fields.DebouncedField.extend(TranslatableFieldMixin, {
    className: 'oe_form_field oe_form_field_html_text',
    supportedFieldTypes: ['html'],
    events: {click: '_onFocus'},
    xmlDependencies: ['/wysiwyg_editor/static/src/xml/backend.xml'],

    /**
     * @override
     */
    start: function () {
        $(QWeb.render('MyHtmlEditor')).appendTo(this.$el);
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _renderEdit: function () {
        if (!this.$el.find('#my_editor').html().trim() === 'Write here...' || this.value) {
            this.$el.find('#my_editor').html(this.value);
        }
        var colorPalette = ['000000', 'FF9966', '6699FF', '99FF66', 'CC0000', '00CC00', '0000CC', '333333', '0066FF', 'FFFFFF'];
        var forePalette = this.$('.fore-palette');
        var backPalette = this.$('.back-palette');

        for (var i = 0; i < colorPalette.length; i++) {
            forePalette.append('<a href="#" data-command="forecolor" data-value="' + '#' + colorPalette[i] + '" style="background-color:' + '#' + colorPalette[i] + ';" class="palette-item"></a>');
            backPalette.append('<a href="#" data-command="backcolor" data-value="' + '#' + colorPalette[i] + '" style="background-color:' + '#' + colorPalette[i] + ';" class="palette-item"></a>');
        }

        this.$('.edit_toolbar a').on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            var command = $(this).data('command');
            if (command == 'h1' || command == 'h2' || command == 'p') {
                document.execCommand('formatBlock', false, command);
            }
            if (command == 'forecolor' || command == 'backcolor') {
                document.execCommand($(this).data('command'), false, $(this).data('value'));
            }
            if (command == 'createlink' || command == 'insertimage') {
                var url = prompt('Enter the link here: ', 'http:\/\/');
                document.execCommand($(this).data('command'), false, url);
            } else {
                document.execCommand($(this).data('command'), false, null);
            }
        });
    },

    _renderReadonly: function () {
        this._super.apply(this, arguments);
        this.$el.append('<div>').html(this.value);
    },
    commitChanges: function () {
        if (this._getValue() !== this.value) {
            this._isDirty = true;
        }
        this._super.apply(this, arguments);
    },

    _getValue: function () {
        return this.$el.find('#my_editor').html();
    },

    _onFocus: function () {
        if (this.$el.find('#my_editor').html().trim() === 'Write here...') {
            this.$el.find('#my_editor').html('')
        }
    },
});

field_registry.add('my_html', MyHtmlEditor);
return { MyHtmlEditor: MyHtmlEditor };
});
