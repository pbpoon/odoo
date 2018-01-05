# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


"""
Convenience classes to manipulate dates and datetimes
"""

import datetime
import json
from odoo.tools import pycompat
from odoo.tools.func import monkey_patch

DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT)

DATE_LENGTH = len(datetime.date.today().strftime(DEFAULT_SERVER_DATE_FORMAT))

# Python's strftime supports only the format directives
# that are available on the platform's libc, so in order to
# be cross-platform we map to the directives required by
# the C standard (1989 version), always available on platforms
# with a C standard implementation.
DATETIME_FORMATS_MAP = {
        '%C': '', # century
        '%D': '%m/%d/%Y', # modified %y->%Y
        '%e': '%d',
        '%E': '', # special modifier
        '%F': '%Y-%m-%d',
        '%g': '%Y', # modified %y->%Y
        '%G': '%Y',
        '%h': '%b',
        '%k': '%H',
        '%l': '%I',
        '%n': '\n',
        '%O': '', # special modifier
        '%P': '%p',
        '%R': '%H:%M',
        '%r': '%I:%M:%S %p',
        '%s': '', #num of seconds since epoch
        '%T': '%H:%M:%S',
        '%t': ' ', # tab
        '%u': ' %w',
        '%V': '%W',
        '%y': '%Y', # Even if %y works, it's ambiguous, so we should use %Y
        '%+': '%Y-%m-%d %H:%M:%S',

        # %Z is a special case that causes 2 problems at least:
        #  - the timezone names we use (in res_user.context_tz) come
        #    from pytz, but not all these names are recognized by
        #    strptime(), so we cannot convert in both directions
        #    when such a timezone is selected and %Z is in the format
        #  - %Z is replaced by an empty string in strftime() when
        #    there is not tzinfo in a datetime value (e.g when the user
        #    did not pick a context_tz). The resulting string does not
        #    parse back if the format requires %Z.
        # As a consequence, we strip it completely from format strings.
        # The user can always have a look at the context_tz in
        # preferences to check the timezone.
        '%z': '',
        '%Z': '',
}

POSIX_TO_LDML = {
    'a': 'E',
    'A': 'EEEE',
    'b': 'MMM',
    'B': 'MMMM',
    #'c': '',
    'd': 'dd',
    'H': 'HH',
    'I': 'hh',
    'j': 'DDD',
    'm': 'MM',
    'M': 'mm',
    'p': 'a',
    'S': 'ss',
    'U': 'w',
    'w': 'e',
    'W': 'w',
    'y': 'yy',
    'Y': 'yyyy',
    # see comments above, and babel's format_datetime assumes an UTC timezone
    # for naive datetime objects
    #'z': 'Z',
    #'Z': 'z',
}

def posix_to_ldml(fmt, locale):
    """ Converts a posix/strftime pattern into an LDML date format pattern.

    :param fmt: non-extended C89/C90 strftime pattern
    :param locale: babel locale used for locale-specific conversions (e.g. %x and %X)
    :return: unicode
    """
    buf = []
    pc = False
    quoted = []

    for c in fmt:
        # LDML date format patterns uses letters, so letters must be quoted
        if not pc and c.isalpha():
            quoted.append(c if c != "'" else "''")
            continue
        if quoted:
            buf.append("'")
            buf.append(''.join(quoted))
            buf.append("'")
            quoted = []

        if pc:
            if c == '%': # escaped percent
                buf.append('%')
            elif c == 'x': # date format, short seems to match
                buf.append(locale.date_formats['short'].pattern)
            elif c == 'X': # time format, seems to include seconds. short does not
                buf.append(locale.time_formats['medium'].pattern)
            else: # look up format char in static mapping
                buf.append(POSIX_TO_LDML[c])
            pc = False
        elif c == '%':
            pc = True
        else:
            buf.append(c)

    # flush anything remaining in quoted buffer
    if quoted:
        buf.append("'")
        buf.append(''.join(quoted))
        buf.append("'")

    return ''.join(buf)

