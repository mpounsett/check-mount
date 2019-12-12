# -*- coding: utf-8 -*-
# -----------------------------------------------------
# Copyright 2019 OARC Inc
# Matthew Pounsett <matt@NimbusOps.com>
# -----------------------------------------------------
"""
An Icinga/Nagios-compatible plugin for checking mount points.

Example Usage
-------------

Insist on 15 mounts being present, and return WARNING or CRITICAL respectively
if the number of mounts is above or below that number:

check-mount -w15:15
check-mount -c15:15

Insist on a minimum of 3 and maximum of 5 mounts of type NFS and EXT4:

check-mount -t nfs -t ext4 -w 3:5

Make sure that three specific mounts are present.  This may be
counterintuitive, but the warning range requires that there be precisely one
of each.

check-mount -p /home -p /var -p /opt -w1:1

"""

import argparse
import inspect
import logging
import os
import platform
import re
import subprocess
import sys

import nagiosplugin

__version__ = "1.0.3"
_LOG = logging.getLogger('nagiosplugin')

IGNORE_TYPES = [
    'autofs',
    'bpf',
    'cgroup',
    'cgroup2',
    'debugfs',
    'devpts',
    'devtmpfs',
    'hugetlbfs',
    'mqueue',
    'proc',
    'pstore',
    'securityfs',
    'sysfs',
    'tmpfs',
]

PLATFORMS = {
    'Linux': {
        'mount_path': '/bin/mount',
        'mount_fields': {
            'target': 2,
            'source': 0,
            'fstype': 4,
            'options': 5,
        },
        'function': 'process_linux_mount',
    },
    'BSD': {
        'mount_path': '/sbin/mount',
        'mount_regex': r"^(.+) on (.+) \((.*)\)$",
        'function': 'process_bsd_mount',
    },
}

# Map the platform.system() output to the key of the PLATFORMS dictionary
# above
PLATFORM_OPTIONS = PLATFORMS[
    {
        'Darwin': 'BSD',
        'FreeBSD': 'BSD',
        'Linux': 'Linux',
    }.get(platform.system())
]


class Mount(nagiosplugin.Resource):
    """
    Domain model: Mount points.

    Determines if the requested mount points are present.  The `probe` method
    returns a list of all mounts which match the selection criteria.
    """

    def __init__(self, paths=None, types=None, mount_path='/sbin/mount'):
        """Create a Mount object."""
        if paths and types:
            raise ValueError("paths and types cannot both be set")

        if paths is not None:
            if isinstance(paths, str):
                self.paths = [paths]
            elif isinstance(paths, list):
                self.paths = paths
            else:
                raise TypeError('paths must be a string or a list')
        else:
            self.paths = paths

        if types is not None:
            if isinstance(types, str):
                self.types = [types.lower()]
            elif isinstance(types, list):
                self.types = [type.lower() for type in types]
            else:
                raise TypeError('types must be a string or a list')
        else:
            self.types = None

        self.mount_path = mount_path

    @classmethod
    def process_linux_mount(cls, text):
        """Process a line of Linux-style mount output to a native structure."""
        fields = PLATFORM_OPTIONS['mount_fields']
        detail = {}
        items = text.split()
        detail['target'] = items[fields['target']]
        detail['source'] = items[fields['source']]
        detail['fstype'] = items[fields['fstype']]
        detail['options'] = items[fields['options']].strip('()').split(',')
        return detail

    @classmethod
    def process_bsd_mount(cls, text):
        """Process a line of BSD-style mount output into a native structure."""
        detail = {}
        result = re.search(PLATFORM_OPTIONS['mount_regex'], text)
        detail['target'] = result.group(1)
        detail['source'] = result.group(2)
        opts = result.group(3).split(', ')
        detail['fstype'] = opts.pop(0)
        detail['options'] = opts
        return detail

    @classmethod
    def process_mount_data(cls, text):
        """
        Process mount output into a native data structure.

        This method takes  one or more lines of output from mount(8) as a
        single string, splits it up into lines, and then passes those lines to
        the appropriate processing function to retrieve a native data
        structure.

        Returns a list of dictionaries.
        """
        results = []
        for line in text.decode().split(os.linesep):
            line = line.strip()
            if line == '':
                continue
            func = getattr(Mount, PLATFORM_OPTIONS['function'])
            detail = func(line)
            _LOG.debug("found mount: %s", detail)
            results.append(detail)
        return results

    def get_mount_data(self):
        """Shell out to run mount(8), return the processed output."""
        cmd = [
            self.mount_path,
        ]
        try:
            result = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            output = result.communicate()[0]
        except OSError as err:
            _LOG.error("mount execution failed: %s", err)
            raise
        except Exception as err:
            _LOG.error("unknown error calling mount: %s", err)
            raise

        return output

    def probe(self):
        """Return all mount points matching the selection criteria."""
        _LOG.debug('obtaining mount list from mount')
        mount_data = Mount.process_mount_data(self.get_mount_data())

        # If we have a list of paths, then we're checking that specific paths
        # exist.
        if self.paths:
            targets = [mount['target'] for mount in mount_data]
            for path in self.paths:
                if path in targets:
                    _LOG.debug("mount %s present", path)
                    yield nagiosplugin.Metric(path, 1, context=path)
                else:
                    _LOG.debug("mount %s missing", path)
                    yield nagiosplugin.Metric(path, 0, context=path)
        # Otherwise, we're just counting mounts
        else:
            mount_count = 0
            for mount in mount_data:
                if self.types and mount['fstype'] in self.types:
                    _LOG.debug("mount %s counted", mount['target'])
                    mount_count += 1
                else:
                    if self.types and mount['fstype'] not in self.types:
                        _LOG.debug(
                            "ignoring mount %s: not in user types list",
                            (mount['target'], mount['fstype'])
                        )
                        continue
                    if mount['fstype'] in IGNORE_TYPES:
                        _LOG.debug(
                            "ignoring mount %s: type in default ignore list",
                            (mount['target'], mount['fstype'])
                        )
                        continue
                    _LOG.debug("mount %s counted", mount['target'])
                    mount_count += 1
            yield nagiosplugin.Metric(
                'total mounts', mount_count, min=0, context='mount'
            )


