#!/usr/bin/env python3

import argparse
import contextlib
import fnmatch
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
    scan_command.set_defaults(func=scan_main)
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

    # Sub-command "compare"
    compare_command = subcommands.add_parser(
        'compare', help='Compare two directory scan dumps'
    )
    compare_command.set_defaults(func=compare_main)
    compare_command.add_argument(
        'dumps', metavar='DUMP', nargs=2, help='Dumps to compare'
    )
    compare_command.add_argument(
        '-s', '--skip', action='append', default=[],
        help=skip_help
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


def scan_main(arguments: argparse.Namespace):
    """
    Main function for the "scan" command
    :param arguments: command line arguments
    """
    path = Path(arguments.dir)
    skip_check = get_skip_checker(arguments.skip)
    output = sys.stdout.write
    # Top dictionary hase just one item with root path as key.
    with wrap(output, f'{{{str_encode(str(path))}:', '}'):
        _scan(path, output=output, prefix='', skip_check=skip_check)


def _scan(path: Path, output: Callable[[str], None], prefix: str = '', indent: str = ' ',
          skip_check: Callable[[str], bool] = lambda path: False):
    """
    Scan given path and write file/directory representation in JSON format to output
    """

    # Handle unreadable directory.
    try:
        listing = os.scandir(path)
    except PermissionError:
        output('"<permissionerror>"')
        return

    # First item doesn't require a joiner.
    joiner = ''

    def add_item(item):
        nonlocal joiner
        output(f"{joiner}\n{prefix}{item}")
        joiner = ','

    with wrap(output, "{", "}"):
        for x in listing:
            name = str_encode(x.name)
            if x.is_symlink():
                add_item(f'{name}:"<symlink>"')
            elif x.is_file():
                add_item(f'{name}:{x.stat().st_size}')
            elif x.is_dir():
                if skip_check(x.path):
                    add_item(f'{name}:"<skip>"')
                else:
                    add_item(f'{name}:')
                    _scan(x.path, output=output, prefix=prefix + indent, skip_check=skip_check)
            else:
                log.warning(f'Skipping {x.path}')


@contextlib.contextmanager
def wrap(output, before: str, after: str):
    output(before)
    yield
    output(after)


def compare_main(arguments: argparse.Namespace):
    """
    Main function for the "compare" command
    :param arguments:
    """
    # TODO options to skip dirs
    # TODO Relative path mode
    dump_a, dump_b = arguments.dumps
    with open(dump_a) as f:
        tree_a = json.load(f)
    with open(dump_b) as f:
        tree_b = json.load(f)
    skip_check = get_skip_checker(arguments.skip)
    compare(tree_a, tree_b, skip_check=skip_check)


def compare(a: dict, b: dict, prefix: str = '',
            skip_check: Callable[[str], bool] = lambda path: False):
    a_keys = set(a.keys())
    b_keys = set(b.keys())
    only_a = a_keys.difference(b_keys)
    only_b = b_keys.difference(a_keys)
    both = a_keys.intersection(b_keys)

    prefix = prefix.rstrip('/')
    if prefix:
        def full_path(name):
            return f'{prefix}/{name}'
    else:
        def full_path(name):
            return name

    def report(path, a, b):
        print(f'{a:^12s} {b:^12s} {path}')

    for k in only_a:
        report(full_path(k), '', 'n/a')
    for k in only_b:
        report(full_path(k), 'n/a', '')

    for k in both:
        a_k = a[k]
        b_k = b[k]
        path = full_path(k)
        if skip_check(path):
            continue
        if isinstance(a_k, dict):
            if isinstance(b_k, dict):
                # Recurse
                compare(a_k, b_k, prefix=path, skip_check=skip_check)
            else:
                report(path, 'dir', 'not dir')
        else:
            if isinstance(b_k, dict):
                report(path, 'not dir', 'dir')
            else:
                # File compare
                if a_k != b_k:
                    report(path, f'{a_k}b', f'{b_k}b')


if __name__ == '__main__':
    main()
