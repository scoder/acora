from setuptools import setup
from distutils.extension import Extension

import sys
import os.path

SOURCES = ["acora/_acora", "acora/_cacora"]
BASEDIR = os.path.dirname(__file__)

extensions = [
    Extension("acora._acora", ["acora/_acora.py"]),
    Extension("acora._cacora", ["acora/_cacora.pyx"]),
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
        import Cython
        print("Building with Cython %s" % Cython.__version__)
    else:
        def cythonize(extensions, **kwargs):
            for extension in extensions:
                sources = []
                for sfile in extension.sources:
                    path, ext = os.path.splitext(sfile)
                    if ext in ('.pyx', '.py'):
                        sfile = path + '.c'
                    sources.append(sfile)
                extension.sources[:] = sources
            return extensions
    extensions = cythonize(extensions, annotate=True, language_level=3)
else:
    extensions = []


def read_readme():
    with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as f:
        return f.read()


def parse_version():
    import re
    version = None

    with open(os.path.join(os.path.dirname(__file__), 'acora', '__init__.py')) as f:
        for line in f:
            if line.lstrip().startswith("__version__"):
                version = re.search(r'"([0-9a-z.]+)"', line).group(1)
                break

    if not version:
        raise RuntimeError("Failed to parse version from acora/__init__.py")

    print("Building acora %s" % version)
    return version


setup(
    name="acora",
    version=parse_version(),
    author="Stefan Behnel",
    author_email="stefan_ml@behnel.de",
    maintainer="Stefan Behnel",
    maintainer_email="stefan_ml@behnel.de",
    url="http://pypi.python.org/pypi/acora",

    description="Fast multi-keyword search engine for text strings",

    long_description=read_readme(),

    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Cython',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
        'Topic :: Text Processing',
    ],

    # extension setup

    ext_modules=extensions,
    packages=['acora'],
    extras_require={
        'source': 'Cython>=0.29',
    },
)
