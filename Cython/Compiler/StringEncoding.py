#
#   Cython -- encoding related tools
#

import re
import sys

if sys.version_info[0] >= 3:
    _unicode, _str, _bytes = str, str, bytes
    IS_PYTHON3 = True
else:
    _unicode, _str, _bytes = unicode, str, str
    IS_PYTHON3 = False

empty_bytes = _bytes()
empty_unicode = _unicode()

join_bytes = empty_bytes.join

class UnicodeLiteralBuilder(object):
    """Assemble a unicode string.
    """
    def __init__(self):
        self.chars = []

    def append(self, characters):
        if isinstance(characters, _bytes):
            # this came from a Py2 string literal in the parser code
            characters = characters.decode("ASCII")
        assert isinstance(characters, _unicode), str(type(characters))
        self.chars.append(characters)

    def append_charval(self, char_number):
        self.chars.append( unichr(char_number) )

    def getstring(self):
        return EncodedString(u''.join(self.chars))


class BytesLiteralBuilder(object):
    """Assemble a byte string or char value.
    """
    def __init__(self, target_encoding):
        self.chars = []
        self.target_encoding = target_encoding

    def append(self, characters):
        if isinstance(characters, _unicode):
            characters = characters.encode(self.target_encoding)
        assert isinstance(characters, _bytes), str(type(characters))
        self.chars.append(characters)

    def append_charval(self, char_number):
        self.chars.append( unichr(char_number).encode('ISO-8859-1') )

    def getstring(self):
        # this *must* return a byte string!
        s = BytesLiteral(join_bytes(self.chars))
        s.encoding = self.target_encoding
        return s

    def getchar(self):
        # this *must* return a byte string!
        return self.getstring()

class EncodedString(_unicode):
    # unicode string subclass to keep track of the original encoding.
    # 'encoding' is None for unicode strings and the source encoding
    # otherwise
    encoding = None

    def byteencode(self):
        assert self.encoding is not None
        return self.encode(self.encoding)

    def utf8encode(self):
        assert self.encoding is None
        return self.encode("UTF-8")

    def is_unicode(self):
        return self.encoding is None
    is_unicode = property(is_unicode)

class BytesLiteral(_bytes):
    # bytes subclass that is compatible with EncodedString
    encoding = None

    def byteencode(self):
        if IS_PYTHON3:
            return _bytes(self)
        else:
            # fake-recode the string to make it a plain bytes object
            return self.decode('ISO-8859-1').encode('ISO-8859-1')

    def utf8encode(self):
        assert False, "this is not a unicode string: %r" % self

    def __str__(self):
        """Fake-decode the byte string to unicode to support %
        formatting of unicode strings.
        """
        return self.decode('ISO-8859-1')

    is_unicode = False

char_from_escape_sequence = {
    r'\a' : u'\a',
    r'\b' : u'\b',
    r'\f' : u'\f',
    r'\n' : u'\n',
    r'\r' : u'\r',
    r'\t' : u'\t',
    r'\v' : u'\v',
    }.get

def _to_escape_sequence(s):
    if s in '\n\r\t':
        return repr(s)[1:-1]
    elif s == '"':
        return r'\"'
    elif s == '\\':
        return r'\\'
    else:
        # within a character sequence, oct passes much better than hex
        return ''.join(['\\%03o' % ord(c) for c in s])

_c_special = ('\\', '\0', '\n', '\r', '\t', '??', '"')
_c_special_replacements = [(orig.encode('ASCII'),
                            _to_escape_sequence(orig).encode('ASCII'))
                           for orig in _c_special ]

def _build_specials_test():
    subexps = []
    for special in _c_special:
        regexp = ''.join(['[%s]' % c.replace('\\', '\\\\') for c in special])
        subexps.append(regexp)
    return re.compile('|'.join(subexps).encode('ASCII')).search

_has_specials = _build_specials_test()

def escape_char(c):
    if IS_PYTHON3:
        c = c.decode('ISO-8859-1')
    if c in '\n\r\t\\':
        return repr(c)[1:-1]
    elif c == "'":
        return "\\'"
    n = ord(c)
    if n < 32 or n > 127:
        # hex works well for characters
        return "\\x%02X" % n
    else:
        return c

def escape_byte_string(s):
    """Escape a byte string so that it can be written into C code.
    Note that this returns a Unicode string instead which, when
    encoded as ISO-8859-1, will result in the correct byte sequence
    being written.
    """
    if _has_specials(s):
        for special, replacement in _c_special_replacements:
            s = s.replace(special, replacement)
    try:
        return s.decode("ASCII") # trial decoding: plain ASCII => done
    except UnicodeDecodeError:
        pass
    if IS_PYTHON3:
        s_new = bytearray()
        append, extend = s_new.append, s_new.extend
        for b in s:
            if b >= 128:
                extend(('\\%3o' % b).encode('ASCII'))
            else:
                append(b)
        return s_new.decode('ISO-8859-1')
    else:
        l = []
        append = l.append
        for c in s:
            o = ord(c)
            if o >= 128:
                append('\\%3o' % o)
            else:
                append(c)
        return join_bytes(l).decode('ISO-8859-1')

def split_docstring(s):
    if len(s) < 2047:
        return s
    return '\\n\"\"'.join(s.split(r'\n'))
