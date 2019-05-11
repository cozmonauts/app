#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import multiprocessing

from cozmonaut.operation.interact.service import Service

_num_processes = 2


class ServiceSpeech(Service):
    """
    The speech service recognizes speech.
    """

    def __init__(self):
        super().__init__()

        # The process pool
        self._pool: multiprocessing.Pool = None

    def start(self):
        """
        Start the speech service.
        """

        super().start()

        # Spawn the process pool
        self._pool = multiprocessing.Pool(processes=_num_processes)

    def stop(self):
        """
        Stop the speech service.
        """

        super().stop()

        # Close the process pool
        self._pool.close()
