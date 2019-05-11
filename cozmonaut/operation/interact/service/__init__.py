#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

from abc import abstractmethod, ABC


class Service(ABC):
    """
    An abstract service.
    """

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def start(self):
        """
        Start the service.
        """
        pass

    @abstractmethod
    def stop(self):
        """
        Stop the service.
        """
        pass
