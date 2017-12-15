"""
Simple test suite for acora.
"""

import acora

DOTDEBUG = False  # False

if acora.BytesAcora is acora.PyAcora or acora.UnicodeAcora is acora.PyAcora:
    print("WARNING: '_acora' C extension not imported, only testing Python implementation")

try:
    from acora._acora import tree_to_dot
except ImportError:
    tree_to_dot = lambda x: None

try:
    from acora._cacora import machine_to_dot
except ImportError:
    machine_to_dot = lambda x: None

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
        builder = acora.AcoraBuilder(*keywords)
        if DOTDEBUG:
            print('Initial tree:')
            tree_to_dot(builder.tree)
        machine = builder.build(acora=self.acora)
        if DOTDEBUG:
            print('\nProcessed tree:')
            tree_to_dot(builder.tree)
            if not isinstance(machine, acora.PyAcora):
                print('\nMachine:')
                machine_to_dot(machine)
        return machine

    def _build_ignore_case(self, *keywords):
        keywords = list(map(self._swrap, keywords))
        builder = acora.AcoraBuilder(*keywords, ignore_case=True)
        if DOTDEBUG:
            print('Initial tree:')
            tree_to_dot(builder.tree)
        machine = builder.build(acora=self.acora)
        if DOTDEBUG:
            print('\nProcessed tree:')
            tree_to_dot(builder.tree)
            if not isinstance(machine, acora.PyAcora):
                print('\nMachine:')
                machine_to_dot(machine)
        return machine

    def _result(self, result):
        s = self._swrap
        return [(s(k), pos) for k,pos in result]

    # basic tests

    def test_finditer_empty(self):
        s = self._swrap
        finditer = self._build().finditer
        self.assertEqual(
            sorted(finditer(s('abcd'))),
            self._result([]))

    def test_finditer_single_keyword(self):
        s = self._swrap
        finditer = self._build('bc').finditer
        self.assertEqual(
            sorted(finditer(s('abcd'))),
            self._result([('bc', 1)]))

    def test_finditer_many_keywords(self):
        s = self._swrap
        finditer = self._build(*string.ascii_letters).finditer
        self.assertEqual(
            sorted(finditer(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2), ('d', 3)]))

    def test_finditer_many_keywords_not_found(self):
        s = self._swrap
        finditer = self._build(*string.ascii_letters).finditer
        self.assertEqual(sorted(finditer(s(string.digits*100))), [])

    def test_finditer_sequential(self):
        s = self._swrap
        finditer = self._build('a', 'b', 'c', 'd').finditer
        self.assertEqual(
            sorted(finditer(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2), ('d', 3)]))

    def test_finditer_redundant(self):
        s = self._swrap
        finditer = self._build('a', 'b', 'A', 'B').finditer
        self.assertEqual(
            sorted(finditer(s('AaBb'))),
            self._result([('A', 0), ('B', 2), ('a', 1), ('b', 3)]))

    def test_finditer_overlap(self):
        s = self._swrap
        finditer = self._build('a', 'ab', 'abc', 'abcd').finditer
        self.assertEqual(
            sorted(finditer(s('abcd'))),
            self._result([('a', 0), ('ab', 0), ('abc', 0), ('abcd', 0)]))

    def test_finditer_reverse_overlap(self):
        s = self._swrap
        finditer = self._build('d', 'cd', 'bcd', 'abcd').finditer
        self.assertEqual(
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

        self.assertEqual(
            sorted(finditer1(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2)]))

        self.assertEqual(
            sorted(finditer2(s('abcd'))),
            self._result([('a', 0), ('ab', 0), ('b', 1), ('bc', 1), ('c', 2)]))

    def test_deepcopy_machine(self):
        from copy import deepcopy
        s = self._swrap

        builder = acora.AcoraBuilder(*list(map(s, ['a', 'b', 'c'])))
        ac1 = builder.build(acora=self.acora)
        ac2 = deepcopy(ac1)

        self.assertEqual(
            sorted(ac1.finditer(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2)]))

        self.assertEqual(
            sorted(ac2.finditer(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2)]))

    def test_pickle_machine(self):
        import pickle
        s = self._swrap

        builder = acora.AcoraBuilder(*list(map(s, ['a', 'b', 'c'])))
        ac1 = builder.build(acora=self.acora)
        #if not isinstance(ac1, acora.PyAcora):
        #    machine_to_dot(ac1)
        ac2 = pickle.loads(pickle.dumps(ac1))
        #if not isinstance(ac2, acora.PyAcora):
        #    machine_to_dot(ac2)

        self.assertEqual(
            sorted(ac1.finditer(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2)]))

        self.assertEqual(
            sorted(ac2.finditer(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2)]))

    def test_pickle2_machine(self):
        import pickle
        s = self._swrap

        builder = acora.AcoraBuilder(*list(map(s, ['a', 'b', 'c'])))
        ac1 = builder.build(acora=self.acora)
        #if not isinstance(ac1, acora.PyAcora):
        #    machine_to_dot(ac1)
        ac2 = pickle.loads(pickle.dumps(ac1, protocol=pickle.HIGHEST_PROTOCOL))
        #if not isinstance(ac2, acora.PyAcora):
        #    machine_to_dot(ac2)

        self.assertEqual(
            sorted(ac1.finditer(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2)]))

        self.assertEqual(
            sorted(ac2.finditer(s('abcd'))),
            self._result([('a', 0), ('b', 1), ('c', 2)]))

    def test_pickle_machine_new(self):
        s = self._swrap

        builder = acora.AcoraBuilder(*list(map(s, ['a', 'bc', 'c'])))
        ac = builder.build(acora=self.acora)
        #if not isinstance(ac, acora.PyAcora):
        #    machine_to_dot(ac)

        import pickle
        p = pickle.dumps(ac)

        del builder, ac
        import gc
        gc.collect()

        ac = pickle.loads(p)
        #if not isinstance(ac, acora.PyAcora):
        #    machine_to_dot(ac)
        self.assertEqual(
            sorted(ac.finditer(s('abcd'))),
            self._result([('a', 0), ('bc', 1), ('c', 2)]))


