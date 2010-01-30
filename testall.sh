#!/bin/bash

for pyver in 2.5 2.6 3.0 3.1
do
    which python${pyver} >/dev/null || continue
    echo "Running tests with Python $pyver ..."
    rm -f acora/*.so
    _CFLAGS="$CFLAGS -ggdb"
    [ -z "${pyver##2.*}" ] && _CFLAGS="$_CFLAGS -fno-strict-aliasing"
    CFLAGS="$_CFLAGS" PYTHONPATH=~/source/Python/cython/cython-work \
	python${pyver} setup.py build_ext -i
    python${pyver} test.py -v
done
