#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

"""
Main command-line app by The Cozmonauts.

Usage:
    cozmonaut (ls | list-friends) [<friend>...]
    cozmonaut (rm | remove-friends) <friend>...
    cozmonaut interact [-a <sera> | --robot-a=<sera>] [-b <serb> | --robot-b=<serb>]
    cozmonaut (-h | --help | --version)

Options:
    -h, --help      Show help information.
    --version       Show version information.
"""

import time

from docopt import docopt

from cozmonaut import __version__
from cozmonaut.operation.interact import OperationInteract


def do_list_friends():
    """
    Carry out listing friends.
    """

    print('list')


def do_remove_friends():
    """
    Carry out removing friends.
    """

    print('remove')


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

    # Start the operation
    op = OperationInteract(args)
    op.start()

    # Sleep until operation stops or interrupted (e.g. via ^C on a terminal)
    while op.is_running():
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break

    # Print a message indicating we made it this far
    if not op.is_running():
        print('The operation completed naturally')

    # This brings the Cozmos back to their chargers and cleans up resources
    op.stop()


if __name__ == '__main__':
    # Parse command-line arguments
    args = docopt(__doc__, version=__version__)

    if args['ls'] or args['list-friends']:
        # Do friend(s) listing
        do_list_friends()
    elif args['rm'] or args['remove-friends']:
        # Do friend(s) removal
        do_remove_friends()
    elif args['interact']:
        # Do interactive mode
        do_interact(
            sera=args.get('<sera>') or args.get('--robot-a'),
            serb=args.get('<serb>') or args.get('--robot-b'),
        )