class UnicodeAcoraTest(unittest.TestCase, AcoraTest):
    # only unicode data tests
    from acora import UnicodeAcora as acora

    def _swrap(self, s):
        if isinstance(s, unicode):
            s = s.encode('ascii')
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

        self.assertEqual(line, 5)
        self.assertEqual(
            line_matches,
            [('a', 'a'), ('b',), ('b', 'c'), (), ('c', 'd'), ('d',)])

    def test_finditer_single_keyword_unicode(self):
        s = self._swrap
        finditer = self._build("\\uF8D2").finditer
        self.assertEqual(
            list(finditer(s("\\uF8D1\\uF8D2\\uF8D3"))),
            self._result([("\\uF8D2", 1)]))

    def test_finditer_single_keyword_non_bmp(self):
        s = self._swrap
        finditer = self._build("\\U0001F8D2").finditer
        self.assertEqual(
            list(finditer(s("\\U0001F8D1\\U0001F8D2\\uF8D3"))),
            self._result([("\\U0001F8D2", 1)]))

    def test_finditer_ignore_case_single_char(self):
        s = self._swrap
        finditer = self._build_ignore_case('a', 'b', 'c', 'd').finditer
        self.assertEqual(
            sorted(finditer(s('AaBbCcDd'))),
            self._result([('a', 0), ('a', 1), ('b', 2), ('b', 3),
                          ('c', 4), ('c', 5), ('d', 6), ('d', 7)]))

    def test_finditer_ignore_case_words(self):
        s = self._swrap
        finditer = self._build_ignore_case('aAbb', 'bc', 'cc', 'Cd', 'ccD', 'bbb', 'cB').finditer
        self.assertEqual(
            sorted(finditer(s('AaBbCcDd'))),
            self._result([('Cd', 5), ('aAbb', 0), ('bc', 3), ('cc', 4), ('ccD', 4)]))

    def test_finditer_ignore_case_redundant(self):
        s = self._swrap
        finditer = self._build_ignore_case('a', 'b', 'A', 'B').finditer
        self.assertEqual(
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
            s = s.encode('ISO-8859-1')
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

    def test_filefind_empty(self):
        filefind= self._build().filefind
        data = BytesIO(self.search_string)
        self.assertEqual(list(filefind(data)), [])

    def test_large_filelike_searching(self):
        filefind = self._build('SADHFCAL'.encode('ASCII'),
                               'bdeg'.encode('ASCII')).filefind
        data = BytesIO(self.search_string)
        result = list(filefind(data))
        self.assertEqual(len(result), 6000)

    def test_large_filelike_searching_check(self):
        ac = self._build(*self.simple_kwds)
        data = BytesIO(self.simple_data)
        result = list(ac.filefind(data))
        self.assertEqual(result, self.expected_result)

    def test_file_searching(self):
        ac = self._build([ kw.encode('ASCII')
                           for kw in ('a', 'b', 'ab', 'abc') ])
        result = self._search_in_file(ac, 'abbabc')
        self.assertEqual(len(result), 8)

    def test_large_file_searching(self):
        ac = self._build('SADHFCAL'.encode('ASCII'),
                         'bdeg'.encode('ASCII'))
        result = self._search_in_file(ac, self.search_string)
        self.assertEqual(len(result), 6000)

    def test_large_file_searching_check(self):
        ac = self._build(*self.simple_kwds)
        result = self._search_in_file(ac, self.simple_data)
        self.assertEqual(result, self.expected_result)

    def test_binary_data_search(self):
        pattern = self._swrap('\xa5\x66\x80')
        ac = self._build(pattern)
        mainString = self._swrap(10 * '\xf0') + pattern + self._swrap(10 * '\xf0')
        result = ac.findall(mainString)
        self.assertEqual(result, [(pattern, 10)])

    def test_binary_data_search_start(self):
        pattern = self._swrap('\xa5\x66\x80')
        ac = self._build(pattern)
        mainString = pattern + self._swrap(10 * '\xf0')
        result = ac.findall(mainString)
        self.assertEqual(result, [(pattern, 0)])

    def test_binary_data_search_end(self):
        pattern = self._swrap('\xa5\x66\x80')
        ac = self._build(pattern)
        mainString = self._swrap(10 * '\xf0') + pattern
        result = ac.findall(mainString)
        self.assertEqual(result, [(pattern, 10)])


class PyUnicodeAcoraTest(UnicodeAcoraTest):
    from acora import PyAcora as acora


class PyBytesAcoraTest(BytesAcoraTest):
    from acora import PyAcora as acora


def suite():
    import doctest
    tests = unittest.TestSuite([
        unittest.makeSuite(UnicodeAcoraTest),
        unittest.makeSuite(PyUnicodeAcoraTest),
        unittest.makeSuite(BytesAcoraTest),
        unittest.makeSuite(PyBytesAcoraTest),
        doctest.DocTestSuite(),
        doctest.DocFileSuite('README.rst'),
    ])
    return tests


if __name__ == "__main__":
    args = sys.argv[1:]
    verbosity = min(2, args.count('-v') + args.count('-vv')*2)
    unittest.TextTestRunner(verbosity=verbosity).run(suite())
