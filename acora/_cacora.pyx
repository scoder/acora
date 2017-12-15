#cython: embedsignature=True
#cython: language_level=3
#cython: binding=True

"""A fast C implementation of the Acora search engine.

There are two main classes, UnicodeAcora and BytesAcora, that handle
byte data and unicode data respectively.
"""

__all__ = ['BytesAcora', 'UnicodeAcora']

cimport cython
cimport cpython.exc
cimport cpython.mem
cimport cpython.bytes
from cpython.ref cimport PyObject
from cpython.unicode cimport PyUnicode_AS_UNICODE, PyUnicode_GET_SIZE

from ._acora cimport (
    _Machine, _MachineState, build_MachineState, _find_child,
    _convert_old_format, merge_targets, _make_printable)

cdef extern from * nogil:
    ssize_t read(int fd, void *buf, size_t count)

cdef extern from "acora_defs.h":
    # PEP 393
    cdef bint PyUnicode_IS_READY(object u)
    cdef Py_ssize_t PyUnicode_GET_LENGTH(object u)
    cdef int PyUnicode_KIND(object u)
    cdef void* PyUnicode_DATA(object u)
    cdef int PyUnicode_WCHAR_KIND
    cdef Py_UCS4 PyUnicode_READ(int kind, void* data, Py_ssize_t index) nogil


DEF FILE_BUFFER_SIZE = 32 * 1024

ctypedef struct _AcoraUnicodeNodeStruct:
    Py_UCS4* characters
    _AcoraUnicodeNodeStruct** targets
    PyObject** matches
    int char_count

ctypedef struct _AcoraBytesNodeStruct:
    unsigned char* characters
    _AcoraBytesNodeStruct** targets
    PyObject** matches
    int char_count


# state machine building support

def insert_bytes_keyword(_MachineState tree, keyword, long state_id, bint ignore_case=False):
    # keep in sync with insert_unicode_keyword()
    cdef _MachineState child
    cdef unsigned char ch
    if not isinstance(keyword, bytes):
        raise TypeError("expected bytes object, got %s" % type(keyword).__name__)
    if not <bytes>keyword:
        raise ValueError("cannot search for the empty string")
    #print(keyword)
    for ch in <bytes>keyword:
        if ignore_case:
            if c'A' <= ch <= c'Z':
                ch += c'a' - c'A'
        #print(ch)
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


def insert_unicode_keyword(_MachineState tree, keyword, long state_id, bint ignore_case=False):
    # keep in sync with insert_bytes_keyword()
    cdef _MachineState child
    cdef Py_UCS4 ch
    if not isinstance(keyword, unicode):
        raise TypeError("expected Unicode string, got %s" % type(keyword).__name__)
    if not <unicode>keyword:
        raise ValueError("cannot search for the empty string")
    for ch in <unicode>keyword:
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


def machine_to_dot(machine, out=None):
    cdef _AcoraUnicodeNodeStruct* unode
    cdef _AcoraUnicodeNodeStruct* unodes = NULL
    cdef _AcoraBytesNodeStruct* bnode
    cdef _AcoraBytesNodeStruct* bnodes = NULL
    cdef Py_ssize_t node_count, node_id
    cdef PyObject **cmatches
    cdef Py_UCS4 ch
    cdef unsigned char bch

    if isinstance(machine, UnicodeAcora):
        unodes = (<UnicodeAcora>machine).start_node
        node_count = (<UnicodeAcora>machine).node_count
    elif isinstance(machine, BytesAcora):
        bnodes = (<BytesAcora>machine).start_node
        node_count = (<BytesAcora>machine).node_count
    else:
        raise TypeError(
            "Expected UnicodeAcora or BytesAcora instance, got %s" % machine.__class__.__name__)

    if out is None:
        from sys import stdout as out

    write = out.write
    write("digraph {\n")
    write('%s [label="%s"];\n' % (0, 'start'))
    seen = set()
    for node_id in range(node_count):
        if unodes:
            unode = unodes + node_id
            characters = [ch for ch in unode.characters[:unode.char_count]]
            child_ids = [<size_t>(child - unodes) for child in unode.targets[:unode.char_count]]
            cmatches = unode.matches
        else:
            bnode = bnodes + node_id
            characters = [<bytes>bch for bch in bnode.characters[:bnode.char_count]]
            child_ids = [<size_t>(child - bnodes) for child in bnode.targets[:bnode.char_count]]
            cmatches = bnode.matches

        if cmatches is not NULL:
            matches = []
            while cmatches[0]:
                matches.append(_make_printable(<object>cmatches[0]))
                cmatches += 1
            if matches:
                write('M%s [label="%s", shape=note];\n' % (
                    node_id, '\\n'.join(_make_printable(s) for s in matches)))
                write('%s -> M%s [style=dotted];\n' % (node_id, node_id))

        for child_id, character in zip(child_ids, characters):
            character = _make_printable(character)
            if child_id not in seen:
                write('%s [label="%s"];\n' % (child_id, character))
                seen.add(child_id)
            write('%s -> %s [label="%s"];\n' % (node_id, child_id, character))
    write("}\n")


