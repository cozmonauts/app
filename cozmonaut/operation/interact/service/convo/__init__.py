#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#
import os
from typing import List

from pkg_resources import resource_filename

from cozmonaut.operation.interact.service import Service

# The conversation data directory
_data_directory = resource_filename(__name__, 'data')


class ServiceConvo(Service):
    """
    The Convo service manages conversations.
    """

    def __init__(self):
        super().__init__()

    def start(self):
        """
        Start the Convo service.
        """

        super().start()

    def stop(self):
        """
        Stop the Convo service.
        """

        super().stop()

    @staticmethod
    def list() -> List[str]:
        """
        Retrieve a summary of all available conversations.

        :return: A list of names of known conversations
        """

        # List all files in the conversation directory
        return [file[:-5] for file in os.listdir(_data_directory)
                if os.path.isfile(os.path.join(_data_directory, file)) and file.endswith('.json')]


class Conversation:
    """
    A loaded conversation.
    """
    pass