class ODate(datetime.date):
    """
    datetime.date compatibility object with better string representation.
    """
    def __init__(self, year, month, day, dateformat=None):
        if not dateformat:
            dateformat = DEFAULT_SERVER_DATE_FORMAT

        self.dateformat = dateformat

    def __cmp__(self, other): # for python2 only
        if self.__lt__(self, other):
            return -1
        if self.__gt__(self, other):
            return 1
        return 0

    def __contains__(self, item):
        return item in str(self)

    def __eq__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return super(ODate, self).__eq__(other)

    def __ge__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return super(ODate, self).__ge__(other)

    def __getitem__(self, key):
        return str(self)[key]

    def __gt__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return super(ODate, self).__gt__(other)

    def __iter__(self):
        for char in str(self):
            yield char

    def __le__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return super(ODate, self).__le__(other)

    def __len__(self):
        return len(str(self))

    def __lt__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return super(ODate, self).__lt__(other)

    def __ne__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return super(ODate, self).__ne__(other)

    def __repr__(self):
        return '<ODate %s>' % str(self)

    def __str__(self):
        return self.strftime(self.dateformat)

    def __sub__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return super(ODate, self).__sub__(other)

    def __unicode__(self): # for python2 only
        return unicode(str(self))

    def decode(self, encoding='utf-8', errors='strict'):
        """ Launch decode on string form """
        return str(self).decode(encoding, errors)

    def encode(self, encoding="utf-8", errors="strict"):
        """ Launch encode on string form """
        return str(self).encode(encoding, errors)

    def endswith(self, suffix, start=None, end=None):
        """ String form ends with suffix ? """
        return str(self).endswith(suffix, start, end)

    def find(self, sub, start=None, end=None):
        """ Find in string form """
        return str(self).find(sub, start, end)

    @classmethod
    def fromdate(cls, date):
        """ Create an instance from date """
        return cls(date.year, date.month, date.day)

    @classmethod
    def fromstring(cls, string, dateformat=None):
        """ Create an instance from string """
        if not dateformat:
            dateformat = DEFAULT_SERVER_DATE_FORMAT

        return cls.fromdate(datetime.datetime.strptime(string, dateformat))

    def index(self, sub, start=None, end=None):
        """ Get the index of substring in string representation """
        return str(self).index(sub, start, end)

    def replace(self, *args, **kwargs):
        """ Replace old substring by a new one or create a new instance of date. """
        date_params = {'year', 'month', 'day'}
        if date_params | set(kwargs.keys()) or (args and isinstance(args[0], int)):
            return super(ODate, self).replace(*args, **kwargs)

        datestr = str(self)
        datestr.replace(*args, **kwargs)
        self.setstring(datestr)

    def rfind(self, sub, start=None, end=None):
        """ Find substring from right """
        return str(self).rfind(sub, start, end)

    def rindex(self, sub, start=None, end=None):
        """ Get the index of substring, starting from right """
        return str(self).index(sub, start, end)

    def rsplit(self, sep=None, maxsplit=-1):
        """ Right split of string representation """
        return str(self).rsplit(sep, maxsplit)

    def rstrip(self, chars=None):
        """ Right strip of string representation """
        return str(self).rstrip(chars)

    def setdate(self, date):
        """ Set date from date object """
        self.replace(date.year, date.month, date.day)

    @classmethod
    def setstring(cls, string):
        """ Set date from string """
        pass

    def split(self, sep=None, maxsplit=-1):
        """ Split string representation """
        return str(self).split(sep, maxsplit)

    def splitlines(self, keepends):
        """ Split lines of string representation """
        return str(self).splitlines(keepends)

    def startswith(self, prefix, start=None, end=None):
        """  Does string representation start with substring ? """
        return str(self).startswith(prefix, start, end)

    def strip(self, chars):
        """ Strip string representation """
        return str(self).strip(chars)

class ODatetime(datetime.datetime, ODate):
    """
    datetime.datetime compatibility object with better string representation.
    """
    def __eq__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return datetime.datetime.__eq__(self, other)

    def __ge__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return datetime.datetime.__ge__(self, other)

    def __init__(self, year, month, day, hour=0, minute=0, second=0,
                 microsecond=0, tzinfo=None, dateformat=None):
        if not dateformat:
            dateformat = DEFAULT_SERVER_DATETIME_FORMAT

        self.dateformat = dateformat

    def __gt__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return datetime.datetime.__gt__(self, other)

    def __le__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return datetime.datetime.__le__(self, other)

    def __len__(self):
        return len(str(self))

    def __lt__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return datetime.datetime.__lt__(self, other)

    def __ne__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return datetime.datetime.__ne__(self, other)

    def __repr__(self):
        return '<ODatetime %s>' % str(self)

    def __sub__(self, other):
        if isinstance(other, pycompat.string_types):
            other = self.fromstring(other, self.dateformat)
        return datetime.datetime.__sub__(self, other)

    def date(self):
        return ODate.fromdate(super(ODatetime, self).date())

    @classmethod
    def fromdatetime(cls, new):
        """ Create an instance from a datetime object. """
        return cls(
            new.year, new.month, new.day,
            hour=new.hour, minute=new.minute, second=new.second, microsecond=new.microsecond,
            tzinfo=new.tzinfo)

    @classmethod
    def fromstring(cls, string, dateformat=None):
        """ Create an instance from string """
        if not dateformat:
            dateformat = DEFAULT_SERVER_DATETIME_FORMAT

        return cls.fromdatetime(datetime.datetime.strptime(string, dateformat))

    def replace(self, *args, **kwargs):
        """ Replace old substring by a new one or create a new instance of date. """
        date_params = {
            'year', 'month', 'day',
            'hour', 'minute', 'second', 'microsecond',
            'tzinfo'}
        if date_params | set(kwargs.keys()) or (args and isinstance(args[0], int)):
            return datetime.datetime.replace(self, *args, **kwargs)

        datestr = str(self)
        datestr.replace(*args, **kwargs)
        self.setstring(datestr)

    def setdatetime(self, new):
        """ Set date from datetime object """
        self.replace(
            new.year, new.month, new.day, new.hour, new.second,
            microsecond=new.microsecond, tzinfo=new.tzinfo)

@monkey_patch(json.JSONEncoder)
def default(self, o):
    if isinstance(o, ODate):
        return str(o)
    return default.super(self, o)
