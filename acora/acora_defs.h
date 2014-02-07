#ifndef HAS_ACORA_DEFS_H
#define HAS_ACORA_DEFS_H

#if PY_VERSION_HEX <= 0x03030000 && !(defined(CYTHON_PEP393_ENABLED) && CYTHON_PEP393_ENABLED)
  #define PyUnicode_IS_READY(op)    (0)
  #define PyUnicode_GET_LENGTH(u)   PyUnicode_GET_SIZE(u)
  #define PyUnicode_KIND(u)         (sizeof(Py_UNICODE))
  #define PyUnicode_DATA(u)         ((void*)PyUnicode_AS_UNICODE(u))
  #define PyUnicode_WCHAR_KIND      0
  #define PyUnicode_READ(kind, data, index)   \
        (((void)kind), (Py_UCS4) ((Py_UNICODE*)data)[index])
#endif

#endif /* HAS_ACORA_DEFS_H */
