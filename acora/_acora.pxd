
cdef class _NfaState(dict):
    cdef public unsigned long id
    cdef public list matches
