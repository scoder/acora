from distutils.core import setup
from distutils.extension import Extension

try:
    from Cython.Distutils import build_ext
    cmdclass = {'build_ext': build_ext}
    source_ext = 'pyx'
except ImportError:
    build_ext = None
    cmdclass = {}
    source_ext = 'c'

version = "1.0"

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

    long_description="""\
Acora is 'fgrep' for Python, a fast multi-keyword text search engine.

Based on a set of keywords, it generates a search automaton (DFA) and
runs it over string input, either unicode or bytes.

Features include:

* works with unicode strings and byte strings
* about 2-3x as fast as Python's regular expression engine
* finds overlapping matches, i.e. all matches of all keywords
* support for case insensitive search (~10x as fast as 're')
* frees the GIL while searching
* additional (slow but short) pure Python implementation
* support for Python 2.4+ and 3.x
""",

    classifiers = [
    'Intended Audience :: Developers',
    'Intended Audience :: Information Technology',
    'License :: OSI Approved :: BSD License',
    'Programming Language :: Cython',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.4',
    'Programming Language :: Python :: 2.5',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.1',
    'Operating System :: OS Independent',
    'Topic :: Text Processing',
    ],

    # extension setup

    cmdclass = {'build_ext': build_ext},
    ext_modules = [Extension("acora._acora",
                             ["acora/_acora."+source_ext])],
    packages = ['acora'],
)
