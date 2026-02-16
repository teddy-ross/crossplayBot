"""Build script for Cython extensions.

Usage:
    python setup_cython.py build_ext --inplace

This compiles crossplay/engine_cy.pyx and crossplay/simulation_cy.pyx
into shared-object (.so / .pyd) files that Python can import directly.
"""

from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        "crossplay.engine_cy",
        ["crossplay/engine_cy.pyx"],
    ),
    Extension(
        "crossplay.simulation_cy",
        ["crossplay/simulation_cy.pyx"],
    ),
]

setup(
    name="crossplay-cython",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
        },
    ),
)
