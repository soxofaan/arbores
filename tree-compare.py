#!/usr/bin/env python3

import argparse
import contextlib
import json
import logging
import os
import sys
from fnmatch import fnmatch
from json.encoder import encode_basestring_ascii as str_encode
from pathlib import Path
from typing import Callable, Set

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
    scan_command.add_argument(
        '-s', '--skip', action='append', default=[],
        help="Directory name to skip, e.g. '.git' or '.Trash'. "
             "Unix shell-style wildcards like '*' and '?' are supported. "
             "Can be supplied multiple times."
    )

    # Sub-command "compare"
    compare_command = subcommands.add_parser(
        'compare', help='Compare two directory scan dumps'
    )
    compare_command.set_defaults(func=compare_main)
    compare_command.add_argument(
        'dumps', metavar='DUMP', nargs=2, help='Dumps to compare'
    )

    arguments = cli.parse_args()
    if not hasattr(arguments, 'func'):
        return cli.print_help()
    arguments.func(arguments)


def scan_main(arguments: argparse.Namespace):
    """
    Main function for the "scan" command
    :param arguments: command line arguments
    """
    path = Path(arguments.dir)
    dirs_to_skip = set(arguments.skip)
    output = sys.stdout.write
    with wrap(output, f'{{{str_encode(str(path))}:', '}'):
        _scan(path, output=output, prefix='', dirs_to_skip=dirs_to_skip)


def _scan(path: Path, output: Callable[[str], None], prefix: str = '', indent: str = ' ',
          dirs_to_skip: Set[str] = None):
    """
    Scan given path and write file/directory representation in JSON format to output
    """
    dirs_to_skip = dirs_to_skip or set()

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
                if any(fnmatch(x.name, p) for p in dirs_to_skip):
                    add_item(f'{name}:"<skip>"')
                else:
                    add_item(f'{name}:')
                    _scan(x.path, output=output, prefix=prefix + indent, dirs_to_skip=dirs_to_skip)
            else:
                log.warning(f'Skipping {x.path}')


@contextlib.contextmanager
def wrap(output, before: str, after: str):
    output(before)
    yield
    output(after)


def compare_main(arguments):
    # TODO options to skip dirs
    dump_a, dump_b = arguments.dumps
    with open(dump_a) as f:
        tree_a = json.load(f)
    with open(dump_b) as f:
        tree_b = json.load(f)

    compare(tree_a, tree_b)


def _report(path, a, b):
    print(f'{a:^12s} {b:^12s} {path}')


def compare(a: dict, b: dict, prefix: str = ''):
    a_keys = set(a.keys())
    b_keys = set(b.keys())
    only_a = a_keys.difference(b_keys)
    only_b = b_keys.difference(a_keys)
    both = a_keys.intersection(b_keys)

    prefix = prefix.rstrip('/')
    if prefix:
        def _path(name):
            return f'{prefix}/{name}'
    else:
        def _path(name):
            return name

    for k in only_a:
        _report(_path(k), '', 'n/a')
    for k in only_b:
        _report(_path(k), 'n/a', '')

    for k in both:
        a_k = a[k]
        b_k = b[k]
        if isinstance(a_k, dict):
            if isinstance(b_k, dict):
                # Recurse
                compare(a_k, b_k, prefix=_path(k))
            else:
                _report(_path(k), 'dir', 'file')
        else:
            if isinstance(b_k, dict):
                _report(_path(k), 'file', 'dir')
            else:
                # File compare
                if a_k != b_k:
                    _report(_path(k), f'{a_k}b', f'{b_k}b')


if __name__ == '__main__':
    main()
