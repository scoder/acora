"""
Simple test suite for acora.
"""

import acora

import re
import sys
import unittest
import codecs

try:
    unicode
except NameError:
    unicode = str

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

    # unicode tests


class UnicodeAcoraTest(unittest.TestCase, AcoraTest):
    # only unicode data tests
    from acora import UnicodeAcora as acora

    def _swrap(self, s):
        if not isinstance(s, unicode):
            s = s.decode('utf-8')
        return unescape_unicode(s)

    def test_finditer_single_keyword_unicode(self):
        s = self._swrap
        finditer = self._build(unicode("\\uF8D2")).finditer
        self.assertEquals(
            list(finditer(s(unicode("\\uF8D1\\uF8D2\\uF8D3")))),
            self._result([(unicode("\\uF8D2"), 1)]))


class BytesAcoraTest(unittest.TestCase, AcoraTest):
    # only byte data tests
    from acora import BytesAcora as acora

    def _swrap(self, s):
        if isinstance(s, unicode):
            s = s.encode('utf-8')
        return s


class PyAcoraTest(UnicodeAcoraTest, BytesAcoraTest):
    # both types of tests work here
    from acora import PyAcora as acora

    def _swrap(self, s):
        if isinstance(s, unicode):
            s = unescape_unicode(s)
        return s


if __name__ == "__main__":
    import doctest
    doctest.testmod()
    doctest.testfile('README.txt')
    unittest.main()
