"""\
Acora - a multi-keyword search engine based on Aho-Corasick trees.

Usage::

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
"""

from __future__ import absolute_import

import sys
IS_PY3 = sys.version_info[0] >= 3

if IS_PY3:
    unicode = str

FILE_BUFFER_SIZE = 32 * 1024


class PyAcora(object):
    """A simple (and very slow) Python implementation of the Acora
    search engine.
    """
    transitions = None

    def __init__(self, machine, transitions=None):
        if transitions is not None:
            # old style format
            start_state = machine
            self.transitions = dict([
                ((state.id, char), (target_state.id, target_state.matches))
                for ((state, char), target_state) in transitions.items()])
        else:
            # new style Machine format
            start_state = machine.start_state
            ignore_case = machine.ignore_case
            self.transitions = transitions = {}

            child_states = machine.child_states
            child_targets = {}
            state_matches = {}
            needs_bytes_conversion = None
            for state in child_states:
                state_id = state.id
                child_targets[state_id], state_matches[state_id] = (
                    _merge_targets(state, ignore_case))
                if needs_bytes_conversion is None and state_matches[state_id]:
                    if IS_PY3:
                        needs_bytes_conversion = any(
                            isinstance(s, bytes) for s in state_matches[state_id])
                    elif any(isinstance(s, unicode) for s in state_matches[state_id]):
                        # in Py2, some keywords might be str even though we're processing unicode
                        needs_bytes_conversion = False

            if needs_bytes_conversion is None and not IS_PY3:
                needs_bytes_conversion = True
            if needs_bytes_conversion:
                if IS_PY3:
                    convert = ord
                else:
                    from codecs import latin_1_encode

                    def convert(s):
                        return latin_1_encode(s)[0]
            else:
                convert = None

            get_child_targets = child_targets.get
            get_matches = state_matches.get

            state_id = start_state.id
            for ch, child in _merge_targets(start_state, ignore_case)[0].items():
                child_id = child.id
                if convert is not None:
                    ch = convert(ch)
                transitions[(state_id, ch)] = (child_id, get_matches(child_id))

            for state in child_states:
                state_id = state.id
                for ch, child in get_child_targets(state_id).items():
                    child_id = child.id
                    if convert is not None:
                        ch = convert(ch)
                    transitions[(state_id, ch)] = (child_id, get_matches(child_id))

        self.start_state = start_state.id

    def finditer(self, s):
        """Iterate over all occurrences of any keyword in the string.

        Returns (keyword, offset) pairs.
        """
        state = self.start_state
        start_state = (state, [])
        next_state = self.transitions.get
        pos = 0
        for char in s:
            pos += 1
            state, matches = next_state((state, char), start_state)
            if matches:
                for match in matches:
                    yield (match, pos-len(match))

    def findall(self, s):
        """Find all occurrences of any keyword in the string.

        Returns a list of (keyword, offset) pairs.
        """
        return list(self.finditer(s))

    def filefind(self, f):
        """Iterate over all occurrences of any keyword in a file.

        Returns (keyword, offset) pairs.
        """
        opened = False
        if not hasattr(f, 'read'):
            f = open(f, 'rb')
            opened = True

        try:
            state = self.start_state
            start_state = (state, ())
            next_state = self.transitions.get
            pos = 0
            while 1:
                data = f.read(FILE_BUFFER_SIZE)
                if not data:
                    break
                for char in data:
                    pos += 1
                    state, matches = next_state((state, char), start_state)
                    if matches:
                        for match in matches:
                            yield (match, pos-len(match))
        finally:
            if opened:
                f.close()

    def filefindall(self, f):
        """Find all occurrences of any keyword in a file.

        Returns a list of (keyword, offset) pairs.
        """
        return list(self.filefind(f))


# import from shared Python/Cython module
from acora._acora import (
    insert_bytes_keyword, insert_unicode_keyword,
    build_trie as _build_trie, build_MachineState as _MachineState, merge_targets as _merge_targets)

# import from Cython module if available
try:
    from acora._cacora import (
        UnicodeAcora, BytesAcora, insert_bytes_keyword, insert_unicode_keyword)
