#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import asyncio
import time
from concurrent.futures.process import ProcessPoolExecutor
from typing import Tuple

from cozmonaut.operation.interact.service import Service

_num_processes = 2


class TrackedFace:
    """
    A face tracked in a camera stream.
    """

    def __init__(self):
        self._index = 0
        self._coords = (0, 0, 0, 0)

    @property
    def index(self):
        """
        :return: The face index
        """
        return self._index

    @index.setter
    def index(self, value: int):
        """
        :param value: The face index
        """
        self._index = value

    @property
    def coords(self):
        """
        :return: The LTRB coordinates
        """
        return self._coords

    @coords.setter
    def coords(self, value: Tuple[float, float, float, float]):
        """
        :param value: The LTRB coordinates
        """
        self._coords = value


class RecognizedFace(TrackedFace):
    """
    A face recognized to an identity.
    """

    def __init__(self):
        super().__init__()

        self._ident = 0

    @property
    def ident(self):
        """
        :return: The identity
        """
        return self._ident

    @ident.setter
    def ident(self, value: int):
        """
        :param value: The identity
        """
        self._ident = value


class ServiceFace(Service):
    """
    The face service recognizes faces.
    """

    def __init__(self):
        super().__init__()

        # The process pool
        self._exec: ProcessPoolExecutor = None

    def start(self):
        """
        Start the face service.
        """

        super().start()

        # Spawn the process pool
        self._exec = ProcessPoolExecutor(max_workers=_num_processes)

    def stop(self):
        """
        Stop the face service.
        """

        super().stop()

        # Close the process pool
        self._exec.shutdown(wait=True)

    async def next_track(self) -> TrackedFace:
        """
        Get the next tracked face.

        :return: The tracked face
        """

        # Get the event loop
        loop = asyncio.get_event_loop()

        # Run detection in process pool
        return await loop.run_in_executor(self._exec, _detect_main)

    async def update_track(self, index: int) -> TrackedFace:
        """
        Get the latest track of the indexed face.

        :param index: The track index
        :return: The tracked face
        """

        # Get the event loop
        loop = asyncio.get_event_loop()

        # Run re-detection in process pool
        return await loop.run_in_executor(self._exec, _detect_main)

    async def recognize_track(self, index: int) -> RecognizedFace:
        """
        Recognize the latest track.

        :param index: The track index
        :return: The recognized face
        """

        # Get the event loop
        loop = asyncio.get_event_loop()

        # Run recognition in process pool
        return await loop.run_in_executor(self._exec, _recognize_main)


def _detect_main():
    time.sleep(3)
    print('THIS IS THE DETECTION')
    return 1234


def _recognize_main():
    time.sleep(2)
    print('THIS IS THE RECOGNITION')
    return 1234
