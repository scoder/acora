"""
Benchmark comparison between acora search and re.findall()
"""

COMPARED_IMPLEMENTATIONS = ["pa", "ca", "re"]
REPEAT_COUNT = 5

import re
import sys
import timeit
from time import time

from itertools import combinations
from functools import partial

try:
    from pyximport.pyxbuild import pyx_to_dll
except ImportError:
    pass
else:
    so_path = pyx_to_dll('acora/_acora.pyx')
    import os.path
    sys.path.insert(0, os.path.dirname(so_path))

from acora import AcoraBuilder, BytesAcora, UnicodeAcora, PyAcora


def prepare_benchmark_data():
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


def compare_search(s, filename, ignore_case, *keywords):
    setup_pya = setup_cya = setup_re = 0
    run_pa = 'pa' in COMPARED_IMPLEMENTATIONS
    run_ca = 'ca' in COMPARED_IMPLEMENTATIONS
    run_re = 're' in COMPARED_IMPLEMENTATIONS

    if run_pa:
        t = time()
        builder = AcoraBuilder(keywords, ignore_case=ignore_case)
        py_acora = builder.build(acora=PyAcora)
        setup_pya = time() - t
        t = time()
    if run_ca:
        t = time()
        builder = AcoraBuilder(keywords, ignore_case=ignore_case)
        c_acora = builder.build()
        setup_ca = time() - t
    if run_re:
        t = time()
        if hasattr(keywords[0], 'encode'): # unicode in Py3?
            kw_regexp = '|'.join(keywords)
        else:
            kw_regexp = '|'.encode('ASCII').join(keywords)
        if ignore_case:
            regexp = re.compile(kw_regexp, re.I)
        else:
            regexp = re.compile(kw_regexp)
        setup_re = time() - t
    print("Case %ssensitive %s\n- setup times: PA: %.4f, CA: %.4f, RE: %.4f" % (
            ignore_case and 'in' or '',
            builder.for_unicode and 'unicode' or 'bytes',
            setup_pya, setup_ca, setup_re))

    if run_pa:
        timings = timeit.Timer(partial(py_acora.findall, s)).repeat(number=REPEAT_COUNT)
        print("TIME(paS): %.3f" % min(timings))
    if run_ca:
        timings = timeit.Timer(partial(c_acora.findall, s)).repeat(number=REPEAT_COUNT)
        print("TIME(caS): %.3f" % min(timings))
    if filename:
        if run_pa:
            timings = timeit.Timer(partial(py_acora.filefindall, filename)).repeat(number=REPEAT_COUNT)
            print("TIME(paF): %.3f" % min(timings))
        if run_ca:
            timings = timeit.Timer(partial(c_acora.filefindall, filename)).repeat(number=REPEAT_COUNT)
            print("TIME(caF): %.3f" % min(timings))
    if run_re:
        timings = timeit.Timer(partial(regexp.findall, s)).repeat(number=REPEAT_COUNT)
        print("TIME(reS): %.3f" % min(timings))

    return (
        run_pa and py_acora.findall(s) or None,
        run_ca and c_acora.findall(s) or None,
        run_pa and (filename and py_acora.filefindall(filename)) or None,
        run_ca and (filename and c_acora.filefindall(filename)) or None,
        run_re and regexp.findall(s) or None
        )


def run_benchmark(search_string, all_keywords):
    search_string_lower = search_string.lower()
    bytes_search_string = search_string.encode('ASCII')
    bytes_search_string_lower = search_string_lower.encode('ASCII')

    import tempfile
    temp_text_file = tempfile.NamedTemporaryFile()
    temp_text_file.write(bytes_search_string)
    temp_text_file.flush()

    filename = temp_text_file.name

    for i in range(len(all_keywords),0,-1):
        for keywords in combinations(all_keywords, i):
            print('##Keywords(%d): %s' % (len(keywords), ' '.join(sorted(keywords))))
            keywords_lower = [ kw.lower() for kw in keywords ]

            results = compare_search(search_string, None, False, *keywords)
            for result in results[:2]:
                assert_equal(results, result, search_string, keywords)

            results = compare_search(search_string, None, True, *keywords)
            for result in results[:2]:
                assert_equal(results, result, search_string_lower, keywords_lower)

            keywords = [ keyword.encode('ASCII') for keyword in keywords ]

            results = compare_search(bytes_search_string, filename, False, *keywords)
            for result in results[:4]:
                assert_equal(results, result, bytes_search_string, keywords)

            if sys.version_info[0] < 3:
                keywords_lower = [ keyword.encode('ASCII') for keyword in keywords_lower ]
                # case-insensitive search in byte strings is not supported in Py3
                results = compare_search(bytes_search_string, filename, True, *keywords)
                for result in results[:4]:
                    assert_equal(results, result, bytes_search_string_lower, keywords_lower)


def assert_equal(results, result, search_string, keywords):
    if result is None:
        return
    assert len(result) == sum(map(search_string.count, keywords)), \
        "EXPECTED: %d, got %s, %s" % (
            sum(map(search_string.count, keywords)),
            len(result),
            [(len(res) if res is not None else None) for res in results])


if __name__ == '__main__':
    run_benchmark(*prepare_benchmark_data())