# Unicode machine

cdef int _init_unicode_node(
        _AcoraUnicodeNodeStruct* c_node, _MachineState state,
        _AcoraUnicodeNodeStruct* all_nodes,
        dict node_offsets, dict pyrefs, bint ignore_case) except -1:
    cdef _MachineState child, fail_state
    cdef size_t mem_size
    cdef Py_ssize_t i
    cdef unicode letter
    cdef dict targets

    # merge children failure states and matches to avoid deep failure state traversal
    targets, matches = merge_targets(state, ignore_case)
    cdef size_t child_count = len(targets)

    # use a single malloc for targets and match-string pointers
    mem_size = sizeof(_AcoraUnicodeNodeStruct**) * child_count
    if matches:
        mem_size += sizeof(PyObject*) * (len(matches) + 1)  # NULL terminated
    mem_size += sizeof(Py_UCS4) * child_count
    c_node.targets = <_AcoraUnicodeNodeStruct**> cpython.mem.PyMem_Malloc(mem_size)
    if c_node.targets is NULL:
        raise MemoryError()

    if not matches:
        c_node.matches = NULL
        c_characters = <Py_UCS4*> (c_node.targets + child_count)
    else:
        c_node.matches = <PyObject**> (c_node.targets + child_count)
        matches = _intern(pyrefs, tuple(matches))
        i = 0
        for match in matches:
            c_node.matches[i] = <PyObject*>match
            i += 1
        c_node.matches[i] = NULL
        c_characters = <Py_UCS4*> (c_node.matches + i + 1)

    if state.children and len(targets) == len(state.children):
        for i, child in enumerate(state.children):
            c_node.targets[i] = all_nodes + <size_t>node_offsets[child]
            c_characters[i] = child.letter
    else:
        # dict[key] is much faster than creating and sorting item tuples
        for i, character in enumerate(sorted(targets)):
            c_node.targets[i] = all_nodes + <size_t>node_offsets[targets[character]]
            c_characters[i] = character

    c_node.characters = c_characters
    c_node.char_count = child_count


cdef int _init_bytes_node(
        _AcoraBytesNodeStruct* c_node, state,
        _AcoraBytesNodeStruct* all_nodes,
        dict node_offsets, dict pyrefs, bint ignore_case) except -1:
    cdef _MachineState child, fail_state
    cdef size_t mem_size
    cdef Py_ssize_t i
    cdef unicode letter
    cdef dict targets

    # merge children failure states and matches to avoid deep failure state traversal
    targets, matches = merge_targets(state, ignore_case)
    cdef size_t child_count = len(targets)

    # use a single malloc for targets and match-string pointers
    mem_size = targets_mem_size = sizeof(_AcoraBytesNodeStruct**) * len(targets)
    if matches:
        mem_size += sizeof(PyObject*) * (len(matches) + 1) # NULL terminated
    c_node.targets = <_AcoraBytesNodeStruct**> cpython.mem.PyMem_Malloc(mem_size)
    if c_node.targets is NULL:
        raise MemoryError()

    if mem_size == targets_mem_size:  # no matches
        c_node.matches = NULL
    else:
        c_node.matches = <PyObject**> (c_node.targets + len(targets))
        matches = _intern(pyrefs, tuple(matches))
        i = 0
        for match in matches:
            c_node.matches[i] = <PyObject*>match
            i += 1
        c_node.matches[i] = NULL

    characters = cpython.bytes.PyBytes_FromStringAndSize(NULL, len(targets))
    cdef unsigned char *c_characters = characters
    if len(targets) == len(state.children):
        for i, child in enumerate(state.children):
            c_node.targets[i] = all_nodes + <size_t>node_offsets[child]
            c_characters[i] = child.letter
    else:
        # dict[key] is much faster than creating and sorting item tuples
        for i, character in enumerate(sorted(targets)):
            c_node.targets[i] = all_nodes + <size_t>node_offsets[targets[character]]
            c_characters[i] = <Py_UCS4>character
    characters = _intern(pyrefs, characters)

    c_node.characters = characters
    c_node.char_count = len(characters)


