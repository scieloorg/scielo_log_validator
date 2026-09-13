#!/usr/bin/env python3
import os, setuptools

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md")) as f:
    README = f.read()

requires = [
    'python-magic',
]

tests_require = [
]

setuptools.setup(
    name="scielo-log-validator",
    version="2.0.4",
    author="Rafael JP Damaceno",
    author_email="rafael@pitangainnovare.com.br",
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
    python_requires=">=3.8",
    test_suite="tests",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Other Environment",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'console_scripts': [
            'log_validator=scielo_log_validator.validator:main',
        ],
    },
)
