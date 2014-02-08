#cython: embedsignature=True
#cython: language_level=3
#cython: binding=True

"""A fast C implementation of the Acora search engine.

There are two main classes, UnicodeAcora and BytesAcora, that handle
byte data and unicode data respectively.
"""

__all__ = ['BytesAcora', 'UnicodeAcora']

from libc cimport stdio
cimport cpython.exc
cimport cpython.mem
cimport cpython.object
from cpython.ref cimport PyObject
from cpython.version cimport PY_MAJOR_VERSION
from cpython.unicode cimport PyUnicode_AS_UNICODE, PyUnicode_GET_SIZE

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

cdef class _NfaState(dict):
    """NFA state for the untransformed automaton.
    """
    def __richcmp__(self, other, int cmp_type):
        if type(self) is not _NfaState or type(other) is not _NfaState:
            return cmp_type == cpython.object.Py_NE
        if cmp_type == cpython.object.Py_EQ:
            return (<_NfaState>self).id == (<_NfaState>other).id
        elif cmp_type == cpython.object.Py_LT:
            return (<_NfaState>self).id < (<_NfaState>other).id
        elif cmp_type == cpython.object.Py_NE:
            return (<_NfaState>self).id != (<_NfaState>other).id
        # that's all we need
        return False

    def __hash__(self):
        return <long>self.id

    def __str__(self):
        return str(self.id)

    def __repr__(self):
        return str(self.id)

    def __copy__(self):
        state = _NfaState(self)
        state.id = self.id
        state.matches = self.matches[:]
        return state

    def __deepcopy__(self, memo):
        state = _NfaState(
            [ (character, child.__deepcopy__(None))
              for character, child in (<object>self).items() ])
        state.id = self.id
        state.matches = self.matches[:]
        return state

    def __reduce__(self):
        """pickle"""
        return (build_NfaState, (self.id, self.matches),
                None, None, iter(self.items()))


cpdef _NfaState build_NfaState(state_id, list matches=None):
    cdef _NfaState state = _NfaState()
    state.id = state_id
    state.matches = [] if matches is None else matches
    return state


# Unicode machine

cdef _init_unicode_node(_AcoraUnicodeNodeStruct* c_node, state,
                        list state_transitions,
                        _AcoraUnicodeNodeStruct* all_nodes,
                        dict node_offsets, dict pyrefs):
    cdef size_t targets_mem_size, mem_size
    cdef Py_ssize_t i
    cdef tuple matches
    cdef unicode characters
    cdef Py_UCS4 ch

    state_transitions.sort() # sort by characters
    chars, targets = list(zip(*state_transitions))
    characters = u''.join(chars)
    matches = tuple(state.matches) if state.matches else None

    # use a single malloc for targets and match-string pointers
    mem_size = targets_mem_size = sizeof(_AcoraUnicodeNodeStruct**) * len(targets)
    if matches:
        mem_size += sizeof(PyObject*) * (len(matches) + 1) # NULL terminated
    mem_size += sizeof(Py_UCS4) * len(characters)
    c_node.targets = <_AcoraUnicodeNodeStruct**> cpython.mem.PyMem_Malloc(mem_size)
    if c_node.targets is NULL:
        raise MemoryError()

    for i, target in enumerate(targets):
        c_node.targets[i] = all_nodes + <size_t>node_offsets[target]

    if not matches:
        c_node.matches = NULL
        c_characters = <Py_UCS4*> (c_node.targets + len(targets))
    else:
        c_node.matches = <PyObject**> (c_node.targets + len(targets))
        matches = _intern(pyrefs, matches)
        i = 0
        for match in matches:
            c_node.matches[i] = <PyObject*>match
            i += 1
        c_node.matches[i] = NULL
        c_characters = <Py_UCS4*> (c_node.matches + i + 1)

    for i, ch in enumerate(characters):
        c_characters[i] = ch
    c_node.characters = c_characters
    c_node.char_count = len(characters)