cdef inline _intern(dict d, obj):
    if obj in d:
        return d[obj]
    d[obj] = obj
    return obj


cdef dict group_transitions_by_state(dict transitions):
    transitions_by_state = {}
    for (state, character), target in transitions.iteritems():
        if state in transitions_by_state:
            transitions_by_state[state].append((character, target))
        else:
            transitions_by_state[state] = [(character, target)]
    return transitions_by_state


# unicode data handling

cdef class UnicodeAcora:
    """Acora search engine for unicode data.
    """
    cdef _AcoraUnicodeNodeStruct* start_node
    cdef Py_ssize_t node_count
    cdef tuple _pyrefs
    cdef bint _ignore_case

    def __cinit__(self, start_state, dict transitions=None):
        cdef _Machine machine
        cdef _AcoraUnicodeNodeStruct* c_nodes
        cdef _AcoraUnicodeNodeStruct* c_node
        cdef Py_ssize_t i

        if transitions is not None:
            # old pickle format => rebuild trie
            machine = _convert_old_format(transitions)
        else:
            machine = start_state
        ignore_case = self._ignore_case = machine.ignore_case
        self.node_count = len(machine.child_states) + 1

        c_nodes = self.start_node = <_AcoraUnicodeNodeStruct*> cpython.mem.PyMem_Malloc(
            sizeof(_AcoraUnicodeNodeStruct) * self.node_count)
        if c_nodes is NULL:
            raise MemoryError()

        for c_node in c_nodes[:self.node_count]:
            # required by __dealloc__ in case of subsequent errors
            c_node.targets = NULL

        node_offsets = {state: i for i, state in enumerate(machine.child_states, 1)}
        node_offsets[machine.start_state] = 0
        pyrefs = {}  # used to keep Python references alive (and intern them)

        _init_unicode_node(c_nodes, machine.start_state, c_nodes, node_offsets, pyrefs, ignore_case)
        for i, state in enumerate(machine.child_states, 1):
            _init_unicode_node(c_nodes + i, state, c_nodes, node_offsets, pyrefs, ignore_case)
        self._pyrefs = tuple(pyrefs)

    def __dealloc__(self):
        cdef Py_ssize_t i
        if self.start_node is not NULL:
            for i in range(self.node_count):
                if self.start_node[i].targets is not NULL:
                    cpython.mem.PyMem_Free(self.start_node[i].targets)
            cpython.mem.PyMem_Free(self.start_node)

    def __reduce__(self):
        """pickle"""
        cdef _AcoraUnicodeNodeStruct* c_node
        cdef _AcoraUnicodeNodeStruct* c_child
        cdef _AcoraUnicodeNodeStruct* c_start_node = self.start_node
        cdef Py_ssize_t state_id, i
        cdef bint ignore_case
        states = {}
        states_list = []
        for state_id in range(self.node_count):
            state = states[state_id] = {'id': state_id}
            states_list.append(state)
            c_node = c_start_node + state_id
            if c_node.matches:
                state['m'] = matches = []
                match = c_node.matches
                while match[0]:
                    matches.append(<unicode>match[0])
                    match += 1

        # create child links
        ignore_case = self._ignore_case
        for state_id in range(self.node_count):
            c_node = c_start_node + state_id
            if not c_node.char_count:
                continue
            state = states[state_id]
            state['c'] = children = []
            for i in range(c_node.char_count):
                ch = c_node.characters[i]
                if ignore_case and ch.isupper():
                    # ignore upper case characters, assuming that lower case exists as well
                    continue
                c_child = c_node.targets[i]
                child_id = c_child - c_start_node
                children.append((ch, child_id))

        return _unpickle, (self.__class__, states_list, self._ignore_case,)

    cpdef finditer(self, unicode data):
        """Iterate over all occurrences of any keyword in the string.

        Returns (keyword, offset) pairs.
        """
        if self.start_node.char_count == 0:
            return iter(())
        return _UnicodeAcoraIter(self, data)

    def findall(self, unicode data):
        """Find all occurrences of any keyword in the string.

        Returns a list of (keyword, offset) pairs.
        """
        return list(self.finditer(data))


