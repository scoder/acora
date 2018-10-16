Acora
=====

.. contents:: :local:

What is Acora?
--------------

Acora is 'fgrep' for Python, a fast multi-keyword text search engine.

Based on a set of keywords and the
`Aho-Corasick algorithm <https://en.wikipedia.org/wiki/Aho-Corasick_algorithm>`_,
it generates a search automaton and runs it over string input, either unicode
or bytes.

Acora comes with both a pure Python implementation and a fast binary
module written in Cython.  However, note that the current construction
algorithm is not suitable for really large sets of keywords (i.e. more
than a couple of thousand).

You can find the `latest source code <https://github.com/scoder/acora>`_
on github.

To report a bug or request new features, use the `github bug tracker
<https://github.com/scoder/acora/issues>`_.  Please try to provide a
short test case that reproduces the problem without requiring too much
experimentation or large amounts of data.  The easier it is to
reproduce the problem, the easier it is to solve it.


Features
--------

* works with unicode strings and byte strings
* about 2-3x as fast as Python's regular expression engine for most input
* finds overlapping matches, i.e. all matches of all keywords
* support for case insensitive search (~10x as fast as 're')
* frees the GIL while searching
* additional (slow but short) pure Python implementation
* support for Python 2.5+ and 3.x
* support for searching in files
* permissive BSD license


How do I use it?
----------------

Import the package::

    >>> from acora import AcoraBuilder

Collect some keywords::

    >>> builder = AcoraBuilder('ab', 'bc', 'de')
    >>> builder.add('a', 'b')

Or::

    >>> builder.update(['a', 'b'])  # new in version 2.0

Generate the Acora search engine for the current keyword set::

    >>> ac = builder.build()

Search a string for all occurrences::

    >>> ac.findall('abc')
    [('a', 0), ('ab', 0), ('b', 1), ('bc', 1)]
    >>> ac.findall('abde')
    [('a', 0), ('ab', 0), ('b', 1), ('de', 2)]

Iterate over the search results as they come in::

    >>> for kw, pos in ac.finditer('abde'):
    ...     print("%2s[%d]" % (kw, pos))
     a[0]
    ab[0]
     b[1]
    de[2]

Acora also has direct support for parsing files (in binary mode)::

    >>> keywords = ['Import', 'FAQ', 'Acora', 'NotHere'.upper()]

    >>> builder = AcoraBuilder([s.encode('ascii') for s in keywords])
    >>> ac = builder.build()

    >>> found = set(kw for kw, pos in ac.filefind('README.rst'))
    >>> len(found)
    3

    >>> sorted(str(s.decode('ascii')) for s in found)
    ['Acora', 'FAQ', 'Import']


FAQs and recipes
----------------

#) How do I run a greedy search for the longest matching keywords?

   ::

       >>> builder = AcoraBuilder('a', 'ab', 'abc')
       >>> ac = builder.build()

       >>> for kw, pos in ac.finditer('abbabc'):
       ...     print(kw)
       a
       ab
       a
       ab
       abc

       >>> from itertools import groupby
       >>> from operator import itemgetter

       >>> def longest_match(matches):
       ...     for pos, match_set in groupby(matches, itemgetter(1)):
       ...         yield max(match_set)

       >>> for kw, pos in longest_match(ac.finditer('abbabc')):
       ...     print(kw)
       ab
       abc

   Note that this recipe assumes search terms that do not have inner
   overlaps apart from their prefix.

#) How do I parse line-by-line with arbitrary line endings?

       >>> def group_by_lines(s, *keywords):
       ...     builder = AcoraBuilder('\r', '\n', *keywords)
       ...     ac = builder.build()
       ...
       ...     current_line_matches = []
       ...     last_ending = None
       ...
       ...     for kw, pos in ac.finditer(s):
       ...         if kw in '\r\n':
       ...             if last_ending == '\r' and kw == '\n':
       ...                 continue # combined CRLF
       ...             yield tuple(current_line_matches)
       ...             del current_line_matches[:]
       ...             last_ending = kw
       ...         else:
       ...             last_ending = None
       ...             current_line_matches.append(kw)
       ...     yield tuple(current_line_matches)

       >>> kwds = ['ab', 'bc', 'de']
       >>> for matches in group_by_lines('a\r\r\nbc\r\ndede\n\nab', *kwds):
       ...     print(matches)
       ()
       ()
       ('bc',)
       ('de', 'de')
       ()
       ('ab',)


#) How do I find whole lines that contain keywords, as fgrep does?

       >>> def match_lines(s, *keywords):
       ...     builder = AcoraBuilder('\r', '\n', *keywords)
       ...     ac = builder.build()
       ...
       ...     line_start = 0
       ...     matches = False
       ...     for kw, pos in ac.finditer(s):
       ...         if kw in '\r\n':
       ...             if matches:
       ...                  yield s[line_start:pos]
       ...                  matches = False
       ...             line_start = pos + 1
       ...         else:
       ...             matches = True
       ...     if matches:
       ...         yield s[line_start:]

       >>> kwds = ['x', 'de', '\nstart']
       >>> text = 'a line with\r\r\nsome text\r\ndede\n\nab\n start 1\nstart\n'
       >>> for line in match_lines(text, *kwds):
       ...     print(line)
       some text
       dede
       start


Changelog
---------

* 2.2 [2018-08-16]

  - Update to work with CPython 3.7 by building with Cython 0.29.

* 2.1 [2017-12-15]

  - fix handling of empty engines (Github issue #18)

* 2.0 [2016-03-17]

  - rewrite of the construction algorithm to speed it up and save memory

* 1.9 [2015-10-10]

  - recompiled with Cython 0.23.4 for better compatibility with recent
    Python versions.

* 1.8 [2014-02-12]

  - pickle support for the pre-built search engines
  - performance optimisations in builder
  - Unicode parsing is optimised for Python 3.3 and later
  - no longer recompiles sources when Cython is installed, unless
    ``--with-cython`` option is passed to setup.py (requires Cython 0.20+)
  - build failed with recent Cython versions
  - built using Cython 0.20.1

* 1.7 [2011-08-24]

  - searching binary strings for byte values > 127 was broken
  - built using Cython 0.15+

* 1.6 [2011-07-24]

  - substantially faster automaton building
  - no longer includes .hg repo in source distribution
  - built using Cython 0.15 (rc0)

* 1.5 [2011-01-24]

  - Cython compiled NFA-2-DFA construction runs substantially faster
  - always build extension modules even if Cython is not installed
  - ``--no-compile`` switch in ``setup.py`` to prevent extension module building
  - built using Cython 0.14.1 (rc2)

* 1.4 [2009-02-10]

  - minor speed-up in inner search engine loop
  - some code cleanup
  - built using Cython 0.12.1 (final)

* 1.3 [2009-01-30]

  - major fix for file search
  - built using Cython 0.12.1 (beta0)

* 1.2 [2009-01-30]

  - deep-copy support for AcoraBuilder class
  - doc/test fixes
  - include .hg repo in source distribution
  - built using Cython 0.12.1 (beta0)

* 1.1 [2009-01-29]

  - doc updates
  - some cleanup
  - built using Cython 0.12.1 (beta0)

* 1.0 [2009-01-29]

  - initial release