cdef _init_bytes_node(_AcoraBytesNodeStruct* c_node, state,
                      list state_transitions,
                      _AcoraBytesNodeStruct* all_nodes,
                      dict node_offsets, dict pyrefs):
    cdef size_t targets_mem_size, mem_size
    cdef Py_ssize_t i

    state_transitions.sort() # sort by characters
    characters, targets = list(zip(*state_transitions))
    if PY_MAJOR_VERSION >= 3:
        characters = bytes(characters) # items are integers, not byte strings
    else:
        characters = b''.join(characters)
    characters = _intern(pyrefs, characters)

    c_node.characters = characters
    c_node.char_count = len(characters)

    # use a single malloc for targets and match-string pointers
    mem_size = targets_mem_size = sizeof(_AcoraBytesNodeStruct**) * len(targets)
    if state.matches is not None and len(state.matches) > 0:
        mem_size += sizeof(PyObject*) * (len(state.matches) + 1) # NULL terminated
    c_node.targets = <_AcoraBytesNodeStruct**> cpython.mem.PyMem_Malloc(mem_size)
    if c_node.targets is NULL:
        raise MemoryError()

    for i, target in enumerate(targets):
        c_node.targets[i] = all_nodes + <size_t>node_offsets[target]

    if mem_size == targets_mem_size:
        c_node.matches = NULL
    else:
        c_node.matches = <PyObject**> (c_node.targets + len(targets))
        matches = _intern(pyrefs, tuple(state.matches))
        i = 0
        for match in matches:
            c_node.matches[i] = <PyObject*>match
            i += 1
        c_node.matches[i] = NULL


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
    #_dump_transitions(transitions_by_state)
    return transitions_by_state


"""
cdef _dump_transitions(dict transitions_by_state):
    try:
        from io import open
    except ImportError:
        from codecs import open

    with open('out.dot', 'w', encoding='utf8') as f:
        f.write('digraph {\n')
        for state, targets in transitions_by_state.iteritems():
            for character, target in targets:
                if isinstance(character, bytes):
                    character = (<bytes>character).decode('iso8859-1')
                elif isinstance(character, int):
                    character = chr(character)
                if target.id > 1:
                    f.write('    "%s" -> "%s" [label="%s", color=%s];\n' % (
                        state.id, target.id,
                        character.replace('"', '\\"'),
                        'red' if target.matches else 'black',
                    ))
        f.write('}\n')
"""


# unicode data handling

