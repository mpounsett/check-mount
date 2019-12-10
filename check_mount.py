# -*- coding: utf-8 -*-
# -----------------------------------------------------
# Copyright 2019 OARC Inc
# Matthew Pounsett <matt@NimbusOps.com>
# -----------------------------------------------------

import argparse
import inspect
import logging
import nagiosplugin
import os
import sys
import platform
import subprocess

__version__ = "1.0.0b1"
_log = logging.getLogger('nagiosplugin')

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
        'mount_fields': {
            'target': 2,
            'source': 0,
            'options': 3,
        },
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
    Domain model: Mount points

    Determines if the requested mount points are present.  The `probe` method
    returns a list of all mounts which match the selection criteria.
    """

    def __init__(self, paths=None, types=None, mount_path='/sbin/mount'):
        if paths and types:
            raise(ValueError("paths and types cannot both be set"))

        if paths is not None:
            if type(paths) is str:
                self.PATHS = [paths]
            elif type(paths) is list:
                self.PATHS = paths
            else:
                raise TypeError('paths must be a string or a list')
        else:
            self.PATHS = paths

        if types is not None:
            if type(types) is str:
                self.TYPES = [types.lower()]
            elif type(types) is list:
                self.TYPES = [type.lower() for type in types]
            else:
                raise TypeError('types must be a string or a list')
        else:
            self.TYPES = None

        self.MOUNT_PATH = mount_path

    def process_linux_mount(self, text):
        fields = PLATFORM_OPTIONS['mount_fields']
        detail = {}
        items = text.split()
        detail['target'] = items[fields['target']]
        detail['source'] = items[fields['source']]
        detail['fstype'] = items[fields['fstype']]
        detail['options'] = items[fields['options']]
        return detail

    def process_bsd_mount(self, text):
        fields = PLATFORM_OPTIONS['mount_fields']
        detail = {}
        items = text.split()
        detail['target'] = items[fields['target']]
        detail['source'] = items[fields['source']]
        opts = items[fields['options']].strip('()').split(', ')
        detail['fstype'] = opts.pop(0)
        detail['options'] = '({})'.format(', '.join(opts))
        return detail

    def process_mount_data(self, text):
        results = []
        for line in text.decode().split(os.linesep):
            line = line.strip()
            if line == '':
                continue
            f = getattr(self, PLATFORM_OPTIONS['function'])
            detail = f(line)
            _log.debug("found mount: {!r}".format(detail))
            results.append(detail)
        return results

    def get_mount_data(self):
        cmd = [
            self.MOUNT_PATH,
        ]
        try:
            result = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            output = result.communicate()[0]
        except OSError as e:
            _log.error("mount execution failed {err}".format(err=e))
            raise
        except Exception as e:
            _log.error("unknown error calling mount: {err}".format(err=e))
            raise

        return self.process_mount_data(output)

    def probe(self):
        """
        Return all mount points matching the selection criteria.
        """
        _log.debug('obtaining mount list from mount')
        mount_data = self.get_mount_data()
        # If we have a list of paths, then we're checking that specific paths
        # exist.
        if self.PATHS:
            targets = [mount['target'] for mount in mount_data]
            for path in self.PATHS:
                if path in targets:
                    _log.debug("mount {!r} present".format(path))
                    yield(nagiosplugin.Metric(path, 1, context=path))
                else:
                    _log.debug("mount {!r} missing".format(path))
                    yield(nagiosplugin.Metric(path, 0, context=path))
        # Otherwise, we're just counting mounts
        else:
            mount_count = 0
            for mount in mount_data:
                if self.TYPES and mount['fstype'] in self.TYPES:
                    _log.debug("mount {!r} counted".format(mount['target']))
                    mount_count += 1
                else:
                    if self.TYPES and mount['fstype'] not in self.TYPES:
                        _log.debug(
                            "ignoring mount {!r}: not in user types list".
                            format((mount['target'], mount['fstype']))
                        )
                        continue
                    if mount['fstype'] in IGNORE_TYPES:
                        _log.debug(
                            "ignoring mount {!r}: type in default ignore list".
                            format((mount['target'], mount['fstype']))
                        )
                        continue
                    _log.debug("mount {!r} counted".format(mount['target']))
                    mount_count += 1
            yield nagiosplugin.Metric(
                'total mounts', mount_count, min=0, context='mount'
            )


def parse_args(args=sys.argv[1:]):
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