def _unpickle(type cls not None, list states_list not None, bint ignore_case):
    if not issubclass(cls, (UnicodeAcora, BytesAcora)):
        raise ValueError(
            "Invalid machine class, expected UnicodeAcora or BytesAcora, got %s" % cls.__name__)

    cdef Py_ssize_t i
    states = {i: build_MachineState(i) for i in range(len(states_list))}
    start_state = states[0]
    for state_data in states_list:
        state = states[state_data['id']]
        state.matches = state_data.get('m')
        state.children = children = []
        for character, child_id in state_data.get('c', ()):
            child = states[child_id]
            child.letter = character
            children.append(child)

    return cls(_Machine(start_state, ignore_case=ignore_case))


cdef class _UnicodeAcoraIter:
    cdef _AcoraUnicodeNodeStruct* current_node
    cdef _AcoraUnicodeNodeStruct* start_node
    cdef Py_ssize_t data_pos, data_len, match_index
    cdef unicode data
    cdef UnicodeAcora acora
    cdef void* data_start
    cdef int unicode_kind

    def __cinit__(self, UnicodeAcora acora not None, unicode data not None):
        assert acora.start_node is not NULL
        assert acora.start_node.matches is NULL
        self.acora = acora
        self.start_node = self.current_node = acora.start_node
        self.match_index = 0
        self.data = data
        self.data_pos = 0
        if PyUnicode_IS_READY(data):
            # PEP393 Unicode string
            self.data_start = PyUnicode_DATA(data)
            self.data_len = PyUnicode_GET_LENGTH(data)
            self.unicode_kind = PyUnicode_KIND(data)
        else:
            # pre-/non-PEP393 Unicode string
            self.data_start = PyUnicode_AS_UNICODE(data)
            self.data_len = PyUnicode_GET_SIZE(data)
            self.unicode_kind = PyUnicode_WCHAR_KIND

        if not acora.start_node.char_count:
            raise ValueError("Non-empty engine required")

    def __iter__(self):
        return self

    def __next__(self):
        cdef void* data_start = self.data_start
        cdef Py_UCS4* test_chars
        cdef Py_UCS4 current_char
        cdef int i, found = 0, start, mid, end
        cdef Py_ssize_t data_len = self.data_len, data_pos = self.data_pos
        cdef _AcoraUnicodeNodeStruct* start_node = self.start_node
        cdef _AcoraUnicodeNodeStruct* current_node = self.current_node

        if current_node.matches is not NULL:
            if current_node.matches[self.match_index] is not NULL:
                return self._build_next_match()
            self.match_index = 0

        kind = self.unicode_kind
        with nogil:
            while data_pos < data_len:
                current_char = PyUnicode_READ(kind, data_start, data_pos)
                data_pos += 1
                current_node = _step_to_next_node(start_node, current_node, current_char)
                if current_node.matches is not NULL:
                    found = 1
                    break
        self.data_pos = data_pos
        self.current_node = current_node
        if found:
            return self._build_next_match()
        raise StopIteration

    cdef _build_next_match(self):
        match = <unicode> self.current_node.matches[self.match_index]
        self.match_index += 1
        return match, self.data_pos - len(match)


# bytes data handling

