#!/bin/bash

[ -z "$1" ] && VERSIONS="2.5 2.6 2.7 3.0 3.1 3.2" || VERSIONS="$1"

FAILED=

for pyver in $VERSIONS
do
    which python${pyver} >/dev/null || continue
    echo "Running tests with Python $pyver ..."
    rm -f acora/*.so
    _CFLAGS="$CFLAGS -ggdb"
    [ -z "${pyver##2.*}" ] && _CFLAGS="$_CFLAGS -fno-strict-aliasing"
    CFLAGS="$_CFLAGS" python${pyver} setup.py build_ext -i
    python${pyver} test.py || FAILED="$FAILED $pyver"
done

[ -n "$FAILED" ] && echo "FAILED: $FAILED" || echo "DONE."
