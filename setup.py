from distutils.core import setup
from distutils.extension import Extension

import sys
import os.path

SOURCES = ["acora/_acora", "acora/_nfa2dfa"]
BASEDIR = os.path.dirname(__file__)

extensions = [
    Extension("acora._acora", ["acora/_acora.pyx"]),
    Extension("acora._nfa2dfa", ["acora/_nfa2dfa.py"]),
]

try:
    sys.argv.remove('--with-cython')
except ValueError:
    USE_CYTHON = False
else:
    USE_CYTHON = True

try:
    sys.argv.remove('--no-compile')
except ValueError:
    if not all(os.path.exists(os.path.join(BASEDIR, sfile+'.c'))
               for sfile in SOURCES):
        print("WARNING: Generated .c files are missing,"
              " enabling Cython compilation")
        USE_CYTHON = True

    if USE_CYTHON:
        from Cython.Build import cythonize
    else:
        def cythonize(extensions):
            for extension in extensions:
                sources = []
                for sfile in extension.sources:
                    path, ext = os.path.splitext(sfile)
                    if ext in ('.pyx', '.py'):
                        sfile = path + '.c'
                    sources.append(sfile)
                extension.sources[:] = sources
            return extensions
    extensions = cythonize(extensions)
else:
    extensions = []


version = "1.8pre"

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
    'Programming Language :: Python :: 3.1',
    'Programming Language :: Python :: 3.2',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'Operating System :: OS Independent',
    'Topic :: Text Processing',
    ],

    # extension setup

    ext_modules = extensions,
    packages = ['acora'],
)
