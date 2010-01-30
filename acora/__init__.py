"""\
Acora - a multi-keyword search engine based on Aho-Corasick trees
and NFA2DFA powerset construction.

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

try:
    unicode
except NameError:
    unicode = str

FILE_BUFFER_SIZE = 32 * 1024

class PyAcora(object):
    """A simple (and very slow) Python implementation of the Acora
    search engine.
    """
    def __init__(self, start_state, transitions):
        self.start_state = start_state.id
        self.transitions = dict([
                ((state.id, char), (target_state.id, target_state.matches))
                for ((state, char), target_state) in transitions.items() ])

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
            state, matches = next_state((state,char), start_state)
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
                    state, matches = next_state((state,char), start_state)
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

try:
    from acora._acora import UnicodeAcora, BytesAcora
except ImportError:
    # C module not there ...
    UnicodeAcora = BytesAcora = PyAcora

class AcoraBuilder(object):
    """The main builder class for an Acora search engine.

    Add keywords by calling ``.add(*keywords)`` or by passing them
    into the constructor. Then build the search engine by calling
    ``.build()``.
    """
    def __init__(self, *keywords):
        if len(keywords) == 1 and isinstance(keywords[0], (list, tuple)):
            keywords = keywords[0]
        self.for_unicode = None
        self.keywords = list(keywords)
        self.state_counter = 1
        self.tree = NfaState(0)
        self._insert_all(self.keywords)

    def add(self, *keywords):
        """Add more keywords to the search engine builder.

        Adding keywords does not impact previously built search
        engines.
        """
        self.keywords.extend(keywords)
        self._insert_all(keywords)

    def build(self, ignore_case=False, acora=None):
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
                raise ValueError("Case insensitive search is not supported for byte strings in Python 3")
        return acora(*nfa2dfa(self.tree, ignore_case))

    def _insert_all(self, keywords):
        for keyword in keywords:
            if self.for_unicode is None:
                self.for_unicode = isinstance(keyword, unicode)
            elif self.for_unicode != isinstance(keyword, unicode):
                raise TypeError(
                    "keywords must be either bytes or unicode, not mixed (got %s)" %
                    type(keyword))
            self.state_counter = insert_keyword(
                self.tree, keyword, self.state_counter)


# initial graph representation of the automaton

class NfaState(dict):
    """NFA state for the untransformed automaton.
    """
    def __new__(cls, state_id, *args, **kwargs):
        state = dict.__new__(cls, *args, **kwargs)
        state.id = state_id
        state.matches = []
        return state

    def __init__(self, state_id, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def __lt__(self, other):
        return self.id < other.id

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return self.id

    def __str__(self):
        return str(self.id)
    __repr__ = __str__

    def __copy__(self):
        state = NfaState(self.id, **self)
        state.matches[:] = self.matches
        return state

    def __deepcopy__(self, memo):
        state = NfaState(
            self.id,
            [ (char, state.__deepcopy__(None))
              for char, state in self.items() ])
        state.matches[:] = self.matches
        return state

def insert_keyword(tree, keyword, state_id):
    if not keyword:
        raise ValueError("cannot search for the empty string")
    for char in keyword:
        if char in tree:
            tree = tree[char]
        else:
            next_node = NfaState(state_id)
            state_id += 1
            tree[char] = next_node
            tree = next_node
    tree.matches = [keyword]
    return state_id

# NFA to DFA transformation

def nfa2dfa(tree, ignore_case):
    """Transform a keyword tree into a DFA using powerset construction.
    """
    def visit_all(tree, visitor):
        visitor(tree)
        for node in tree.values():
            visit_all(node, visitor)

    states = []
    visit_all(tree, states.append)
    next_state_id = len(states)

    # run through all states and collect all transitions, including
    # those from the start state (in which the NFA always stays)
    transitions = {}
    chars_by_state = {}
    new_eq_classes = set()
    for state in states:
        chars = chars_by_state[state] = set()
        for char, target in state.items():
            if ignore_case:
                char = char.lower()
            transitions[(state,char)] = set([target])
            chars.add(char)
        for char, target in tree.items():
            if ignore_case:
                char = char.lower()
            chars.add(char)
            key = (state,char)
            if key in transitions:
                transitions[key].add(target)
                new_eq_classes.add(key)
            else:
                transitions[key] = set([target])

    # create new states for newly found equivalence classes
    existing_eq_classes = {}
    eq_classes_by_state = {}
    while new_eq_classes:
        eq_classes = new_eq_classes
        new_eq_classes = set()
        for key in eq_classes:
            eq_states = transitions[key]
            if len(eq_states) < 2:
                continue
            eq_key = tuple(sorted([s.id for s in eq_states]))
            if eq_key in existing_eq_classes:
                transitions[key] = set([existing_eq_classes[eq_key]])
                continue

            # create a new joined state
            new_state = NfaState(next_state_id)

            matches = []
            for s in eq_states:
                matches.extend(s.matches)
            matches.sort(key=len, reverse=True)
            new_state.matches = matches

            eq_classes_by_state[new_state] = eq_states
            existing_eq_classes[eq_key] = new_state
            next_state_id += 1

            # redirect the original transition to the new node
            transitions[key] = set([new_state])

            # collect its transitions
            new_chars = chars_by_state[new_state] = set()
            for state in eq_states:
                chars = chars_by_state[state]
                new_chars.update(chars)
                for char in chars:
                    # resolve original states from equivalence class states
                    targets = set()
                    for target in transitions[(state,char)]:
                        if target in eq_classes_by_state:
                            targets.update(eq_classes_by_state[target])
                        else:
                            targets.add(target)
                    new_key = (new_state,char)
                    if new_key in transitions:
                        transitions[new_key].update(targets)
                    else:
                        transitions[new_key] = set(targets)
                    new_eq_classes.add(new_key)

    # rebuild transitions dict to point to exactly one state
    for key, state_set in transitions.items():
        assert len(state_set) == 1
        transitions[key] = tuple(state_set)[0]

    # duplicate the transitions for case insensitive parsing
    if ignore_case:
        for (state,char), target in list(transitions.items()):
            transitions[(state,char.upper())] = target

    # return start state and transitions
    return tree, transitions


### convenience functions

def search(s, *keywords):
    """Convenience function to search a string for keywords.
    """
    acora  = AcoraBuilder(keywords).build()
    return acora.findall(s)

def search_ignore_case(s, *keywords):
    """Convenience function to search a string for keywords.  Case
    insensitive version.
    """
    acora  = AcoraBuilder(keywords).build(ignore_case=True)
    return acora.findall(s)
