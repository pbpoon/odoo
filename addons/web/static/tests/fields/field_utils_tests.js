odoo.define('web.field_utils_tests', function (require) {
"use strict";

var core = require('web.core');
var session = require('web.session');
var fieldUtils = require('web.field_utils');

QUnit.module('fields', {}, function () {

QUnit.module('field_utils');

QUnit.test('format integer', function(assert) {
    assert.expect(5);

    var originalGrouping = core._t.database.parameters.grouping;

    core._t.database.parameters.grouping = [3, 3, 3, 3];
    assert.strictEqual(fieldUtils.format.integer(1000000), '1,000,000');

    core._t.database.parameters.grouping = [3, 2, -1];
    assert.strictEqual(fieldUtils.format.integer(106500), '1,06,500');

    core._t.database.parameters.grouping = [1, 2, -1];
    assert.strictEqual(fieldUtils.format.integer(106500), '106,50,0');

    assert.strictEqual(fieldUtils.format.integer(0), "0");
    assert.strictEqual(fieldUtils.format.integer(false), "");

    core._t.database.parameters.grouping = originalGrouping;
});

QUnit.test('format float', function(assert) {
    assert.expect(5);

    var originalParameters = $.extend(true, {}, core._t.database.parameters);

    core._t.database.parameters.grouping = [3, 3, 3, 3];
    assert.strictEqual(fieldUtils.format.float(1000000), '1,000,000.00');

    core._t.database.parameters.grouping = [3, 2, -1];
    assert.strictEqual(fieldUtils.format.float(106500), '1,06,500.00');

    core._t.database.parameters.grouping = [1, 2, -1];
    assert.strictEqual(fieldUtils.format.float(106500), '106,50,0.00');

    _.extend(core._t.database.parameters, {
        grouping: [3, 0],
        decimal_point: ',',
        thousands_sep: '.'
    });
    assert.strictEqual(fieldUtils.format.float(6000), '6.000,00');
    assert.strictEqual(fieldUtils.format.float(false), '');

    core._t.database.parameters = originalParameters;
});

QUnit.test("format_datetime", function (assert) {
    assert.expect(1);

    var date_string = "2009-05-04 12:34:23";
    var date = fieldUtils.parse.datetime(date_string, {}, {timezone: false});
    var str = fieldUtils.format.datetime(date, {timezone: false});
    assert.strictEqual(str, moment(date).format("MM/DD/YYYY HH:mm:ss"));
});

QUnit.test("format_many2one", function (assert) {
    assert.expect(2);

    assert.strictEqual('', fieldUtils.format.many2one(null));
    assert.strictEqual('A M2O value', fieldUtils.format.many2one({
        data: { display_name: 'A M2O value' },
    }));
});

QUnit.test('format monetary', function(assert) {
    assert.expect(1);

    assert.strictEqual(fieldUtils.format.monetary(false), '');
});

QUnit.test('format char', function(assert) {
    assert.expect(1);

    assert.strictEqual(fieldUtils.format.char(), '',
        "undefined char should be formatted as an empty string");
});

QUnit.test('format many2many', function(assert) {
    assert.expect(3);

    assert.strictEqual(fieldUtils.format.many2many({data: []}), 'No records');
    assert.strictEqual(fieldUtils.format.many2many({data: [1]}), '1 record');
    assert.strictEqual(fieldUtils.format.many2many({data: [1, 2]}), '2 records');
});

QUnit.test('format one2many', function(assert) {
    assert.expect(3);

    assert.strictEqual(fieldUtils.format.one2many({data: []}), 'No records');
    assert.strictEqual(fieldUtils.format.one2many({data: [1]}), '1 record');
    assert.strictEqual(fieldUtils.format.one2many({data: [1, 2]}), '2 records');
});

QUnit.test('parse float', function(assert) {
    assert.expect(7);

    assert.strictEqual(fieldUtils.parse.float(""), 0);
    assert.strictEqual(fieldUtils.parse.float("0"), 0);
    assert.strictEqual(fieldUtils.parse.float("100.00"), 100);
    assert.strictEqual(fieldUtils.parse.float("-100.00"), -100);
    assert.strictEqual(fieldUtils.parse.float("1,000.00"), 1000);
    assert.strictEqual(fieldUtils.parse.float("1,000,000.00"), 1000000);

    var originalParameters = $.extend(true, {}, core._t.database.parameters);
    _.extend(core._t.database.parameters, {
        grouping: [3, 0],
        decimal_point: ',',
        thousands_sep: '.'
    });
    assert.strictEqual(fieldUtils.parse.float('1.234,567'), 1234.567);

    core._t.database.parameters = originalParameters;
});

QUnit.test('parse monetary', function(assert) {
    assert.expect(11);
    var originalCurrencies = session.currencies;
    session.currencies = {
        1: {
            digits: [69, 2],
            position: "after",
            symbol: "€"
        },
        3: {
            digits: [69, 2],
            position: "before",
            symbol: "$"
        }
    };

    assert.strictEqual(fieldUtils.parse.monetary(""), 0);
    assert.strictEqual(fieldUtils.parse.monetary("0"), 0);
    assert.strictEqual(fieldUtils.parse.monetary("100.00"), 100);
    assert.strictEqual(fieldUtils.parse.monetary("-100.00"), -100);
    assert.strictEqual(fieldUtils.parse.monetary("1,000.00"), 1000);
    assert.strictEqual(fieldUtils.parse.monetary("1,000,000.00"), 1000000);
    assert.strictEqual(fieldUtils.parse.monetary("$&nbsp;125.00", {}, {currency_id: 3}), 125);
    assert.strictEqual(fieldUtils.parse.monetary("1,000.00&nbsp;€", {}, {currency_id: 1}), 1000);
    assert.throws(function() {fieldUtils.parse.monetary("$ 12.00", {}, {currency_id: 3})}, /is not a correct/);
    assert.throws(function() {fieldUtils.parse.monetary("$&nbsp;12.00", {}, {currency_id: 1})}, /is not a correct/);
    assert.throws(function() {fieldUtils.parse.monetary("$&nbsp;12.00&nbsp;34", {}, {currency_id: 3})}, /is not a correct/);

    session.currencies = originalCurrencies;
});
});
});
