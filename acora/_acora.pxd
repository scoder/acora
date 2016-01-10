
cimport cython

cimport cpython.object


@cython.final
cdef class _MachineState:
    cdef public list children
    cdef public list matches
    cdef public _MachineState fail
    cdef public unsigned long id
    cdef public Py_UCS4 letter

    @cython.locals(state=_MachineState)
    cdef _MachineState _copy_with_children(self, list children)


cdef inline _richcmp(self, other, int cmp_type):
    if type(self) is not _MachineState or type(other) is not _MachineState:
        return cmp_type == cpython.object.Py_NE
    if cmp_type == cpython.object.Py_EQ:
        return (<_MachineState>self).id == (<_MachineState>other).id
    elif cmp_type == cpython.object.Py_LT:
        return (<_MachineState>self).id < (<_MachineState>other).id
    elif cmp_type == cpython.object.Py_NE:
        return (<_MachineState>self).id != (<_MachineState>other).id
    # that's all we need
    return False


@cython.final
cdef class _Machine:
    cdef readonly _MachineState start_state
    cdef list _child_states
    cdef readonly bint ignore_case

    @cython.locals(state=_MachineState)
    cpdef __reduce__(self)


@cython.locals(state=_MachineState)
cpdef _MachineState build_MachineState(state_id, list matches=*)


@cython.locals(child=_MachineState)
cdef _MachineState _find_child(_MachineState state, Py_UCS4 ch)


@cython.locals(child=_MachineState, ch=Py_UCS4, ukeyword=unicode)
cpdef insert_unicode_keyword(_MachineState tree, keyword, long state_id, bint ignore_case=*)


@cython.locals(state=_MachineState, child=_MachineState, ch=Py_UCS4, uc=Py_UCS4)
cpdef build_trie(_MachineState start_state, bint ignore_case=*)


@cython.locals(letter=object, uc=Py_UCS4, child=_MachineState)
cpdef tuple merge_targets(_MachineState state, bint ignore_case)


@cython.locals(ch=Py_UCS4, lower=Py_UCS4, upper=Py_UCS4)
cdef _Machine _convert_old_format(transitions)


@cython.locals(state=_MachineState, child=_MachineState)
cpdef tree_to_dot(_MachineState tree, out=*)

@cython.locals(b=bytes)
cdef unicode _make_printable(s)


cpdef _sort_by_character(_MachineState s)
cpdef _sort_by_lc_character(_MachineState s)
