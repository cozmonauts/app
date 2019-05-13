#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

"""
Main command-line app by The Cozmonauts.

Usage:
    cozmonaut interact [-a <sera> | --robot-a=<sera>] [-b <serb> | --robot-b=<serb>]
    cozmonaut (-h | --help | --version)

Options:
    -h, --help      Show help information.
    --version       Show version information.
"""

import time

from docopt import docopt

from cozmonaut import __version__
from cozmonaut.operation.interact import InteractInterface, OperationInteract


def do_interact(sera: str, serb: str):
    """
    Carry out interacting with people.

    :param sera: Serial number for robot A or None to ignore it
    :param serb: Serial number for robot B or None to ignore it
    """

    # Arguments for interaction
    args = {}

    # Add robot A serial number if given
    if sera is not None:
        args['sera'] = sera

        # Update interact mode
        # We're for sure using robot A, but we're standing by for B
        args['mode'] = 'just_a'

    # Add robot B serial number if existent
    if serb is not None:
        args['serb'] = serb

        # Update interact mode
        # If we're using robot A, then upgrade to both A and B
        # Otherwise, we're just using robot B
        if args.get('mode') == 'just_a':
            args['mode'] = 'both'
        else:
            args['mode'] = 'just_b'

    # Require at least one robot serial number
    if args.get('mode') is None:
        print('Need to specify at least one robot')
        exit(1)

    # Start the operation in the background
    # We need to keep the foreground (main thread) open for the terminal interface
    op = OperationInteract(args)
    op.start()

    # Give the operation a few seconds to set up
    time.sleep(3)

    # Run the terminal interface for the interact operation
    # This internally registers a SIGINT handler
    iface = InteractInterface(op)
    iface.cmdloop()

    # Print a message if the operation completed without assistance
    if not op.is_running():
        print('The operation completed naturally')

    # This brings the Cozmos back to their chargers and cleans up resources
    op.stop()


if __name__ == '__main__':
    # Parse command-line arguments
    args = docopt(__doc__, version=__version__)

    if args['interact']:
        # Do interactive mode
        do_interact(
            sera=args.get('<sera>') or args.get('--robot-a'),
            serb=args.get('<serb>') or args.get('--robot-b'),
        )
