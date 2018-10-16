# cython: binding=True
## cython: profile=True

from __future__ import absolute_import

from copy import deepcopy


class _Machine(object):
    def __init__(self, tree, child_states=None, ignore_case=False):
        self.start_state = tree
        self._child_states = child_states
        self.ignore_case = ignore_case

    @property
    def child_states(self):
        if self._child_states is not None:
            return self._child_states
        seen = set()
        child_states = list(self.start_state.children) if self.start_state.children else []
        for child in child_states:
            if child in seen:
                continue
            seen.add(child)
            child_states.extend(child.children)
        self._child_states = child_states
        return child_states

    def __copy__(self):
        return type(self)(self.start_state, self._child_states, self.ignore_case)

    def __deepcopy__(self, memo):
        start_state = deepcopy(self.start_state, memo)
        return type(self)(start_state, ignore_case=self.ignore_case)

    def __reduce__(self):
        """pickle"""
        return self.__class__, (self.start_state, None, self.ignore_case)


class _MachineState(object):
    """Trie node state for the automaton.
    """
    def __init__(self):
        self.id = 0
        self.letter = u'\0'
        self.children = None
        self.matches = None
        self.fail = None

    def __richcmp__(self, other, cmp_type):
        return _richcmp(self, other, cmp_type)  # only in compiled version

    def __hash__(self):
        return self.id

    def __str__(self):
        return str(self.id)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.id)

    def _copy_with_children(self, children):
        state = _MachineState.__new__(_MachineState)
        state.id = self.id
        state.letter = self.letter
        state.children = children
        state.matches = self.matches[:]
        return state

    def __copy__(self):
        return self._copy_with_children(self.children[:] if self.children else [])

    def __deepcopy__(self, memo):
        return self._copy_with_children(
            [deepcopy(child, memo) for child in self.children] if self.children else [])


def build_MachineState(state_id, matches=None):
    state = _MachineState.__new__(_MachineState)
    state.id = state_id
    state.letter = 0        # only required when not compiled
    state.children = None   # only required when not compiled
    state.matches = [] if matches is None else matches
    return state


def _find_child(state, ch):
    for child in state.children:
        if child.letter == ch:
            return child
    return None


def insert_unicode_keyword(tree, keyword, state_id, ignore_case=False):
    # keep in sync with insert_bytes_keyword()
    if not keyword:
        raise ValueError("cannot search for the empty string")
    for ch in keyword:
        if ignore_case:
            ch = ch.lower()
        if tree.children is None:
            tree.children = []
            child = None
        else:
            child = _find_child(tree, ch)
        if child is None:
            child = build_MachineState(state_id)
            child.letter = ch
            state_id += 1
            tree.children.append(child)
        tree = child
    if ignore_case and tree.matches:
        if keyword not in tree.matches:
            tree.matches.append(keyword)
    else:
        tree.matches = [keyword]
    return state_id


def insert_bytes_keyword(tree, keyword, state_id, ignore_case=False):
    # keep in sync with insert_bytes_keyword()
    if not keyword:
        raise ValueError("cannot search for the empty string")
    for ch in keyword:
        if ignore_case:
            ch = ch.lower()
        if tree.children is None:
            tree.children = []
            child = None
        else:
            child = _find_child(tree, ch)
        if child is None:
            child = build_MachineState(state_id)
            child.letter = ch
            state_id += 1
            tree.children.append(child)
        tree = child
    if ignore_case and tree.matches:
        if keyword not in tree.matches:
            tree.matches.append(keyword)
    else:
        tree.matches = [keyword]
    return state_id


def _sort_by_character(s):
    return s.letter


def _sort_by_lc_character(s):
    return s.letter.lower()


