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
# ==============================================================================
#  Copyright 2019-2022 Matthew Pounsett <matt@conundrum.com>
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ==============================================================================

import argparse
import inspect
import logging
import os
import platform
import re
import subprocess
import sys

from typing import Dict, List

import nagiosplugin

__version__ = "1.1.0"
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

MOUNT_PATH = {
    'Darwin': '/sbin/mount',
    'FreeBSD': '/sbin/mount',
    'Linux': '/bin/mount',
}.get(platform.system(), '/sbin/mount')


class Mount(nagiosplugin.Resource):
    """
    Domain model: Mount points.

    Determines if the requested mount points are present.  The `probe` method
    returns a list of all mounts which match the selection criteria.
    """

    name = 'Mount'

    def __init__(self,
                 paths: List[str] = None, types: List[str] = None,
                 mount_path: str = MOUNT_PATH):
        """Create a Mount object."""
        if paths and types:
            raise ValueError("paths and types cannot both be set")

        if paths is not None:
            self.paths = paths
        else:
            self.paths = []

        if types is not None:
            self.types = [mount_type.lower() for mount_type in types]
        else:
            self.types = []

        self.mount_path = mount_path

    @classmethod
    def process_mount_line(cls, text) -> Dict:
        """Abstract method that should be replaced by subclassing."""
        raise NotImplementedError(
            "Mount must be subclassed and process_mount_line overridden"
        )

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
            detail = cls.process_mount_line(line)
            _LOG.debug("found mount: %s", detail)
            results.append(detail)
        return results

    def get_mount_data(self):
        """Shell out to run mount(8), return the processed output."""
        cmd = [
            self.mount_path,
        ]
        try:
            with subprocess.Popen(cmd, stdout=subprocess.PIPE) as result:
                return result.communicate()[0]
        except OSError as err:
            _LOG.error("mount execution failed: %s", err)
            raise
        except Exception as err:
            _LOG.error("unknown error calling mount: %s", err)
            raise

    def probe(self):
        """Return all mount points matching the selection criteria."""
        _LOG.debug('obtaining mount list from mount')
        mount_class = MountFactory.get_mount_class()
        mount_data = mount_class.process_mount_data(self.get_mount_data())

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
                if self.types and mount['filesystem_type'] in self.types:
                    _LOG.debug("mount %s counted", mount['target'])
                    mount_count += 1
                else:
                    if (
                        self.types
                        and mount['filesystem_type'] not in self.types
                    ):
                        _LOG.debug(
                            "ignoring mount %s: not in user types list",
                            (mount['target'], mount['filesystem_type'])
                        )
                        continue
                    if mount['filesystem_type'] in IGNORE_TYPES:
                        _LOG.debug(
                            "ignoring mount %s: type in default ignore list",
                            (mount['target'], mount['filesystem_type'])
                        )
                        continue
                    _LOG.debug("mount %s counted", mount['target'])
                    mount_count += 1
            yield nagiosplugin.Metric(
                'total mounts', mount_count, min=0, context='mount'
            )


class BSDMount(Mount):
    """
    Domain model: Mount points.

    Determines if the requested mount points are present.  The `probe` method
    returns a list of all mounts which match the selection criteria.
    """

    @classmethod
    def process_mount_line(cls, text) -> Dict:
        """Process a line of BSD-style mount output into a native structure."""
        detail = {}
        mount_regex = r"^(.+) on (.+) \((.*)\)$"
        result = re.search(mount_regex, text)
        if result is not None:
            detail['source'] = result.group(1)
            detail['target'] = result.group(2)
            opts = result.group(3).split(', ')
            detail['filesystem_type'] = opts.pop(0)
            detail['options'] = opts
        _LOG.debug("Got mount info: %s", detail)
        return detail


class LinuxMount(Mount):
    """
    Domain model: Mount points.

    Determines if the requested mount points are present.  The `probe` method
    returns a list of all mounts which match the selection criteria.
    """

    @classmethod
    def process_mount_line(cls, text) -> Dict:
        """Process a line of Linux-style mount output into a dict."""
        detail = {}
        mount_regex = r"^(.+) on (.+) type (.+) \((.*)\)$"
        result = re.search(mount_regex, text)
        if result is not None:
            detail['source'] = result.group(1)
            detail['target'] = result.group(2)
            detail['filesystem_type'] = result.group(3)
            opts = result.group(4).split(', ')
            detail['options'] = opts
        _LOG.debug("Got mount info: %s", detail)
        return detail


# No need for more methods in a factory class
# pylint: disable-next=too-few-public-methods
class MountFactory:
    """Returns the appropriate Mount subclass for the platform."""

    @staticmethod
    def get_mount_class(paths: List[str] = None,
                        types: List[str] = None,
                        mount_path: str = MOUNT_PATH) -> Mount:
        """
        Return an instance of the appropriate Mount subclass.

        Maps platform.system() to a dictionary of OS names mapped to Mount
        subclasses.
        """
        class_map = {
            'Darwin': BSDMount,
            'FreeBSD': BSDMount,
            'Linux': LinuxMount,
        }
        os_name = platform.system()
        try:
            new_class = class_map[os_name]
        except KeyError:
            raise NotImplementedError(f"OS {os_name} not supported") from None
        return new_class(paths, types, mount_path)


def parse_args(args=None) -> argparse.Namespace:
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
        default=MOUNT_PATH,
        metavar='PATH',
        help=f"Override the path to mount(8) [Default: {MOUNT_PATH}]",
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
        parser.error(f"mount not found at {args.mount_path}")

    # all good... return the results
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
    mount_class = MountFactory.get_mount_class(args.path, args.type,
                                               args.mount_path)
    check = nagiosplugin.Check(mount_class, *contexts)
    check.main(verbose=args.verbose)
