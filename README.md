

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

The basic usage is as follows

1. Do a `scan` of the desired directory, dumping to a JSON file

        python3 treecompare.py scan /path/to/folder > dump1.json

   Do this for each file system tree you want to compare. 

2. Collect the dump files and `compare`:

        python3 treecompare.py compare dump1.json dump2.json

   Which results in something like
   
        n/a                   bar/bo
         6b          12b      bar/lorem.txt
                     n/a      bar/baz/lorem.txt
        dir        not dir    foo
   
   In this example: `bar/bo` is missing from first tree, 
   `bar/baz/lorem.txt` is missing from the second, 
   `bar/lorem.txt` differs in size
   and `foo` is a directory in the first tree but not in the second 
   (e.g. a file instead). 
 

### Options and finetuning

- During `scan` or `compare` it is possible to skip parts of the trees by adding the `--skip`/`-s` option. 
  Some examples:

        # Skip folders with specific (base)names:
        --skip .git --skip .Trash
        # Skip folders with 'temp' in their name: 
        --skip '*temp*'
        # Skip specific folder
        --skip /home/john/Dropbox

  Note that `scan` typically takes longer than `compare`, 
  so it is recommended to experiment with `--skip` during `compare` phase. 

- If you want to compare different directories or scan roots within same file system
  (as opposed to same scan roots in separate file systems), you want to compare 
  relative paths from these scan roots. When doing `compare` add option:
   
        --relative
  
  Note that this also impacts the `--skip` option. 