def build_trie(start_state, ignore_case=False):
    if not isinstance(start_state, _MachineState):
        raise ValueError("expected machine state, got %s" % type(start_state).__name__)

    # collect list of all trie states by breadth-first traversal, ordered by character value
    child_states = []

    start_state.fail = start_state
    if not start_state.children:
        # empty trie is boring but fine, too
        start_state.children = []
        return _Machine(start_state, child_states)

    # set up failure links for start states
    start_state.children.sort(key=_sort_by_character)
    child_states.extend(start_state.children)
    for child in start_state.children:
        child.fail = start_state

    # set up failure links for all states
    seen_targets = {}
    for state in child_states:
        if ignore_case and state.matches and len(state.matches) > 1:
            state.matches.sort()  # sort case-insensitive equivalents alphabetically
        if not state.children:
            state.children = []
            continue
        state.children.sort(key=_sort_by_lc_character if ignore_case else _sort_by_character)
        child_states.extend(state.children)
        for child in state.children:
            ch = child.letter
            # find best continue state for this letter
            fail_state = state.fail
            while True:
                fail_child = _find_child(fail_state, ch)
                if fail_child is None and ignore_case:
                    uc = ch.upper()
                    if uc != ch:
                        fail_child = _find_child(fail_state, uc)
                if fail_child is not None:
                    child.fail = fail_child
                    break
                if fail_state is start_state:
                    child.fail = start_state
                    break
                fail_state = fail_state.fail

    return _Machine(start_state, child_states, ignore_case)


def _convert_old_format(transitions):
    """
    Convert old transitions format by extracting all keywords and building a new trie.
    """
    keywords = set()
    ignores_case = True
    ignore_case_matters = False
    for (state, ch), target in transitions.items():
        if state.matches:
            keywords.update(state.matches)
        if target.matches:
            keywords.update(target.matches)
        if ignores_case:
            lower, upper = ch.lower(), ch.upper()
            if lower != upper:
                ignore_case_matters = True
                if ch == lower and (state, upper) not in transitions:
                    ignores_case = False
                elif ch == upper and (state, lower) not in transitions:
                    ignores_case = False
    from . import AcoraBuilder
    ignore_case = ignore_case_matters and ignores_case
    builder = AcoraBuilder(ignore_case=ignore_case)
    builder.update(keywords)

    def _pass_first_arg(s, **kwargs): return s
    return builder.build(acora=_pass_first_arg)


def tree_to_dot(tree, out=None):
    if out is None:
        from sys import stdout as out
    from collections import deque
    write = out.write
    write("digraph {\n")
    remaining = deque([tree])
    seen = set()
    write('%s [label="%s"];\n' % (tree.id, 'start'))
    while remaining:
        state = remaining.popleft()
        if state in seen:
            continue
        seen.add(state)
        if state.fail is not None:
            write('%s -> %s [style=dashed, arrowsize=0.5];\n' % (state.id, state.fail.id))
        if not state.children:
            continue
        remaining.extend(state.children)
        for child in state.children:
            write('%s [label="%s"];\n' % (child.id, _make_printable(child.letter)))
            write('%s -> %s;\n' % (state.id, child.id))
            if child.matches:
                write('M%s [label="%s", shape=note];\n' % (
                    child.id, '\\n'.join([_make_printable(s) for s in child.matches])))
                write('%s -> M%s [style=dotted];\n' % (child.id, child.id))
    write("}\n")


def _make_printable(s):
    if isinstance(s, bytes):
        s = s.decode('latin1')
    b = s.encode('unicode_escape')
    b = b.replace(b'\\', b'\\\\')
    return b.decode('ascii')


def merge_targets(state, ignore_case):
    # merge children failure states and matches to avoid deep failure state traversal
    targets = {}
    if state.children:
        for child in state.children:
            letter = child.letter
            targets[letter] = child
            if ignore_case:
                uc = child.letter.upper()
                if uc != child.letter:
                    targets[uc] = child

    matches = list(state.matches) if state.matches else None
    fail_state = state
    if fail_state.fail is not None:
        while fail_state.fail is not fail_state:  # stop at tree root
            fail_state = fail_state.fail
            if fail_state.matches:
                if matches is None:
                    matches = list(fail_state.matches)
                else:
                    matches.extend(fail_state.matches)
            for child in fail_state.children:
                letter = child.letter
                if letter not in targets:
                    targets[letter] = child
                if ignore_case:
                    uc = child.letter.upper()
                    if uc != child.letter:
                        letter = uc
                        if letter not in targets:
                            targets[letter] = child
    if matches is not None and len(matches) > 1:
        matches.sort(key=len, reverse=True)

    return targets, matches
