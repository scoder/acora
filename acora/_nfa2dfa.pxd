
from _acora cimport _NfaState

cdef _visit_all(_NfaState tree, visitor)

@cython.locals(state=_NfaState, new_state=_NfaState, eq_states=set)
cpdef nfa2dfa(_NfaState tree, bint ignore_case)
