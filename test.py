"""
Simple test suite for acora.
"""

import acora

if acora.BytesAcora is acora.PyAcora or acora.UnicodeAcora is acora.PyAcora:
    print("WARNING: '_acora' C extension not imported, only testing Python implementation")

import re
import sys
import unittest
import codecs
import string

# compat stuff ...

try:
    unicode
except NameError:
    unicode = str

try:
    bytes
except NameError:
    bytes = str

try:
    # Python 2.6+
    from io import StringIO as _StringIO, BytesIO as _BytesIO
except ImportError:
    # Python 2
    from StringIO import StringIO as _StringIO
    _BytesIO = _StringIO

def BytesIO(*args):
    if args and isinstance(args[0], unicode):
        args = (args[0].encode("UTF-8"),)
    return _BytesIO(*args)

def StringIO(*args):
    if args and isinstance(args[0], bytes):
        args = (args[0].decode("UTF-8"),)
    return _BytesIO(*args)

unicode_unescaper = codecs.lookup("unicode_escape")
def unescape_unicode(s):
    return unicode_unescaper.decode(s)[0]


def prepare_test_data():
    s = ('bdfdaskdjfhaslkdhfsadhfklashdflabcasdabcdJAKHDBVDFLNFCBLSADHFCALKSJ'
        'jklhcnajskbhfasjhancfksjdfhbvaliuradefhzcbdegnashdgfbcjaabesdhgkfcnash'
        'fdkhbdegxcbgjsvdhabcabcfcgbnxahsdbgfbcakjsdhgnfcxsababcmdabe')
    s = s.lower() + s + s.upper()
    search_string = s * 1000

    all_keywords = [
        'ab', 'abc', 'abcd', 'abcabc', 'ababc', 'ABBBC', 'ABCABC',
        'bdfd', 'ade', 'abe', 'bdeg', 'fklash',
        'gnfcxsababcmdabe', 'SADHFCAL',
        'notthere', 'not-to-be-found', 'not-to-be-found-either',
        ]

    if sys.version_info[0] < 3:
        all_keywords = list(map(unicode, all_keywords))
        search_string = unicode(search_string)

    return search_string, all_keywords


class AcoraTest(object):
    search_string, all_keywords = prepare_test_data()

    def _build(self, *keywords):
        keywords = list(map(self._swrap, keywords))
        return acora.AcoraBuilder(*keywords).build(acora=self.acora)

    def _build_ignore_case(self, *keywords):
        keywords = list(map(self._swrap, keywords))
        return acora.AcoraBuilder(*keywords).build(
            ignore_case=True, acora=self.acora)

    def _result(self, result):
        s = self._swrap
        return [ (s(k), pos) for k,pos in result ]

    # basic tests

    def test_finditer_single_keyword(self):
        s = self._swrap
        finditer = self._build('bc').finditer
        self.assertEquals(
            sorted(finditer(s('abcd'))),
            self._result([('bc', 1)]))

    def test_finditer_many_keywords(self):
        s = self._swrap
        finditer = self._build(*string.ascii_letters).finditer
        self.assertEquals(
            sorted(finditer(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2), ('d', 3)]))

    def test_finditer_many_keywords_not_found(self):
        s = self._swrap
        finditer = self._build(*string.ascii_letters).finditer
        self.assertEquals(sorted(finditer(s(string.digits*100))), [])

    def test_finditer_sequential(self):
        s = self._swrap
        finditer = self._build('a', 'b', 'c', 'd').finditer
        self.assertEquals(
            sorted(finditer(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2), ('d', 3)]))

    def test_finditer_redundant(self):
        s = self._swrap
        finditer = self._build('a', 'b', 'A', 'B').finditer
        self.assertEquals(
            sorted(finditer(s('AaBb'))),
            self._result([('A', 0), ('B', 2), ('a', 1), ('b', 3)]))

    def test_finditer_overlap(self):
        s = self._swrap
        finditer = self._build('a', 'ab', 'abc', 'abcd').finditer
        self.assertEquals(
            sorted(finditer(s('abcd'))),
            self._result([('a', 0), ('ab', 0), ('abc', 0), ('abcd', 0)]))

    def test_finditer_reverse_overlap(self):
        s = self._swrap
        finditer = self._build('d', 'cd', 'bcd', 'abcd').finditer
        self.assertEquals(
            sorted(finditer(s('abcd'))),
            self._result([('abcd', 0), ('bcd', 1), ('cd', 2), ('d', 3)]))

    def test_deepcopy_builder(self):
        from copy import deepcopy
        s = self._swrap

        builder1 = acora.AcoraBuilder(*list(map(s, ['a', 'b', 'c'])))
        builder2 = deepcopy(builder1)
        builder2.add(s('ab'), s('bc'))
        
        finditer1 = builder1.build(acora=self.acora).finditer
        finditer2 = builder2.build(acora=self.acora).finditer

        self.assertEquals(
            sorted(finditer1(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2)]))

        self.assertEquals(
            sorted(finditer2(s('abcd'))),
            self._result([('a', 0), ('ab', 0), ('b', 1), ('bc', 1), ('c', 2)]))
        

