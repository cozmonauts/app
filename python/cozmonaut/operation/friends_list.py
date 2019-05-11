#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

from cozmonaut.operation import AbstractOperation


class OperationFriendsList(AbstractOperation):
    """
    The friends list operation.

    Per user request, we list one or more friends. See the __init__ function for
    details on argument structure.
    """

    def __init__(self, args: dict):
        """
        Initialize friends list operation.

        TODO: Add details about arguments

        :param args: The dictionary of string arguments
        """
        super().__init__(args)

    def start(self):
        """
        Start the friends list operation.
        """
        super().start()

        print('start friends list')

    def stop(self):
        """
        Stop the friends list operation.
        """
        super().stop()

        print('stop friends list')
