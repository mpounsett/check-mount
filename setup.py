# -*- coding: utf-8 -*-
# -----------------------------------------------------
# Copyright 2019, Matthew Pounsett <matt@conundrum.com>
# -----------------------------------------------------
import os
import re

from io import open
from setuptools import setup, find_packages


HERE = os.path.abspath(os.path.dirname(__file__))


def read(path):
    with open(os.path.join(HERE, path), 'r', encoding='utf-8') as fp:
        return fp.read()


def find_version(path):
    version_file = read(path)
    version_match = re.search(
        r"^__version__ = ['\"]([^'\"]*)['\"]",
        version_file,
        re.M,
    )
    if version_match:
        return version_match.group(1)
    raise(RuntimeError("Unable to find version."))


setup(
    name="check-mount",
    version=find_version('check_mount.py'),
    description="Nagios / Icinga plugin to check that mounts are present.",
    long_description=read('README.rst'),
    keywords=['Icinga', 'Nagios', 'monitoring'],
    url="https://check-mount.readthedocs.io/",
    download_url='https://pypi.org/project/check-mount/',
    project_urls={
        'check-mount source':
        'https://github.com/mpounsett/check-mount',

        'check-mount issues':
        'https://github.com/mpounsett/check-mount/issues',
    },
    author="Matthew Pounsett",
    author_email="matt@conundrum.com",
    license="Apache Software License 2.0",

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Environment :: Console',
        'Natural Language :: English',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX :: BSD :: FreeBSD',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: System :: Monitoring',
        'Topic :: System :: Networking :: Monitoring',
    ],

    packages=find_packages(),
    scripts=['check_mount.py'],
    install_requires=[
        'nagiosplugin >=1.3, <2.0',
    ],

    entry_points={
        'console_scripts': [
            'check_mount = check_mount:main',
        ],
    },
)
