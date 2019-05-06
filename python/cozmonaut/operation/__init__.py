#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

from abc import ABC, abstractmethod


class AbstractOperation(ABC):
    """
    An operation is a piece of the Python code that governs one operable action
    that the user can command on startup. They roughly align with cmdline args.

    Operations are asynchronous. You can start and stop them at will.
    """

    @abstractmethod
    def __init__(self, args: dict):
        """
        Initialize the operation.

        Each operation can accept a number of string/string mappings as
        arguments. See the specific operation for its details.

        :param args: The dictionary of string arguments
        """

        # Whether or not the operation was started
        self._started = False

        # Whether or not the operation was stopped
        self._stopped = False

    @abstractmethod
    def start(self):
        """
        Asynchronously start the operation.
        """

        # Set started flag
        # This will remain set even if the operation completes naturally
        self._started = True

        # Clear stopped flag
        self._stopped = False

    @abstractmethod
    def stop(self):
        """
        Stop the running operation.
        """

        # Clear started flag
        self._started = False

        # Set stopped flag
        self._stopped = True

    @property
    def started(self):
        """
        :return: Whether or not the operation was started
        """
        return self._started

    @property
    def stopped(self):
        """
        :return: Whether or not the operation was stopped
        """
        return self._stopped