except ImportError:
    # C module not there ...
    UnicodeAcora = BytesAcora = PyAcora


class AcoraBuilder(object):
    """The main builder class for an Acora search engine.

    Add keywords by calling ``.add(*keywords)`` or by passing them
    into the constructor. Then build the search engine by calling
    ``.build()``.

    Builds a case insensitive search engine when passing
    ``ignore_case=True``, and a case sensitive engine otherwise.
    """
    ignore_case = False

    def __init__(self, *keywords, **kwargs):
        if kwargs:
            self.ignore_case = kwargs.pop('ignore_case', False)
            if kwargs:
                raise TypeError(
                    "%s() got unexpected keyword argument %s" % (
                        self.__class__.__name__, next(iter(kwargs))))

        if len(keywords) == 1 and isinstance(keywords[0], (list, tuple)):
            keywords = keywords[0]
        self.for_unicode = None
        self.state_counter = 1
        self.keywords = set()
        self.tree = _MachineState(0)
        if keywords:
            self.update(keywords)

    def __update(self, keywords):
        """Add more keywords to the search engine builder.

        Adding keywords does not impact previously built search
        engines.
        """
        if not keywords:
            return
        self.tree = None
        self.keywords.update(keywords)
        if self.for_unicode is None:
            for keyword in keywords:
                if isinstance(keyword, unicode):
                    self.for_unicode = True
                elif isinstance(keyword, bytes):
                    self.for_unicode = False
                else:
                    raise TypeError(
                        "keywords must be either bytes or unicode, not mixed (got %s)" %
                        type(keyword))
                break
        # validate input string types
        marker = object()
        if self.for_unicode:
            for keyword in keywords:
                if not isinstance(keyword, unicode):
                    break
            else:
                keyword = marker
        else:
            for keyword in keywords:
                if not isinstance(keyword, bytes):
                    break
            else:
                keyword = marker
        if keyword is not marker:
            raise TypeError(
                "keywords must be either bytes or unicode, not mixed (got %s)" %
                type(keyword))

    def add(self, *keywords):
        """Add more keywords to the search engine builder.

        Adding keywords does not impact previously built search
        engines.
        """
        if keywords:
            self.update(keywords)

    def build(self, ignore_case=None, acora=None):
        """Build a search engine from the aggregated keywords.

        Builds a case insensitive search engine when passing
        ``ignore_case=True``, and a case sensitive engine otherwise.
        """
        if acora is None:
            if self.for_unicode:
                acora = UnicodeAcora
            else:
                acora = BytesAcora

        if self.for_unicode == False and ignore_case:
            import sys
            if sys.version_info[0] >= 3:
                raise ValueError(
                    "Case insensitive search is not supported for byte strings in Python 3")

        if ignore_case is not None and ignore_case != self.ignore_case:
            # must rebuild tree
            builder = type(self)(ignore_case=ignore_case)
            builder.update(self.keywords)
            return builder.build(acora=acora)

        return acora(_build_trie(self.tree, ignore_case=self.ignore_case))

    def update(self, keywords):
        for_unicode = self.for_unicode
        ignore_case = self.ignore_case
        insert_keyword = insert_unicode_keyword if for_unicode else insert_bytes_keyword
        for keyword in keywords:
            if for_unicode is None:
                for_unicode = self.for_unicode = isinstance(keyword, unicode)
                insert_keyword = (
                    insert_unicode_keyword if for_unicode else insert_bytes_keyword)
            elif for_unicode != isinstance(keyword, unicode):
                raise TypeError(
                    "keywords must be either bytes or unicode, not mixed (got %s)" %
                    type(keyword))
            self.state_counter = insert_keyword(
                self.tree, keyword, self.state_counter, ignore_case)
        self.keywords.update(keywords)


### convenience functions

def search(s, *keywords):
    """Convenience function to search a string for keywords.
    """
    acora = AcoraBuilder(keywords).build()
    return acora.findall(s)


def search_ignore_case(s, *keywords):
    """Convenience function to search a string for keywords.  Case
    insensitive version.
    """
    acora = AcoraBuilder(keywords, ignore_case=True).build()
    return acora.findall(s)
