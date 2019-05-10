#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

from abc import abstractmethod, ABC


class Operation(ABC):
    """
    An abstract operation.
    """

    @abstractmethod
    def __init__(self, args: dict):
        pass

    @abstractmethod
    def start(self):
        """
        Start the operation.
        """
        pass

    @abstractmethod
    def stop(self):
        """
        Stop the operation.
        """
        pass

    @abstractmethod
    def is_running(self):
        """
        Check if the operation is running.

        :return: True if such is the case, otherwise False
        """
        return False
