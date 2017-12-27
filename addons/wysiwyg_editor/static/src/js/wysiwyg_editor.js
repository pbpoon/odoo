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
        if (!this.$el.find('#my_editor').html() .trim() === 'Write here...' || this.value) {
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
            if (_.contains(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'], command) || command == 'p') {
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

        var $catcher = $('.note-dimension-picker-mousecatcher');
        $catcher.css({
            width:  '10em',
            height: '10em'
        }).on('mousemove', function (event) {
            hDimensionPickerMove(event);
        });

        var PX_PER_EM = 18;
        var hDimensionPickerMove = function (event) {
            var $picker = $(event.target.parentNode); // target is mousecatcher
            var $dimensionDisplay = $picker.next();
            var $catcher = $picker.find('.note-dimension-picker-mousecatcher');
            var $highlighted = $picker.find('.note-dimension-picker-highlighted');
            var $unhighlighted = $picker.find('.note-dimension-picker-unhighlighted');

            var posOffset;
            // HTML5 with jQuery - e.offsetX is undefined in Firefox
            if (event.offsetX === undefined) {
                var posCatcher = $(event.target).offset();
                posOffset = {
                    x: event.pageX - posCatcher.left,
                    y: event.pageY - posCatcher.top
                };
            } else {
                posOffset = {
                  x: event.offsetX,
                  y: event.offsetY
                };
            }

            var dim = {
                c: Math.ceil(posOffset.x / PX_PER_EM) || 1,
                r: Math.ceil(posOffset.y / PX_PER_EM) || 1
            };

            $highlighted.css({ width: dim.c + 'em', height: dim.r + 'em' });
            $catcher.attr('data-value', dim.c + 'x' + dim.r);

            if (3 < dim.c && dim.c < 10) {
                $unhighlighted.css({ width: dim.c + 1 + 'em'});
            }

            if (3 < dim.r && dim.r < 10) {
                $unhighlighted.css({ height: dim.r + 1 + 'em'});
            }

            $dimensionDisplay.html(dim.c + ' x ' + dim.r);
        };
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
        if (this.$el.find('#my_editor').html().trim() === 'Write here...') {
            return '';
        }
        else {
            return this.$el.find('#my_editor').html();
        }
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
