#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

"""
Main command-line app by The Cozmonauts.

Usage:
    cozmonaut (ls | list-friends) [<friend>...]
    cozmonaut (rm | remove-friends) <friend>...
    cozmonaut go [-a <sera> | --robot-a=<sera>] [-b <serb> | --robot-b=<serb>]
    cozmonaut (-h | --help | --version)

Options:
    -h, --help      Show help information.
    --version       Show version information.
"""

from docopt import docopt

from .__version__ import __version__

if __name__ == '__main__':
    # Parse command-line arguments
    args = docopt(__doc__, version=__version__)