def parse_args(args=None):
    """Parse cmdline arguments and return an argparse.Namespace object."""
    args = args or sys.argv[1:]

    parser = argparse.ArgumentParser(
        description=inspect.cleandoc(
            """
            """
        ),
    )
    parser.add_argument(
        '-w', '--warning',
        metavar='RANGE',
        default='',
        help=(
            'Generate warning state if number of mounts is outside this range'
        ),
    )
    parser.add_argument(
        '-c', '--critical',
        metavar='RANGE',
        default='',
        help=(
            'Generate critical state if number of mounts is outside this range'
        ),
    )
    parser.add_argument(
        '-p', '--path',
        action='append',
        metavar='PATH',
        help=inspect.cleandoc(
            """
            A mount point to check to ensure it is present. May be specified
            more than once.  This option is incompatible with --type.
            """
        ),
    )
    parser.add_argument(
        '-t', '--type',
        action='append',
        metavar='TYPE',
        help=inspect.cleandoc(
            """
            Only check mounts of a particular type.  If specified more than
            once, the count of present mounts will include all mounts of all
            types specified.  This option is incompatible with --path.
            """
        ),
    )
    parser.add_argument(
        '-M', '--mount-path',
        default=PLATFORM_OPTIONS['mount_path'],
        metavar='PATH',
        help=(
            'Override the path to mount(8) [Default: {}]'.format(
                PLATFORM_OPTIONS['mount_path']
            )
        ),
    )
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help="Increase output verbosity (use up to 3 times).",
    )
    args = parser.parse_args(args)

    # Do some basic tests
    if args.path and args.type:
        parser.error(
            "--path and --type cannot be specified together."
        )
    if not os.access(args.mount_path, os.X_OK):
        parser.error('mount not found at {}'.format(args.mount_path))

    # all good.. return the results
    return args


@nagiosplugin.guarded
def main():
    """Run the check-mount script.  This is the main entrypoint."""
    args = parse_args()
    if args.path:
        contexts = [
            nagiosplugin.ScalarContext(path, args.warning, args.critical) for
            path in args.path
        ]
    else:
        contexts = [
            nagiosplugin.ScalarContext('mount', args.warning, args.critical)
        ]
    check = nagiosplugin.Check(
        Mount(args.path, args.type, args.mount_path),
        *contexts
    )
    check.main(verbose=args.verbose)
