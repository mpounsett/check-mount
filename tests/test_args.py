# -*- coding: utf-8 -*-
import argparse
import os
import unittest

import check_mount


class TestArgs(unittest.TestCase):
    def test_args_path_list(self):
        test_args = [
            '-p', '/foo',
            '-p', '/bar',
            '-p', '/baz'
        ]
        args = check_mount.parse_args(test_args)
        self.assertIsInstance(args, argparse.Namespace)
        self.assertIsInstance(args.path, list)
        self.assertEqual(len(args.path), 3)
        self.assertIn('/foo', args.path)
        self.assertIn('/bar', args.path)
        self.assertIn('/baz', args.path)

    def test_args_type_list(self):
        test_args = [
            '-t', 'nfs',
            '-t', 'ext4',
        ]
        args = check_mount.parse_args(test_args)
        self.assertIsInstance(args, argparse.Namespace)
        self.assertIsInstance(args.type, list)
        self.assertEqual(len(args.type), 2)
        self.assertIn('nfs', args.type)
        self.assertIn('ext4', args.type)

    def test_args_path_list_conflict(self):
        test_args = [
            '-t', 'nfs',
            '-p', '/foo',
        ]
        with self.assertRaises(SystemExit):
            check_mount.parse_args(test_args)

    def test_args_working_mount(self):
        mount_paths = [
            '/bin/mount',
            '/sbin/mount',
        ]
        mount = [path for path in mount_paths if os.access(path, os.X_OK)][0]
        test_args = [
            '-M', mount,
        ]
        args = check_mount.parse_args(test_args)
        self.assertEqual(args.mount_path, mount)

    def test_args_missing_mount(self):
        test_args = [
            '-M', '/nonexistant',
        ]
        with self.assertRaises(SystemExit):
            check_mount.parse_args(test_args)