class UnicodeAcoraTest(unittest.TestCase, AcoraTest):
    # only unicode data tests
    from acora import UnicodeAcora as acora

    def _swrap(self, s):
        if not isinstance(s, unicode):
            s = s.decode('utf-8')
        return unescape_unicode(s)

    def test_finditer_line_endings(self):
        s = self._swrap
        finditer = self._build_ignore_case('a', 'b', 'c', 'd', '\r', '\n').finditer

        line = 0
        line_matches = []
        current_line_matches = []
        last_ending = None
        for kw, pos in finditer(s('Aa\r\nB\nbC\n\rcD\r\nd')):
            if kw in '\r\n':
                if last_ending == '\r' and kw == '\n':
                    continue
                line_matches.append(tuple(current_line_matches))
                del current_line_matches[:]
                last_ending = kw
                line += 1
            else:
                last_ending = None
                current_line_matches.append(kw)

        line_matches.append(tuple(current_line_matches))

        self.assertEquals(line, 5)
        self.assertEquals(
            line_matches,
            [('a', 'a'), ('b',), ('b', 'c'), (), ('c', 'd'), ('d',)])

    def test_finditer_single_keyword_unicode(self):
        s = self._swrap
        finditer = self._build(unicode("\\uF8D2")).finditer
        self.assertEquals(
            list(finditer(s(unicode("\\uF8D1\\uF8D2\\uF8D3")))),
            self._result([(unicode("\\uF8D2"), 1)]))

    def test_finditer_ignore_case(self):
        s = self._swrap
        finditer = self._build_ignore_case('a', 'b', 'c', 'd').finditer
        self.assertEquals(
            sorted(finditer(s('AaBbCcDd'))),
            self._result([('a', 0), ('a', 1), ('b', 2), ('b', 3),
                          ('c', 4), ('c', 5), ('d', 6), ('d', 7)]))

    def test_finditer_ignore_case_redundant(self):
        s = self._swrap
        finditer = self._build_ignore_case('a', 'b', 'A', 'B').finditer
        self.assertEquals(
            sorted(finditer(s('AaBb'))),
            self._result([('A', 0), ('A', 1), ('B', 2), ('B', 3),
                          ('a', 0), ('a', 1), ('b', 2), ('b', 3)]))


class BytesAcoraTest(unittest.TestCase, AcoraTest):
    # only byte data tests
    from acora import BytesAcora as acora

    simple_data = 'abc' + ('a'*100+'b'*100)*1000 + 'abcde'
    simple_kwds = ['abc'.encode('ASCII'),
                   'abcde'.encode('ASCII')]
    last_match_pos = len(simple_data) - 5
    expected_result = [(simple_kwds[0], 0),
                       (simple_kwds[0], last_match_pos),
                       (simple_kwds[1], last_match_pos)]

    def _swrap(self, s):
        if isinstance(s, unicode):
            s = s.encode('utf-8')
        return s

    def _search_in_file(self, ac, data):
        import tempfile
        tmp = tempfile.TemporaryFile()
        try:
            tmp.write(data.encode('ASCII'))
            tmp.seek(0)
            return list(ac.filefind(tmp))
        finally:
            tmp.close()

    def test_large_filelike_searching(self):
        filefind = self._build('SADHFCAL'.encode('ASCII'),
                               'bdeg'.encode('ASCII')).filefind
        data = BytesIO(self.search_string)
        result = list(filefind(data))
        self.assertEquals(len(result), 6000)

    def test_large_filelike_searching_check(self):
        ac = self._build(*self.simple_kwds)
        data = BytesIO(self.simple_data)
        result = list(ac.filefind(data))
        self.assertEquals(result, self.expected_result)

    def test_file_searching(self):
        ac = self._build([ kw.encode('ASCII')
                           for kw in ('a', 'b', 'ab', 'abc') ])
        result = self._search_in_file(ac, 'abbabc')
        self.assertEquals(len(result), 8)

    def test_large_file_searching(self):
        ac = self._build('SADHFCAL'.encode('ASCII'),
                         'bdeg'.encode('ASCII'))
        result = self._search_in_file(ac, self.search_string)
        self.assertEquals(len(result), 6000)

    def test_large_file_searching_check(self):
        ac = self._build(*self.simple_kwds)
        result = self._search_in_file(ac, self.simple_data)
        self.assertEquals(result, self.expected_result)


class PyAcoraTest(UnicodeAcoraTest, BytesAcoraTest):
    # both types of tests work here
    from acora import PyAcora as acora

    def _swrap(self, s):
        if isinstance(s, unicode):
            s = unescape_unicode(s)
        return s


def suite():
    import doctest
    suite = unittest.TestSuite([
            unittest.makeSuite(UnicodeAcoraTest),
            unittest.makeSuite(BytesAcoraTest),
            unittest.makeSuite(PyAcoraTest),
            doctest.DocTestSuite(),
            doctest.DocFileSuite('README.txt'),
            ])
    return suite

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    verbosity = min(2, args.count('-v') + args.count('-vv')*2)
    unittest.TextTestRunner(verbosity=verbosity).run(suite())
