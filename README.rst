Acora
======

.. contents:: :local:

What is Acora?
---------------

Acora is 'fgrep' for Python, a fast multi-keyword text search engine.

Based on a set of keywords, it generates a search automaton (DFA) and
runs it over string input, either unicode or bytes.

It is based on the Aho-Corasick algorithm and an NFA-to-DFA powerset
construction.

Acora comes with both a pure Python implementation and a fast binary
module written in Cython. However, note that the current construction
algorithm is not suitable for really large sets of keywords (i.e. more
than a couple of thousand).

You can find the `latest source code <https://github.com/scoder/acora>`_ on
github.


Features
---------

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
-----------------

Import the package::

    >>> from acora import AcoraBuilder

Collect some keywords::

    >>> builder = AcoraBuilder('ab', 'bc', 'de')
    >>> builder.add('a', 'b')

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


FAQs and recipes
-----------------

#) how do I run a greedy search for the longest matching keywords?

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

#) how do I parse line-by-line, as fgrep does, but with arbitrary line endings?

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


Changelog
----------

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
