

# Arbores: File system tree compare tool

Tool to compare filesystem trees and look for missing or differing files and folders.

Intended use case: you are migrating a large file system tree of data from one computer to another, 
recovering from a backup or something alike. 
You want to compare the file system trees between two systems: are files or directories
missing or different? This tool tries to help.


## Features

- Standalone Python 3 script with no dependencies outside standard library, 
  so no need to install anything (as long as a Python 3 interpreter is available)
- Two-phase approach: `scan` (to dump file system tree in JSON format) 
  and `compare` (to compare JSON dumps) 

    - allows to compare file trees between different (possibly unconnected) systems
    - re-run quick `compare` with different settings on same dumps (from slow `scan` phase) 

## Usage example

1. Do a `scan` of the desired directory, dumping to a JSON file

        python3 tree-compare.py scan /path/to/folder > dump1.json

   Do this for each file system tree you want to compare. 

2. Collect the dump files and `compare`:

        python3 tree-compare.py compare dump1.json dump2.json


During `scan` or `compare` it's possible to skip parts of the tree by adding the `--skip`/`-s` option. 
Some examples:
    
    # Skip folders with specific (base)names:
    --skip .git --skip .Trash
    # Skip folders with 'temp' in their name: 
    --skip '*temp*'
    # Skip specific folder
    --skip /home/john/Dropbox
