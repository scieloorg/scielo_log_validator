#!/usr/bin/env python2.7
import os, setuptools

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md")) as f:
    README = f.read()

requires = [
    'ipaddress',
    'python-magic',
    'six',
]

tests_require = [
]

setuptools.setup(
    name="scielo-log-validator",
    version="0.5.1",
    author="SciELO",
    author_email="scielo-dev@googlegroups.com",
    description="",
    long_description=README,
    long_description_content_type="text/markdown",
    license="2-clause BSD",
    packages=setuptools.find_packages(
        exclude=["*.tests", "*.tests.*", "tests.*", "tests"]
    ),
    include_package_data=True,
    extras_require={"testing": tests_require},
    install_requires=requires,
    dependency_links=[
    ],
    python_requires=">=2.7",
    test_suite="tests",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Other Environment",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 2 :: Only",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'console_scripts': [
            'log_validator=scielo_log_validator.validator:main',
        ],
    },
)
