About
=====

**check_mount** is a Nagios/Icinga plugin for checking for the presence of
mounted filesystems.  

Sometimes, it is only important to monitor the presence of a mount, and not
the amount of free (or used) storage on that filesystem.  For example, when
monitoring NFS clients it may be redundant to use **check_disk** to monitor
the NFS mounts because the amount of free storage on those mounts is monitored
elsewhere.  Additionally, **check_disk** can give a false negative if the
filesystem is not mounted at all, but the directory used as a mount point is
present.


Usage
=====

.. code:: text

   usage: check_mount [-h] [-w RANGE] [-c RANGE] [-p PATH] [-t TYPE] [-M PATH]
                      [-v]

   optional arguments:
     -h, --help            show this help message and exit
     -w RANGE, --warning RANGE
                           Generate warning state if number of mounts is outside
                           this range
     -c RANGE, --critical RANGE
                           Generate critical state if number of mounts is
                           outside this range
     -p PATH, --path PATH  A mount point to check to ensure it is present. May
                           be specified more than once. This option is
                           incompatible with --type.
     -t TYPE, --type TYPE  Only check mounts of a particular type. If specified
                           more than once, the count of present mounts will
                           include all mounts of all types specified. This
                           option is incompatible with --path.
     -M PATH, --mount-path PATH
                           Override the path to mount(8) [Default: /sbin/mount]
     -v, --verbose         Increase output verbosity (use up to 3 times).

Counting Mounts
---------------

If you're only concerned with making sure the correct number of mounts are
present, you can set a warning/critical range.

To warn if anything other than exactly 5 filesystems are mounted::

   check_mount -w 5:5

To retun critical if fewer than 5 filesystems are mounted, and a warning if
more than 5 are mounted::

   check_mount -w :5 -c 5:

Checking Mounts by Type
-----------------------

If you're only concerned with a particular type of mount, for example you want
to ensure that all of your network mounts are present, but ignore any others,
you can supply a list of filesystem types to **check_mount**.

To look only at AFS and NFS mounts, and to expect exactly 2 total mounts (one
of each)::

   check_mount -t NFS -t AFS -w 2:2

By default, **check_mount** ignores several filessytem pseudo-types.  Ignoring
these can be overridden by specifying them, along with any other types you
would like to check, on the command line.  Filesystem types ignored by default
are::

    autofs      bpf         cgroup      cgroup2     debugfs
    devpts      devtmpfs    hugetlbfs   mqueue      proc
    pstore      securityfs  sysfs       tmpfs

Checking Specific Mount Points
------------------------------

If you wish to check specific mount points you can specify one or more on the
command line with the `--path` argument::

   check_mount -p /home -w1:1

Unlike other modes of operation, when checking specific mount points
**check_mount** applies the warning and critical ranges to each individual
mount, rather than the sum of all mounts.  This allows **check_mount** to
include the names of specific mounts in its error message.  So, if you're
checking three different mount points this way, and you want to return a
critical alert if any of them are missing, you would use a command like this::

   check_mount -p /home -p /var -p /opt -c1:1

