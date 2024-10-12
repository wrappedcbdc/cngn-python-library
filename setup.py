#!/usr/bin/env python
import os
from setuptools import setup, find_packages

# Dictionary to hold package metadata
about = {}
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "cngn_manager", "__version__.py"), "r", encoding="utf-8") as f:
    exec(f.read(), about)
with open(os.path.join(here, "README.md"), "r", encoding="utf-8") as f:
    readme = f.read()

# Define package dependencies
requires = [
    "requests",
    "cryptography==43.0.1",
    "pynacl==1.5.0",
    "mnemonic==0.20",
    "bip32utils==0.3.post4",
    "hashlib",
    "tronpy",
    "stellar-sdk==11.1.0",
]

# Define test dependencies
test_requirements = [
    "pytest-httpbin==2.1.0",
    "pytest-cov",
    "pytest-mock",
    "pytest-xdist",
    "PySocks>=1.5.6, !=1.5.7",
    "pytest>=3",

]

# Setup function to handle packaging
setup(
    name=about["__title__"],
    version=about["__version__"],
    description=about["__description__"],
    author=about["__author__"],
    author_email=about["__author_email__"],
    license=about["__license__"],
    url=about["__url__"],
    long_description=readme,
    long_description_content_type="text/markdown",
    install_requires=requires,
    python_requires=">=3.8",
    packages=find_packages(),
    project_urls={
        "Documentation": about["__url__"],
        "Source": "https://github.com/wrappedcbdc/cngn-pyhon-library.git",
    }
)
