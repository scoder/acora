Acora
======

Author: Stefan Behnel


What is Acora?
---------------

Acora is 'fgrep' for Python, a fast multi-keyword text search engine.

Based on a set of keywords, it generates a search automaton (DFA) and
runs it over string input, either unicode or bytes.

It is based on the Aho-Corasick algorithm and an NFA-to-DFA
transformation.


Features
---------

* works with unicode strings and byte strings
* about 2-3x as fast as Python's regular expression engine
* finds overlapping matches, i.e. all matches of all keywords
* support for case insensitive search (~10x as fast as 're')
* frees the GIL while searching
* additional (slow but short) pure Python implementation
* support for Python 2.5+ and 3.x
* support for searching in files

How do I use it?
-----------------

Import the package::

    >>> from acora import AcoraBuilder

Collect some keywords::

    >>> builder = AcoraBuilder('ab', 'bc', 'de')
    >>> builder.add('a', 'b')

Generate the Acora search engine::

    >>> ac = builder.build()

Search a string for all occurrences::

    >>> ac.findall('abc')
    [('a', 0), ('ab', 0), ('b', 1), ('bc', 1)]
    >>> ac.findall('abde')
    [('a', 0), ('ab', 0), ('b', 1), ('de', 2)]


Changelog
----------

* 1.1 [2009-01-29]
  doc updates, some cleanup, built using Cython 0.12.1
* 1.0 [2009-01-29]
  initial release
