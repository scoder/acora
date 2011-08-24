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

def _visit_all(tree, visitor):
    visitor(tree)
    for node in tree.values():
        _visit_all(node, visitor)

def nfa2dfa(tree, ignore_case):
    """Transform a keyword tree into a DFA using powerset construction.
    """
    states = []
    _visit_all(tree, states.append)
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
    targets = set() # created here to reduce overhead in innermost loop
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

            eq_classes_by_state[new_state] = eq_states
            existing_eq_classes[eq_key] = new_state
            next_state_id += 1

            # redirect the original transition to the new node
            transitions[key] = set([new_state])

            # collect its transitions and matches
            matches = []
            new_chars = chars_by_state[new_state] = set()
            for state in eq_states:
                matches.extend(state.matches)
                transition_chars = chars_by_state[state]
                new_chars.update(transition_chars)
                for char in transition_chars:
                    # resolve original states from equivalence class states
                    for target in transitions[(state,char)]:
                        if target in eq_classes_by_state:
                            targets.update(eq_classes_by_state[target])
                        else:
                            targets.add(target)
                    new_key = (new_state,char)
                    if new_key in transitions:
                        transitions[new_key].update(targets)
                        targets.clear()
                    else:
                        transitions[new_key] = targets
                        targets = set()
                    new_eq_classes.add(new_key)
            # sort longest match first to assure left-to-right match order
            matches.sort(key=len, reverse=True)
            new_state.matches = matches

    # rebuild transitions dict to point to exactly one state
    for key, state_set in transitions.items():
        assert len(state_set) == 1
        transitions[key] = state_set.pop()

    # duplicate the transitions for case insensitive parsing
    if ignore_case:
        for (state,char), target in list(transitions.items()):
            transitions[(state,char.upper())] = target

    # return start state and transitions
    return tree, transitions
