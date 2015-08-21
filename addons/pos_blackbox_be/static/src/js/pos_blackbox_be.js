odoo.define('pos_blackbox_be.pos_blackbox_be', function (require) {
    var core    = require('web.core');
    var screens = require('point_of_sale.screens');
    var models = require('point_of_sale.models');
    var devices = require('point_of_sale.devices');
    var chrome = require('point_of_sale.chrome');
    var Class = require('web.Class');
    var PosBaseWidget = require('point_of_sale.BaseWidget');
    var PaymentScreenWidget = screens.PaymentScreenWidget;

    var _t      = core._t;

    models.Orderline = models.Orderline.extend({
        // generates a table of the form
        // {..., 'char_to_translate': translation_of_char, ...}
        _generate_translation_table: function () {
            var replacements = [
                ["ÄÅÂÁÀâäáàã", "A"],
                ["Ææ", "AE"],
                ["ß", "SS"],
                ["çÇ", "C"],
                ["ÎÏÍÌïîìí", "I"],
                ["€", "E"],
                ["ÊËÉÈêëéè", "E"],
                ["ÛÜÚÙüûúù", "U"],
                ["ÔÖÓÒöôóò", "O"],
                ["Œœ", "OE"],
                ["ñÑ", "N"],
                ["ýÝÿ", "Y"]
            ];

            var lowercase_to_uppercase = _.range("a".charCodeAt(0), "z".charCodeAt(0) + 1).map(function (lowercase_ascii_code) {
                return [String.fromCharCode(lowercase_ascii_code), String.fromCharCode(lowercase_ascii_code).toUpperCase()];
            });
            replacements = replacements.concat(lowercase_to_uppercase);

            var lookup_table = {};

            _.forEach(replacements, function (letter_group) {
                _.forEach(letter_group[0], function (special_char) {
                    lookup_table[special_char] = letter_group[1];
                });
            });

            return lookup_table;
        },

        _replace_hash_and_sign_chars: function (str) {
            if (typeof str !== 'string') {
                throw "Can only handle strings";
            }

            var translation_table = this._generate_translation_table();

            var replaced_char_array = _.map(str, function (char, index, str) {
                var translation = translation_table[char];
                if (translation) {
                    return translation;
                } else {
                    return char;
                }
            });

            return replaced_char_array.join("");
        },

        // for hash and sign the allowed range for DATA is:
        //   - A-Z
        //   - 0-9
        // and SPACE as well. We filter SPACE out here though, because
        // SPACE will only be used in DATA of hash and sign as description
        // padding
        _filter_allowed_hash_and_sign_chars: function (str) {
            if (typeof str !== 'string') {
                throw "Can only handle strings";
            }

            var filtered_char_array = _.filter(str, function (char) {
                var ascii_code = char.charCodeAt(0);

                if ((ascii_code >= "A".charCodeAt(0) && ascii_code <= "Z".charCodeAt(0)) ||
                    (ascii_code >= "0".charCodeAt(0) && ascii_code <= "9".charCodeAt(0))) {
                    return true;
                } else {
                    return false;
                }
            });

            return filtered_char_array.join("");
        },

        // for both amount and price
        // price should be in eurocents
        // amount should be in gram
        _prepare_number_for_plu: function (number, field_length) {
            number = Math.abs(number);
            number = Math.round(number); // todo jov: don't like this

            var number_string = number.toFixed(0);

            number_string = this._replace_hash_and_sign_chars(number_string);
            number_string = this._filter_allowed_hash_and_sign_chars(number_string);

            // get the required amount of least significant characters
            number_string = number_string.substr(-field_length);

            // pad left with 0 to required size
            while (number_string.length < field_length) {
                number_string = "0" + number_string;
            }

            return number_string;
        },

        _prepare_description_for_plu: function (description) {
            description = this._replace_hash_and_sign_chars(description);
            description = this._filter_allowed_hash_and_sign_chars(description);

            // get the 20 most significant characters
            description = description.substr(0, 20);

            // pad right with SPACE to required size of 20
            while (description.length < 20) {
                description = description + " ";
            }

            return description;
        },

        _get_amount_for_plu: function () {
            // three options:
            // 1. unit => need integer
            // 2. weight => need integer gram
            // 3. volume => need integer milliliter

            var amount = this.get_quantity();
            var uom = this.get_unit();

            if (uom.is_unit) {
                return amount;
            } else {
                if (uom.category_id[1] === "Weight") {
                    var uom_gram = _.find(this.pos.units_by_id, function (unit) {
                        return unit.category_id[1] === "Weight" && unit.name === "g";
                    });
                    amount = (amount / uom.factor) * uom_gram.factor;
                } else if (uom.category_id[1] === "Volume") {
                    var uom_milliliter = _.find(this.pos.units_by_id, function (unit) {
                        return unit.category_id[1] === "Volume" && unit.name === "Milliliter(s)";
                    });
                    amount = (amount / uom.factor) * uom_milliliter.factor;
                }

                return amount;
            }
        },

        get_vat_letter: function () {
            var taxes = this.get_taxes()[0];
            var line_name = this.get_product().display_name;

            if (! taxes) {
                throw new Error(line_name + " has no tax associated with it.");
            }

            var vat_letter = taxes.identification_letter;

            if (! vat_letter) {
                throw new Error(line_name + " has an invalid tax amount. Only 21%, 12%, 6% and 0% are allowed.");
            }

            return vat_letter;
        },

        generate_plu_line: function () {
            // |--------+-------------+-------+-----|
            // | AMOUNT | DESCRIPTION | PRICE | VAT |
            // |      4 |          20 |     8 |   1 |
            // |--------+-------------+-------+-----|

            // steps:
            // 1. replace all chars
            // 2. filter out forbidden chars
            // 3. build PLU line

            var amount = this._get_amount_for_plu();
            var description = this.get_product().display_name;
            var price_in_eurocents = this.get_display_price() * 100;
            var vat_letter = this.get_vat_letter();

            amount = this._prepare_number_for_plu(amount, 4);
            description = this._prepare_description_for_plu(description);
            price_in_eurocents = this._prepare_number_for_plu(price_in_eurocents, 8);

            return amount + description + price_in_eurocents + vat_letter;
        }
    });

    models.Order = models.Order.extend({
        _hash_and_sign_string: function () {
            var order_str = "";

            this.get_orderlines().forEach(function (current, index, array) {
                order_str += current.generate_plu_line();
            });

            return order_str;
        },

        get_tax_percentage_for_tax_letter: function (tax_letter) {
            var percentage_per_letter = {
                'A': 21,
                'B': 12,
                'C': 6,
                'D': 0
            };

            return percentage_per_letter[tax_letter];
        },

        get_base_price_in_eurocents_per_tax_letter: function () {
            var base_price_per_tax_letter = {
                'A': 0,
                'B': 0,
                'C': 0,
                'D': 0
            };

            this.get_orderlines().forEach(function (current, index, array) {
                var tax_letter = current.get_vat_letter();

                if (tax_letter) {
                    base_price_per_tax_letter[tax_letter] += Math.floor(current.get_price_without_tax() * 100);
                }
            });

            return base_price_per_tax_letter;
        },

        // returns an array of the form:
        // [{'letter', 'amount'}, {'letter', 'amount'}, ...]
        get_base_price_in_eurocents_per_tax_letter_list: function () {
            var base_price_per_tax_letter = this.get_base_price_in_eurocents_per_tax_letter();
            var base_price_per_tax_letter_list = _.map(_.keys(base_price_per_tax_letter), function (key) {
                return {
                    'letter': key,
                    'amount': base_price_per_tax_letter[key]
                };
            });

            return base_price_per_tax_letter_list;
        },

        calculate_hash: function () {
            return Sha1.hash(this._hash_and_sign_string());
        },

        set_validation_time: function () {
            this.blackbox_pos_receipt_time = moment();
        }
    });

    var FDMPacketField = Class.extend({
        init: function (name, length, content, pad_character) {
            if (typeof content !== 'string') {
                throw "Can only handle string contents";
            }

            this.name = name;
            this.length = length;

            this.content = this._pad_left_to_length(content, pad_character);
        },

        _pad_left_to_length: function (content, pad_character) {
            if (content.length < this.length && ! pad_character) {
                throw "Can't pad without a pad character";
            }

            while (content.length < this.length) {
                content = pad_character + content;
            }

            return content;
        },

        to_string: function () {
            return this.content;
        }
    });

    var FDMPacket = Class.extend({
        init: function () {
            this.fields = [];
        },

        add_field: function (field) {
            this.fields.push(field);
        },

        to_string: function () {
            return _.map(this.fields, function (field) {
                return field.to_string();
            }).join("");
        },

        to_human_readable_string: function () {
            return _.map(this.fields, function (field) {
                return field.name + ": " + field.to_string();
            }).join("\n");
        }

        // todo jov: send: function () {}?
    });

    PaymentScreenWidget.include({
        _prepare_date_for_ticket: function (date) {
            // format of date coming from blackbox is YYYYMMDD
            var year = date.substr(0, 4);
            var month = date.substr(4, 2);
            var day = date.substr(6, 2);

            return day + "/" + month + "/" + year;
        },

        _prepare_time_for_ticket: function (time) {
            // format of time coming from blackbox is HHMMSS
            var hours = time.substr(0, 2);
            var minutes = time.substr(2, 2);
            var seconds = time.substr(4, 2);

            return hours + ":" + minutes + ":" + seconds;
        },

        _prepare_ticket_counter_for_ticket: function (counter, total_counter, event_type) {
            return counter + "/" + total_counter + " " + event_type;
        },

        _required_information_filled_in: function () {
            if (! this.pos.get_cashier().insz_or_bis_number) {
                this.gui.show_popup("error", {
                    'title': _t("Fiscal Data Module error"),
                    'body':  _t("INSZ or BIS number not set for current cashier."),
                });

                return false;
            } else if (! this.pos.company.street) {
                this.gui.show_popup("error", {
                    'title': _t("Fiscal Data Module error"),
                    'body':  _t("Company address must be set."),
                });

                return false;
            } else if (! this.pos.company.vat) {
                this.gui.show_popup("error", {
                    'title': _t("Fiscal Data Module error"),
                    'body':  _t("VAT number must be set."),
                });

                return false;
            }

            return true;
        },

        _prepare_plu_hash_for_ticket: function (hash) {
            var amount_of_least_significant_characters = 8;

            return hash.substr(-amount_of_least_significant_characters);
        },

        validate_order: function (force_validation) {
            var self = this;
            var validate_order_super = this._super.bind(this);
            var order = self.pos.get_order();

            if (! this._required_information_filled_in()) {
                return;
            }

            order.set_validation_time();

            var packet = this.pos.proxy._build_fdm_hash_and_sign_request(order);
            this.pos.proxy.request_fdm_hash_and_sign(packet).then(function (parsed_response) {
                if (parsed_response) {
                    // put fields that we need on tickets on order
                    order.blackbox_date = self._prepare_date_for_ticket(parsed_response.date);
                    order.blackbox_time = self._prepare_time_for_ticket(parsed_response.time);
                    order.blackbox_ticket_counter =
                        self._prepare_ticket_counter_for_ticket(parsed_response.vsc_ticket_counter,
                                                                parsed_response.vsc_total_ticket_counter,
                                                                parsed_response.event_label);
                    order.blackbox_signature = parsed_response.signature;
                    order.blackbox_vsc_identification_number = parsed_response.vsc_identification_number;
                    order.blackbox_unique_fdm_production_number = parsed_response.fdm_unique_production_number;
                    order.blackbox_plu_hash = self._prepare_plu_hash_for_ticket(packet.fields[packet.fields.length - 1].content);

                    validate_order_super(force_validation);
                }
            });
        }
    });

    devices.ProxyDevice.include({
        _get_sequence_number: function () {
            var sequence_number = this.pos.db.load('sequence_number', 0);
            this.pos.db.save('sequence_number', (sequence_number + 1) % 100);

            console.log("using sequence number: " + sequence_number);
            return sequence_number;
        },

        build_request: function (id) {
            var packet = new FDMPacket();

            packet.add_field(new FDMPacketField("id", 1, id));
            packet.add_field(new FDMPacketField("sequence number", 2, this._get_sequence_number().toString(), "0"));
            packet.add_field(new FDMPacketField("retry number", 1, "0"));

            return packet;
        },

        // ignore_non_critical: will ignore everything (no errors and
        // warnings) and will ignore certain 'real' errors defined in
        // non_critical_errors
        _handle_fdm_errors: function (parsed_response, ignore_non_critical) {
            var self = this;
            var error_1 = parsed_response.error_1;
            var error_2 = parsed_response.error_2;

            var non_critical_errors = [
                1, // no vat signing card
                2, // initialize vat signing card with pin
                3, // vsc blocked
                5, // memory full
                9, // real time clock corrupt
                10, // vsc not compatible
            ];

            if (error_1 === 0) { // no errors
                if (error_2 === 1) {
                    this.pos.gui.show_popup("confirm", {
                        'title': _t("Fiscal Data Module"),
                        'body':  _t("PIN accepted."),
                    });
                }

                return true;
            } else if (error_1 === 1 && ! ignore_non_critical) { // warnings
                if (error_2 === 1) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module warning"),
                        'body':  _t("Fiscal Data Module memory 90% full."),
                    });
                } else if (error_2 === 2) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module warning"),
                        'body':  _t("Already handled request."),
                    });
                } else if (error_2 === 3) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module warning"),
                        'body':  _t("No record."),
                    });
                } else if (error_2 === 99) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module warning"),
                        'body':  _t("Unspecified warning."),
                    });
                }

                return true;
            } else { // errors
                if (ignore_non_critical && non_critical_errors.indexOf(error_2) !== -1) {
                    return true;
                }

                if (error_2 === 1) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("No Vat Signing Card or Vat Signing Card broken."),
                    });
                } else if (error_2 === 2) {
                    this.pos.gui.show_popup("number", {
                        'title': _t("Please initialize the Vat Signing Card with PIN."),
                        'confirm': function (pin) {
                            self.pos.proxy.request_fdm_pin_verification(pin);
                        }
                    });
                } else if (error_2 === 3) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Vat Signing Card blocked."),
                    });
                } else if (error_2 === 4) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Invalid PIN."),
                    });
                } else if (error_2 === 5) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Fiscal Data Module memory full."),
                    });
                } else if (error_2 === 6) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Unknown identifier."),
                    });
                } else if (error_2 === 7) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Invalid data in message."),
                    });
                } else if (error_2 === 8) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Fiscal Data Module not operational."),
                    });
                } else if (error_2 === 9) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Fiscal Data Module real time clock corrupt."),
                    });
                } else if (error_2 === 10) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Vat Signing Card not compatible with Fiscal Data Module."),
                    });
                } else if (error_2 === 99) {
                    this.pos.gui.show_popup("error", {
                        'title': _t("Fiscal Data Module error"),
                        'body':  _t("Unspecified error."),
                    });
                }

                return false;
            }
        },

        _parse_fdm_common_response: function (response) {
            return {
                identifier: response[0],
                sequence_number: parseInt(response.substr(1, 2), 10),
                retry_counter: parseInt(response[3], 10),
                error_1: parseInt(response[4], 10),
                error_2: parseInt(response.substr(5, 2), 10),
                error_3: parseInt(response.substr(7, 3), 10),
                fdm_unique_production_number: response.substr(10, 11),
            };
        },

        parse_fdm_identification_response: function (response) {
            return _.extend(this._parse_fdm_common_response(response),
                            {
                                fdm_firmware_version_number: response.substr(21, 20),
                                fdm_communication_protocol_version: response[41],
                                vsc_identification_number: response.substr(42, 14),
                                vsc_version_number: parseInt(response.substr(56, 3), 10)
                            });
        },

        parse_fdm_pin_response: function (response) {
            return _.extend(this._parse_fdm_common_response(response),
                            {
                                vsc_identification_number: response.substr(21, 14),
                            });
        },

        parse_fdm_hash_and_sign_response: function (response) {
            return _.extend(this._parse_fdm_common_response(response),
                            {
                                vsc_identification_number: response.substr(21, 14),
                                date: response.substr(35, 8),
                                time: response.substr(43, 6),
                                event_label: response.substr(49, 2),
                                vsc_ticket_counter: parseInt(response.substr(51, 9)),
                                vsc_total_ticket_counter: parseInt(response.substr(60, 9)),
                                signature: response.substr(69, 40)
                            });
        },

        _build_fdm_identification_request: function () {
            return this.build_request("I");
        },

        _build_fdm_pin_request: function (pin) {
            var packet = this.build_request("P");
            packet.add_field(new FDMPacketField("pin code", 5, pin.toString(), "0"));

            return packet;
        },

        // todo jov: p77
        _build_fdm_hash_and_sign_request: function (order) {
            var packet = this.build_request("H");
            var insz_or_bis_number = this.pos.get_cashier().insz_or_bis_number;

            packet.add_field(new FDMPacketField("ticket date", 8, order.blackbox_pos_receipt_time.format("YYYYMMDD")));
            packet.add_field(new FDMPacketField("ticket time", 6, order.blackbox_pos_receipt_time.format("HHmmss")));
            packet.add_field(new FDMPacketField("insz or bis number", 11, insz_or_bis_number));

            // todo jov:
            // p8
            // format is kind of weird
            // id   cert license-key
            // BXXX CCC  PPPPPPP
            packet.add_field(new FDMPacketField("production number POS", 14, this.pos.blackbox_pos_production_id));

            // todo jov:
            // this should be truly sequential (so always +1) also across sessions
            // so probably just add a field on the point_of_sale
            packet.add_field(new FDMPacketField("ticket number", 6, order.sequence_number.toString(), "0"));

            // todo jov:
            // p3 pdf
            // most normal thing is normal sales => NS
            // but there's also the training and pro forma (implement?)
            packet.add_field(new FDMPacketField("event label", 2, "NS"));

            packet.add_field(new FDMPacketField("total amount to pay in eurocent", 11, (order.get_due() * 100).toString(), " "));

            var tax_amounts = order.get_base_price_in_eurocents_per_tax_letter();
            packet.add_field(new FDMPacketField("tax percentage 1", 4, "2100"));
            packet.add_field(new FDMPacketField("amount at tax percentage 1 in eurocent", 11, tax_amounts['A'].toString(), " "));
            packet.add_field(new FDMPacketField("tax percentage 2", 4, "1200"));
            packet.add_field(new FDMPacketField("amount at tax percentage 2 in eurocent", 11, tax_amounts['B'].toString(), " "));
            packet.add_field(new FDMPacketField("tax percentage 3", 4, " 600"));
            packet.add_field(new FDMPacketField("amount at tax percentage 3 in eurocent", 11, tax_amounts['C'].toString(), " "));
            packet.add_field(new FDMPacketField("tax percentage 4", 4, " 000"));
            packet.add_field(new FDMPacketField("amount at tax percentage 4 in eurocent", 11, tax_amounts['D'].toString(), " "));
            packet.add_field(new FDMPacketField("PLU hash", 40, order.calculate_hash()));

            return packet;
        },

        _show_could_not_connect_error: function () {
            self.pos.gui.show_popup("error", {
                'title': _t("Fiscal Data Module error"),
                'body':  _t("Could not connect to the Fiscal Data Module."),
            });
        },

        request_fdm_identification: function () {
            var self = this;

            return this.message('request_blackbox', {
                'high_layer': self._build_fdm_identification_request().to_string(),
                'response_size': 59
            }).then(function (response) {
                if (! response) {
                    self._show_could_not_connect_error();
                    return "";
                } else {
                    var parsed_response = self.parse_fdm_identification_response(response);

                    if (self._handle_fdm_errors(parsed_response, true)) {
                        return parsed_response;
                    } else {
                        return "";
                    }
                }
            });
        },

        request_fdm_pin_verification: function (pin) {
            var self = this;

            return this.message('request_blackbox', {
                'high_layer': self._build_fdm_pin_request(pin).to_string(),
                'response_size': 35
            }).then(function (response) {
                if (! response) {
                    self._show_could_not_connect_error();
                } else {
                    var parsed_response = self.parse_fdm_pin_response(response);

                    // pin being verified will show up as 'error'
                    self._handle_fdm_errors(parsed_response);
                }
            });
        },

        request_fdm_hash_and_sign: function (packet) {
            var self = this;

            console.log(packet.to_human_readable_string());

            return this.message('request_blackbox_mock_hash_and_sign', {
                'high_layer': packet.to_string(),
                'response_size': 109
            }).then(function (response) {
                if (! response) {
                    self._show_could_not_connect_error();
                    return "";
                } else {
                    var parsed_response = self.parse_fdm_hash_and_sign_response(response);

                    if (self._handle_fdm_errors(parsed_response)) {
                        return parsed_response;
                    } else {
                        return "";
                    }
                }
            });
        }
    });

    var BlackBoxIdentificationWidget = PosBaseWidget.extend({
        template: 'BlackboxIdentificationWidget',
        start: function () {
            var self = this;

            this.$el.click(function () {
                self.pos.proxy.request_fdm_identification().then(function (parsed_response) {
                    if (parsed_response) {
                        var list = _.map(_.pairs(_.pick(parsed_response, 'fdm_unique_production_number',
                                                        'fdm_firmware_version_number',
                                                        'fdm_communication_protocol_version',
                                                        'vsc_identification_number',
                                                        'vsc_version_number')), function (current) {
                                                            return {
                                                                'label': current[0].replace(/_/g, " ") + ": " + current[1]
                                                            };
                                                        });

                        self.gui.show_popup("selection", {
                            'title': _t("FDM identification"),
                            'list': list
                        });
                    }
                });
            });
        },
    });

    chrome.Chrome.include({
        build_widgets: function () {
            // add blackbox id widget to left of proxy widget
            var proxy_status_index = _.findIndex(this.widgets, function (widget) {
                return widget.name === "proxy_status";
            });

            this.widgets.splice(proxy_status_index, 0, {
                'name': 'blackbox_identification',
                'widget': BlackBoxIdentificationWidget,
                'append': '.pos-rightheader',
            });

            var debug_widget = _.find(this.widgets, function (widget) {
                return widget.name === "debug";
            });

            debug_widget.widget.include({
                start: function () {
                    var self = this;
                    this._super();

                    this.$('.button.build-hash-and-sign-request').click(function () {
                        var order = self.pos.get_order();
                        order.set_validation_time();

                        console.log(self.pos.proxy._build_fdm_hash_and_sign_request(order).to_human_readable_string());
                    });
                }
            });

            this._super();
        }
    });

    models.load_models({
        'model': "ir.config_parameter",
        'fields': ['key', 'value'],
        'domain': [['key', '=', 'database.uuid']],
        'loaded': function (self, params) {
            // 12 lsB of db uid + 2 bytes pos config
            var config_id = self.config.id.toString();

            if (config_id.length < 2) {
                config_id = "0" + config_id;
            }

            self.blackbox_pos_production_id = params[0].value.substr(-12) + config_id;
        }
    }, {
        'after': "pos.config"
    });

    models.load_fields("res.users", "insz_or_bis_number");
    models.load_fields("account.tax", "identification_letter");
    models.load_fields("res.company", "street");

    return {
        'FDMPacketField': FDMPacketField,
        'FDMPacket': FDMPacket
    };
});
