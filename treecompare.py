#!/usr/bin/env python3

import argparse
import contextlib
import fnmatch
import functools
import json
import logging
import os
import re
import sys
from json.encoder import encode_basestring_ascii as str_encode
from pathlib import Path
from typing import Callable, List

log = logging.getLogger('scan')


def main():
    cli = argparse.ArgumentParser()
    subcommands = cli.add_subparsers(help='Sub-command')

    # Sub-command "scan"
    scan_command = subcommands.add_parser(
        'scan', help='Scan directory contents and dump as JSON.'
    )
    scan_command.set_defaults(func=Scanner.main)
    scan_command.add_argument(
        'dir', metavar='DIR', nargs='?', default='.',
        help="Directory to scan. Current directory by default."
    )
    skip_help = "Directory path patterns to skip (can be supplied multiple times)." \
                " Supports Unix shell-style wildcards like '*' and '?'." \
                " For ease of use: if pattern doesn't start with '*', '?' or '/'," \
                " the pattern is automatically prepended with '*/'." \
                " Examples: '.git': skip all directories with basename '.git'," \
                " '/home/john/tmp': skip this particular directory," \
                " '*temp*': skip all folders having 'temp' in their name."
    scan_command.add_argument(
        '-s', '--skip', action='append', default=[],
        help=skip_help
    )
    scan_command.add_argument(
        '-d', '--depth', type=int, default=None,
        help="Maximum directory recursion depth."
    )

    # Sub-command "compare"
    compare_command = subcommands.add_parser(
        'compare', help='Compare two directory scan dumps'
    )
    compare_command.set_defaults(func=Comparer.main)
    compare_command.add_argument(
        'dumps', metavar='DUMP', nargs=2, help='Dumps to compare'
    )
    compare_command.add_argument(
        '-s', '--skip', action='append', default=[],
        help=skip_help
    )
    compare_command.add_argument(
        '--relative', action='store_true', default=False,
        help='Work with relative paths from the scan root.'
             ' Note that --skip options should also be specified in relative fashion'
    )

    arguments = cli.parse_args()
    if not hasattr(arguments, 'func'):
        return cli.print_help()
    arguments.func(arguments)


def get_skip_checker(skip_list: List[str]) -> Callable[[str], bool]:
    """Build function to check whether to skip a path, given list of path patterns."""
    matchers = []
    for p in set(skip_list):
        if p[:1] not in ('*', '?', '/'):
            p = '*/' + p
        matchers.append(re.compile(fnmatch.translate(p), flags=re.IGNORECASE).match)

    return lambda path: any(match(path) for match in matchers)


class Scanner(object):

    @staticmethod
    def main(arguments: argparse.Namespace):
        """
        Main function for the "scan" command
        :param arguments: command line arguments
        """
        path = Path(arguments.dir)
        skip_check = get_skip_checker(arguments.skip)
        max_depth = arguments.depth
        output = sys.stdout.write
        # Top dictionary has just one item with root path as key.
        with Scanner.wrap(output, '{%s:' % str_encode(str(path)), '}'):
            Scanner(output=output, skip_check=skip_check).scan(path, prefix='', max_depth=max_depth)

    def __init__(self, output: Callable[[str], None], indent: str = ' ',
                 skip_check: Callable[[str], bool] = lambda path: False):
        self.output = output
        self.indent = indent
        self.skip_check = skip_check

    def scan(self, path: Path, prefix: str = '', max_depth: int = None):
        """
        Scan given path and write file/directory representation in JSON format to output
        """

        # Handle unreadable directory.
        try:
            listing = os.scandir(path)
        except PermissionError:
            self.output('"<permissionerror>"')
            return

        # First item doesn't require a joiner.
        joiner = ''

        def add_item(item):
            nonlocal joiner
            self.output(f"{joiner}\n{prefix}{item}")
            joiner = ','

        with self.wrap(self.output, "{", "}"):
            for x in listing:
                name = str_encode(x.name)
                if x.is_symlink():
                    # TODO add target of symlink
                    add_item(f'{name}:"symlink"')
                elif x.is_file():
                    add_item(f'{name}:{x.stat().st_size}')
                elif x.is_dir():
                    if max_depth is not None and max_depth <= 0:
                        add_item(f'{name}:"unlisted dir"')
                    elif self.skip_check(x.path):
                        add_item(f'{name}:"skipped dir"')
                    else:
                        add_item(f'{name}:')
                        self.scan(
                            x.path, prefix=prefix + self.indent,
                            max_depth=None if max_depth is None else max_depth - 1
                        )
                else:
                    log.warning(f'Skipping {x.path}')

    @staticmethod
    @contextlib.contextmanager
    def wrap(output, before: str, after: str):
        output(before)
        yield
        output(after)


class Comparer(object):
    """The `compare` command for comparing file tree dumps."""

    @staticmethod
    def main(arguments: argparse.Namespace):
        """
        Main function for the "compare" command
        :param arguments:
        """
        dump_a, dump_b = arguments.dumps
        with open(dump_a) as f:
            tree_a = json.load(f)
        with open(dump_b) as f:
            tree_b = json.load(f)
        skip_check = get_skip_checker(arguments.skip)
        if arguments.relative:
            # Ignore scan root at top level dictionary (which should be only item).
            k, = tree_a.keys()
            tree_a = tree_a[k]
            k, = tree_b.keys()
            tree_b = tree_b[k]
        Comparer(skip_check=skip_check).compare(tree_a, tree_b)

    def __init__(self, skip_check: Callable[[str], bool] = lambda path: False):
        self.skip_check = skip_check

    @staticmethod
    def _report(path, a, b):
        print(f'{a:^12s} {b:^12s} {path}')

    @staticmethod
    def _item_type(x):
        if isinstance(x, dict):
            return 'dir'
        elif isinstance(x, int):
            return 'file'
        elif isinstance(x, str):
            return x
        else:
            raise ValueError(x)

    def compare(self, a: dict, b: dict, prefix: str = ''):
        full_path = functools.partial(os.path.join, prefix)

        for k in sorted(set(a.keys()) | set(b.keys())):
            if k not in b:
                self._report(full_path(k), self._item_type(a[k]), 'n/a')
            elif k not in a:
                self._report(full_path(k), 'n/a', self._item_type(b[k]))
            else:
                a_k = a[k]
                b_k = b[k]
                path = full_path(k)
                if self.skip_check(path):
                    continue
                if isinstance(a_k, dict) and isinstance(b_k, dict):
                    # Two dirs: recurse
                    self.compare(a_k, b_k, prefix=path)
                elif isinstance(a_k, int) and isinstance(b_k, int):
                    # Two files: size compare
                    if a_k != b_k:
                        self._report(path, f'{a_k}b', f'{b_k}b')
                else:
                    # All other cases: compare types
                    a_type = self._item_type(a_k)
                    b_type = self._item_type(b_k)
                    if a_type != b_type:
                        self._report(path, a_type, b_type)


if __name__ == '__main__':
    main()
