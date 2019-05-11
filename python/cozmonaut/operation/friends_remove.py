#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

from cozmonaut.operation import AbstractOperation


class OperationFriendsRemove(AbstractOperation):
    """
    The friends remove operation.

    Per user request, we remove one or more friends. See the __init__ function
    for details on argument structure.
    """

    def __init__(self, args: dict):
        """
        Initialize friends remove operation.

        TODO: Add details about arguments

        :param args: The dictionary of string arguments
        """
        super().__init__(args)

    def start(self):
        """
        Start the friends remove operation.
        """
        super().start()

        print('start friends remove')

    def stop(self):
        """
        Stop the friends remove operation.
        """
        super().stop()

        print('stop friends remove')
