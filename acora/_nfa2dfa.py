#cython: language_level=3

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


try:
    from acora._acora import build_NfaState as NfaState
except ImportError:
    # no C implementation there
    pass


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

def _collect(tree, collected):
    collected.append(tree)
    for node in tree.values():
        _collect(node, collected)


def nfa2dfa(tree, ignore_case):
    """Transform a keyword tree into a DFA using powerset construction.
    """
    states = []
    _collect(tree, states)
    next_state_id = len(states)

    # run through all states and collect all transitions, including
    # those from the start state (in which the NFA always stays)
    transitions = {}
    chars_by_state = {}
    new_eq_classes = set()
    start_state_transitions = list(tree.items())
    for state in states:
        chars = chars_by_state[state] = set()
        for char, target in state.items():
            if ignore_case:
                char = char.lower()
            transitions[(state, char)] = [target]
            chars.add(char)
        for char, target in start_state_transitions:
            if ignore_case:
                char = char.lower()
            chars.add(char)
            key = (state, char)
            t = transitions.get(key)
            if t is None:
                transitions[key] = [target]
            elif target not in t:
                # more than one target for this transition found
                new_eq_classes.add(key)
                t.append(target)

    # create new states for newly found equivalence classes
    existing_eq_classes = {}
    eq_classes_by_state = {}
    while new_eq_classes:
        eq_classes = new_eq_classes
        new_eq_classes = set()
        for key in eq_classes:
            eq_states = frozenset(transitions[key])
            if len(eq_states) < 2:
                continue
            if eq_states in existing_eq_classes:
                transitions[key] = [existing_eq_classes[eq_states]]
                continue

            # create a new joined state
            new_state = NfaState(next_state_id)

            eq_classes_by_state[new_state] = eq_states
            existing_eq_classes[eq_states] = new_state
            next_state_id += 1

            # redirect the original transition to the new node
            transitions[key] = [new_state]

            # collect its transitions and matches
            matches = []
            new_chars = chars_by_state[new_state] = set()
            for state in eq_states:
                if state.matches:
                    matches.extend(state.matches)
                transition_chars = chars_by_state[state]
                new_chars.update(transition_chars)
                for char in transition_chars:
                    # resolve original states from equivalence class states
                    added = False
                    new_key = (new_state, char)
                    old_targets = transitions.setdefault(new_key, [])
                    for target in transitions[(state, char)]:
                        for t in eq_classes_by_state.get(target, (target,)):
                            if t not in old_targets:
                                old_targets.append(t)
                                added = True
                    if added and len(old_targets) > 1:
                        new_eq_classes.add(new_key)

            if matches:
                # sort longest match first to assure left-to-right match order
                if len(matches) > 1:
                    matches.sort(key=len, reverse=True)
                new_state.matches = matches

    new_eq_classes = existing_eq_classes = eq_classes_by_state = None

    # rebuild transitions dict to point to exactly one state
    targets = set()
    for key, state_set in transitions.items():
        assert len(state_set) == 1
        target = transitions[key] = state_set[0]
        targets.add(target)

    # prune unreachable states (completely replaced by equivalence classes)
    unreachable = set()
    while True:
        targets.add(tree)
        for key in transitions:
            if key[0] not in targets:
                unreachable.add(key)
        if not unreachable:
            break
        for key in unreachable:
            del transitions[key]
        unreachable.clear()
        targets = set(transitions.values())

    # duplicate the transitions for case insensitive parsing
    if ignore_case:
        for (state, char), target in list(transitions.items()):
            transitions[(state, char.upper())] = target

    # return start state and transitions
    return tree, transitions