cdef class UnicodeAcora:
    """Acora search engine for unicode data.
    """
    cdef _AcoraUnicodeNodeStruct* start_node
    cdef Py_ssize_t node_count
    cdef tuple _pyrefs

    def __cinit__(self, start_state, dict transitions not None):
        cdef _AcoraUnicodeNodeStruct* c_nodes
        cdef Py_ssize_t i
        self.start_node = NULL
        # sort states by id (start state first)
        states = list(enumerate(
            sorted(group_transitions_by_state(transitions).items())))

        self.node_count = len(states)
        c_nodes = self.start_node = <_AcoraUnicodeNodeStruct*> cpython.mem.PyMem_Malloc(
            sizeof(_AcoraUnicodeNodeStruct) * self.node_count)
        if c_nodes is NULL:
            raise MemoryError()

        for i in range(self.node_count):
            # required by __dealloc__ in case of subsequent errors
            c_nodes[i].targets = NULL

        node_offsets = dict([
            (state, i) for i, (state, state_transitions) in states])
        pyrefs = {} # used to keep Python references alive (and intern them)
        for i, (state, state_transitions) in states:
            _init_unicode_node(&c_nodes[i], state, state_transitions,
                               c_nodes, node_offsets, pyrefs)

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
        states = {}
        for c_node in self.start_node[:self.node_count]:
            state_id = c_node - self.start_node
            state = states[state_id] = build_NfaState(state_id)
            if c_node.matches:
                match = c_node.matches
                while match[0]:
                    state.matches.append(<unicode>match[0])
                    match += 1

        transitions = {}
        for c_node in self.start_node[:self.node_count]:
            state_id = c_node - self.start_node
            state = states[state_id]
            for i in range(c_node.char_count):
                ch = <unicode>c_node.characters[i]
                target_id = c_node.targets[i] - self.start_node
                transitions[(state, ch)] = states[target_id]

        return type(self), (states[0], transitions)

    cpdef finditer(self, unicode data):
        """Iterate over all occurrences of any keyword in the string.

        Returns (keyword, offset) pairs.
        """
        return _UnicodeAcoraIter(self, data)

    def findall(self, unicode data):
        """Find all occurrences of any keyword in the string.

        Returns a list of (keyword, offset) pairs.
        """
        return list(self.finditer(data))


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
                test_chars = current_node.characters
                if current_char == test_chars[0]:
                    current_node = current_node.targets[0]
                elif current_char < test_chars[0] \
                        or current_char > test_chars[current_node.char_count-1]:
                    current_node = start_node
                else:
                    # walk through at most half the characters
                    mid = current_node.char_count // 2
                    if current_char < test_chars[mid]:
                        start = 0
                        end = mid
                    else:
                        start = mid
                        end = current_node.char_count

                    for i in range(start, end):
                        if current_char <= test_chars[i]:
                            if current_char == test_chars[i]:
                                current_node = current_node.targets[i]
                            else:
                                current_node = start_node
                            break
                    else:
                        current_node = start_node
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

    def __cinit__(self, start_state, dict transitions not None):
        cdef _AcoraBytesNodeStruct* c_nodes
        cdef Py_ssize_t i
        self.start_node = NULL
        # sort states by id (start state first)
        states = list(enumerate(
            sorted(group_transitions_by_state(transitions).items())))

        self.node_count = len(states)
        c_nodes = self.start_node = <_AcoraBytesNodeStruct*> cpython.mem.PyMem_Malloc(
            sizeof(_AcoraBytesNodeStruct) * self.node_count)
        if c_nodes is NULL:
            raise MemoryError()

        for i in range(self.node_count):
            # required by __dealloc__ in case of subsequent errors
            c_nodes[i].targets = NULL

        node_offsets = dict([
            (state, i) for i, (state, state_transitions) in states])
        pyrefs = {} # used to keep Python references alive (and intern them)
        for i, (state, state_transitions) in states:
            _init_bytes_node(&c_nodes[i], state, state_transitions,
                             c_nodes, node_offsets, pyrefs)

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
        states = {}
        for c_node in self.start_node[:self.node_count]:
            state_id = c_node - self.start_node
            state = states[state_id] = build_NfaState(state_id)
            if c_node.matches:
                match = c_node.matches
                while match[0]:
                    state.matches.append(<bytes>match[0])
                    match += 1

        transitions = {}
        for c_node in self.start_node[:self.node_count]:
            state_id = c_node - self.start_node
            state = states[state_id]
            for i in range(c_node.char_count):
                ch = c_node.characters[i]
                character = <bytes>ch if PY_MAJOR_VERSION < 3 else ch
                target_id = c_node.targets[i] - self.start_node
                transitions[(state, character)] = states[target_id]

        return type(self), (states[0], transitions)

    cpdef finditer(self, bytes data):
        """Iterate over all occurrences of any keyword in the string.

        Returns (keyword, offset) pairs.
        """
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
        assert acora.start_node is not NULL and acora.start_node.matches is NULL
        self.acora = acora
        self.start_node = self.current_node = acora.start_node
        self.match_index = 0
        self.data_char = self.data_start = self.data = data
        self.data_end = self.data_char + len(data)

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
    cdef unsigned char* test_chars
    cdef unsigned char current_char
    cdef int i, found = 0, start, mid, end

    while data_char < data_end:
        current_char = data_char[0]
        data_char += 1
        test_chars = current_node.characters
        if current_char == test_chars[0]:
            current_node = current_node.targets[0]
        elif current_char < test_chars[0] \
                or current_char > test_chars[current_node.char_count-1]:
            current_node = start_node
        else:
            # walk through at most half the characters
            mid = current_node.char_count // 2
            if current_char < test_chars[mid]:
                start = 0
                end = mid
            else:
                start = mid
                end = current_node.char_count

            for i in range(start, end):
                if current_char <= test_chars[i]:
                    if current_char == test_chars[i]:
                        current_node = current_node.targets[i]
                    else:
                        current_node = start_node
                    break
            else:
                current_node = start_node
        if current_node.matches is not NULL:
            found = 1
            break
    _data_char[0] = data_char
    _current_node[0] = current_node
    return found


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
        assert acora.start_node is not NULL and acora.start_node.matches is NULL
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
