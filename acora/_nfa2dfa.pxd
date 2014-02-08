
cimport cython
from _acora cimport _NfaState

cdef _collect(_NfaState tree, list collected)

@cython.locals(state=_NfaState, new_state=_NfaState, eq_states=frozenset)
cpdef nfa2dfa(_NfaState tree, bint ignore_case)
