from distutils.core import setup
from distutils.extension import Extension

import sys
import os.path

try:
    sys.argv.remove('--no-compile')
except ValueError:
    try:
        from Cython.Distutils import build_ext
        cmdclass = {'build_ext': build_ext}
        extensions = [Extension("acora._acora", ["acora/_acora.pyx"]),
                      Extension("acora._nfa2dfa", ["acora/nfa2dfa.py"]),
                      ]
    except ImportError:
        cmdclass = {}
        extensions = [Extension("acora._acora", ["acora/_acora.c"]),
                      Extension("acora._nfa2dfa", ["acora/nfa2dfa.c"]),
                      ]
else:
    cmdclass = {}
    extensions = []

version = "1.6"

setup(
    name = "acora",
    version = version,
    author="Stefan Behnel",
    author_email="stefan_ml@behnel.de",
    maintainer="Stefan Behnel",
    maintainer_email="stefan_ml@behnel.de",
    url="http://pypi.python.org/pypi/acora",
    download_url="http://pypi.python.org/packages/source/a/acora/acora-%s.tar.gz" % version,

    description="Fast multi-keyword search engine for text strings",

    long_description = open('README.rst').read(),

    classifiers = [
    'Intended Audience :: Developers',
    'Intended Audience :: Information Technology',
    'License :: OSI Approved :: BSD License',
    'Programming Language :: Cython',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.5',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.0',
    'Programming Language :: Python :: 3.1',
    'Programming Language :: Python :: 3.2',
    'Operating System :: OS Independent',
    'Topic :: Text Processing',
    ],

    # extension setup

    cmdclass = cmdclass,
    ext_modules = extensions,
    packages = ['acora'],
)