cdef class BytesAcora:
    """Acora search engine for byte data.
    """
    cdef _AcoraBytesNodeStruct* start_node
    cdef Py_ssize_t node_count
    cdef tuple _pyrefs
    cdef bint _ignore_case

    def __cinit__(self, start_state, dict transitions=None):
        cdef _Machine machine
        cdef _AcoraBytesNodeStruct* c_nodes
        cdef _AcoraBytesNodeStruct* c_node
        cdef Py_ssize_t i

        if transitions is not None:
            # old pickle format => rebuild trie
            machine = _convert_old_format(transitions)
        else:
            machine = start_state
        ignore_case = self._ignore_case = machine.ignore_case
        self.node_count = len(machine.child_states) + 1

        c_nodes = self.start_node = <_AcoraBytesNodeStruct*> cpython.mem.PyMem_Malloc(
            sizeof(_AcoraBytesNodeStruct) * self.node_count)
        if c_nodes is NULL:
            raise MemoryError()

        for c_node in c_nodes[:self.node_count]:
            # required by __dealloc__ in case of subsequent errors
            c_node.targets = NULL

        node_offsets = {state: i for i, state in enumerate(machine.child_states, 1)}
        node_offsets[machine.start_state] = 0
        pyrefs = {}  # used to keep Python references alive (and intern them)

        _init_bytes_node(c_nodes, machine.start_state, c_nodes, node_offsets, pyrefs, ignore_case)
        for i, state in enumerate(machine.child_states, 1):
            _init_bytes_node(c_nodes + i, state, c_nodes, node_offsets, pyrefs, ignore_case)
        self._pyrefs = tuple(pyrefs)

    def __dealloc__(self):
        cdef Py_ssize_t i
        if self.start_node is not NULL:
            for i in range(self.node_count):
                if self.start_node[i].targets is not NULL:
                    cpython.mem.PyMem_Free(self.start_node[i].targets)
            cpython.mem.PyMem_Free(self.start_node)

    def __reduce__(self):
        """pickle"""
        cdef _AcoraBytesNodeStruct* c_node
        cdef _AcoraBytesNodeStruct* c_child
        cdef _AcoraBytesNodeStruct* c_start_node = self.start_node
        cdef Py_ssize_t state_id, i
        cdef bint ignore_case

        states = {}
        states_list = []
        for state_id in range(self.node_count):
            state = states[state_id] = {'id': state_id}
            states_list.append(state)
            c_node = c_start_node + state_id
            if c_node.matches:
                state['m'] = matches = []
                match = c_node.matches
                while match[0]:
                    matches.append(<unicode>match[0])
                    match += 1

        # create child links
        ignore_case = self._ignore_case
        for state_id in range(self.node_count):
            c_node = c_start_node + state_id
            if not c_node.char_count:
                continue
            state = states[state_id]
            state['c'] = children = []
            for i in range(c_node.char_count):
                ch = c_node.characters[i]
                if ignore_case and ch.isupper():
                    # ignore upper case characters, assuming that lower case exists as well
                    continue
                c_child = c_node.targets[i]
                child_id = c_child - c_start_node
                children.append((ch, child_id))

        return _unpickle, (self.__class__, states_list, self._ignore_case,)

    cpdef finditer(self, bytes data):
        """Iterate over all occurrences of any keyword in the string.

        Returns (keyword, offset) pairs.
        """
        if self.start_node.char_count == 0:
            return iter(())
        return _BytesAcoraIter(self, data)

    def findall(self, bytes data):
        """Find all occurrences of any keyword in the string.

        Returns a list of (keyword, offset) pairs.
        """
        return list(self.finditer(data))

    def filefind(self, f):
        """Iterate over all occurrences of any keyword in a file.

        The file must be either a file path, a file opened in binary mode
        or a file-like object returning bytes objects on .read().

        Returns (keyword, offset) pairs.
        """
        if self.start_node.char_count == 0:
            return iter(())
        close_file = False
        if not hasattr(f, 'read'):
            f = open(f, 'rb')
            close_file = True
        return _FileAcoraIter(self, f, close_file)

    def filefindall(self, f):
        """Find all occurrences of any keyword in a file.

        Returns a list of (keyword, offset) pairs.
        """
        return list(self.filefind(f))


cdef class _BytesAcoraIter:
    cdef _AcoraBytesNodeStruct* current_node
    cdef _AcoraBytesNodeStruct* start_node
    cdef Py_ssize_t match_index
    cdef bytes data
    cdef BytesAcora acora
    cdef unsigned char* data_char
    cdef unsigned char* data_end
    cdef unsigned char* data_start

    def __cinit__(self, BytesAcora acora not None, bytes data):
        assert acora.start_node is not NULL
        assert acora.start_node.matches is NULL
        self.acora = acora
        self.start_node = self.current_node = acora.start_node
        self.match_index = 0
        self.data_char = self.data_start = self.data = data
        self.data_end = self.data_char + len(data)

        if not acora.start_node.char_count:
            raise ValueError("Non-empty engine required")

    def __iter__(self):
        return self

    def __next__(self):
        cdef unsigned char* data_char = self.data_char
        cdef unsigned char* data_end = self.data_end
        cdef unsigned char* test_chars
        cdef unsigned char current_char
        cdef int i, found = 0
        if self.current_node.matches is not NULL:
            if self.current_node.matches[self.match_index] is not NULL:
                return self._build_next_match()
            self.match_index = 0
        with nogil:
            found = _search_in_bytes(self.start_node, data_end,
                                     &self.data_char, &self.current_node)
        if found:
            return self._build_next_match()
        raise StopIteration

    cdef _build_next_match(self):
        match = <bytes> self.current_node.matches[self.match_index]
        self.match_index += 1
        return (match, <Py_ssize_t>(self.data_char - self.data_start) - len(match))


cdef int _search_in_bytes(_AcoraBytesNodeStruct* start_node,
                          unsigned char* data_end,
                          unsigned char** _data_char,
                          _AcoraBytesNodeStruct** _current_node) nogil:
    cdef unsigned char* data_char = _data_char[0]
    cdef _AcoraBytesNodeStruct* current_node = _current_node[0]
    cdef unsigned char current_char
    cdef int found = 0

    while data_char < data_end:
        current_char = data_char[0]
        data_char += 1
        current_node = _step_to_next_node(start_node, current_node, current_char)
        if current_node.matches is not NULL:
            found = 1
            break
    _data_char[0] = data_char
    _current_node[0] = current_node
    return found


ctypedef fused _AcoraNodeStruct:
    _AcoraBytesNodeStruct
    _AcoraUnicodeNodeStruct

ctypedef fused _inputCharType:
    unsigned char
    Py_UCS4


@cython.cdivision(True)
cdef inline _AcoraNodeStruct* _step_to_next_node(
        _AcoraNodeStruct* start_node,
        _AcoraNodeStruct* current_node,
        _inputCharType current_char) nogil:

    cdef _inputCharType* test_chars = <_inputCharType*>current_node.characters
    cdef int i, start, mid, end

    end = current_node.char_count
    if current_char <= test_chars[0]:
        return current_node.targets[0] if current_char == test_chars[0] else start_node

    if current_char >= test_chars[end-1]:
        return current_node.targets[end-1] if current_char == test_chars[end-1] else start_node

    # bisect into larger character maps (> 8 seems to perform best for me)
    start = 0
    while end - start > 8:
        mid = (start + end) // 2
        if current_char < test_chars[mid]:
            end = mid
        elif current_char == test_chars[mid]:
            return current_node.targets[mid]
        else:
            start = mid

    # sequentially run through small character maps
    for i in range(start, end):
        if current_char <= test_chars[i]:
            return current_node.targets[i] if current_char == test_chars[i] else start_node

    return start_node


# file data handling

cdef class _FileAcoraIter:
    cdef _AcoraBytesNodeStruct* current_node
    cdef _AcoraBytesNodeStruct* start_node
    cdef Py_ssize_t match_index, read_size, buffer_offset_count
    cdef bytes buffer
    cdef unsigned char* c_buffer_pos
    cdef unsigned char* c_buffer_end
    cdef object f
    cdef bint close_file
    cdef int c_file
    cdef BytesAcora acora

    def __cinit__(self, BytesAcora acora not None, f, bint close=False, Py_ssize_t buffer_size=FILE_BUFFER_SIZE):
        assert acora.start_node is not NULL
        assert acora.start_node.matches is NULL
        self.acora = acora
        self.start_node = self.current_node = acora.start_node
        self.match_index = 0
        self.buffer_offset_count = 0
        self.f = f
        self.close_file = close
        try:
            self.c_file = f.fileno() if f.tell() == 0 else -1
        except:
            # maybe not a C file?
            self.c_file = -1
        self.read_size = buffer_size
        if self.c_file == -1:
            self.buffer = b''
        else:
            # use a statically allocated, fixed-size C buffer
            self.buffer = b'\0' * buffer_size
        self.c_buffer_pos = self.c_buffer_end = <unsigned char*> self.buffer

        if not acora.start_node.char_count:
            raise ValueError("Non-empty engine required")

    def __iter__(self):
        return self

    def __next__(self):
        cdef bytes buffer
        cdef unsigned char* c_buffer
        cdef unsigned char* data_end
        cdef int error = 0, found = 0
        cdef Py_ssize_t buffer_size, bytes_read = 0
        if self.c_buffer_pos is NULL:
            raise StopIteration
        if self.current_node.matches is not NULL:
            if self.current_node.matches[self.match_index] is not NULL:
                return self._build_next_match()
            self.match_index = 0

        buffer_size = len(self.buffer)
        c_buffer = <unsigned char*> self.buffer
        if self.c_file != -1:
            with nogil:
                found = _find_next_match_in_cfile(
                    self.c_file, c_buffer, buffer_size, self.start_node,
                    &self.c_buffer_pos, &self.c_buffer_end,
                    &self.buffer_offset_count, &self.current_node, &error)
            if error:
                cpython.exc.PyErr_SetFromErrno(IOError)
        else:
            # Why not always release the GIL and only acquire it when reading?
            # Well, it's actually doing that.  When the search finds something,
            # we have to acquire the GIL in order to return the result, and if
            # it does not find anything, then we have to acquire the GIL in order
            # to read more data.  So, wrapping the search call in a nogil section
            # is actually enough.
            data_end = c_buffer + buffer_size
            while not found:
                if self.c_buffer_pos >= data_end:
                    self.buffer_offset_count += buffer_size
                    self.buffer = self.f.read(self.read_size)
                    buffer_size = len(self.buffer)
                    if buffer_size == 0:
                        self.c_buffer_pos = NULL
                        break
                    c_buffer = self.c_buffer_pos = <unsigned char*> self.buffer
                    data_end = c_buffer + buffer_size
                with nogil:
                    found = _search_in_bytes(
                        self.start_node, data_end,
                        &self.c_buffer_pos, &self.current_node)
        if self.c_buffer_pos is NULL:
            if self.close_file:
                self.f.close()
        elif found:
            return self._build_next_match()
        raise StopIteration

    cdef _build_next_match(self):
        match = <bytes> self.current_node.matches[self.match_index]
        self.match_index += 1
        return (match, self.buffer_offset_count + (
                self.c_buffer_pos - (<unsigned char*> self.buffer)) - len(match))


cdef int _find_next_match_in_cfile(int c_file, unsigned char* c_buffer, size_t buffer_size,
                                   _AcoraBytesNodeStruct* start_node,
                                   unsigned char** _buffer_pos, unsigned char** _buffer_end,
                                   Py_ssize_t* _buffer_offset_count,
                                   _AcoraBytesNodeStruct** _current_node,
                                   int* error) nogil:
    cdef unsigned char* buffer_pos = _buffer_pos[0]
    cdef unsigned char* buffer_end = _buffer_end[0]
    cdef unsigned char* data_end = c_buffer + buffer_size
    cdef Py_ssize_t buffer_offset_count = _buffer_offset_count[0]
    cdef _AcoraBytesNodeStruct* current_node = _current_node[0]
    cdef int found = 0
    cdef Py_ssize_t bytes_read

    while not found:
        if buffer_pos >= buffer_end:
            buffer_offset_count += buffer_end - c_buffer
            bytes_read = read(c_file, c_buffer, buffer_size)
            if bytes_read <= 0:
                if bytes_read < 0:
                    error[0] = 1
                buffer_pos = NULL
                break
            buffer_pos = c_buffer
            buffer_end = c_buffer + bytes_read

        found = _search_in_bytes(
            start_node, buffer_end, &buffer_pos, &current_node)

    _current_node[0] = current_node
    _buffer_offset_count[0] = buffer_offset_count
    _buffer_pos[0] = buffer_pos
    _buffer_end[0] = buffer_end
    return found
