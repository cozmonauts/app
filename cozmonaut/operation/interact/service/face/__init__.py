#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import time
from concurrent.futures import Future
from concurrent.futures.thread import ThreadPoolExecutor
from threading import Thread, Lock
from typing import List, Tuple, Dict, Optional

import PIL.Image
import cv2
import dlib
import numpy
from pkg_resources import resource_filename

from cozmonaut.operation.interact.service import Service

# The face detector
_detector = dlib.get_frontal_face_detector()

# The face pose predictor
_predictor_serialized_file_name = resource_filename(__name__, "data/shape_predictor_68_face_landmarks.dat")
_predictor = dlib.shape_predictor(_predictor_serialized_file_name)

# The face recognition model
_model_file_serialized_file_name = resource_filename(__name__, "data/dlib_face_recognition_resnet_model_v1.dat")
_model = dlib.face_recognition_model_v1(_model_file_serialized_file_name)


class DetectedFace:
    """
    Info about a face that has been detected and tracked.
    """

    def __init__(self):
        self._index: int = 0
        self._coords: Tuple[int, int, int, int] = (0, 0, 0, 0)

    @property
    def index(self) -> int:
        """
        :return: The track index
        """
        return self._index

    @index.setter
    def index(self, value):
        """
        :param value: The track index
        """
        self._index = value

    @property
    def coords(self) -> Tuple[int, int, int, int]:
        """
        :return: The face coordinates (left, top, right, bottom)
        """
        return self._coords

    @coords.setter
    def coords(self, value: Tuple[int, int, int, int]):
        """
        :param value: The face coordinates (left, top, right, bottom)
        """
        self._coords = value


class RecognizedFace(DetectedFace):
    """
    Info about a face that has been recognized.

    All recognized faces are detected faces.
    """

    def __init__(self):
        super().__init__()
        self._fid: int = 0
        self._ident: Tuple[int, ...] = ()

    @property
    def fid(self) -> int:
        """
        :return: The face ID
        """
        return self._fid

    @fid.setter
    def fid(self, fid: int):
        """
        :param fid: The face ID
        """
        self._fid = fid

    @property
    def ident(self) -> Tuple[int, ...]:
        """
        :return: The face identity (128-dimensional vector embedding)
        """
        return self._ident

    @ident.setter
    def ident(self, value: Tuple[int, ...]):
        """
        :param value: The face identity (128-dimensional vector embedding)
        """
        self._ident = value


class ServiceFace(Service):
    """
    The face service recognizes faces.
    """

    def __init__(self):
        super().__init__()

        # The face identities
        self._identities: Dict[int, Tuple[float, ...]] = {}
        self._identities_lock = Lock()

        # The detection thread
        # We only need one of these, as each detection operation finds all faces in a frame
        # It would make no sense to parallelize detection across multiple frames simultaneously
        self._thread_detection = None

        # A kill switch for the detection loop
        self._detection_kill = False
        self._detection_kill_lock = Lock()

        # The recognition thread pool executor
        # A thread pool executor is a step above a simple thread pool, as it has a built-in work queue
        # This allows us to submit work orders for recognizing individual faces without worrying about scheduling
        self._thread_pool_recognizers = ThreadPoolExecutor(max_workers=3)  # FIXME: Allow this to be set by the user

        # The individual face trackers
        self._trackers = {}
        self._tracker_images = {}
        self._trackers_lock = Lock()
        self._next_tracker_id = 0

        # The latest frame pending detection
        self._pending_detection = None
        self._pending_detection_flag = False
        self._pending_detection_lock = Lock()

        # The list of "next track" futures
        self._next_track_futures = []
        self._next_track_futures_lock = Lock()

    def add_identity(self, fid: int, ident: Tuple[float, ...]):
        """
        Add a new face identity to the tracker.

        :param fid: The face ID
        :param ident: The face identity (128-dimensional vector)
        """

        with self._identities_lock:
            # Map the identity
            self._identities[fid] = ident

    def remove_identity(self, fid: int):
        """
        Remove a face identity from the tracker.

        :param fid: The face ID
        """

        with self._identities_lock:
            # Unmap the identity
            del self._identities[fid]

    def start(self):
        """
        Start the face service.
        """

        super().start()

        with self._detection_kill_lock:
            # Lock, clear, and unlock the detection loop kill switch
            self._detection_kill = False

        # Start the detection thread
        self._thread_detection = Thread(target=self._thread_detection_main)
        self._thread_detection.start()

    def stop(self):
        """
        Stop the face service.
        """

        super().stop()

        with self._detection_kill_lock:
            # Lock, set, and unlock the detection loop kill switch
            self._detection_kill = True

        # Wait for the detection thread to die
        self._thread_detection.join()

    def update(self, image: PIL.Image):
        """
        Update with the next image in the stream.

        :param image: The next frame
        """

        # Convert to numpy matrix
        image_np = numpy.array(image)

        # Prepare the image
        # TODO: Factor this out
        image_np = cv2.pyrUp(image_np)
        image_np = cv2.medianBlur(image_np, 3)

        with self._trackers_lock:
            # IDs of trackers that need pruning because faces have left us
            doomed_tracker_ids = []

            # For each registered tracker...
            for tracker_id in self._trackers.keys():
                # ...update it with the image!
                quality = self._trackers[tracker_id].update(image_np)
                self._tracker_images[tracker_id] = image_np

                # Doom the trackers with low quality tracks
                if quality < 7:  # TODO: Allow user to set this
                    doomed_tracker_ids.append(tracker_id)

            # Prune the doomed trackers
            for tracker_id in doomed_tracker_ids:
                self._trackers.pop(tracker_id, None)
                self._tracker_images.pop(tracker_id, None)

        with self._pending_detection_lock:
            # Update pending detection frame
            self._pending_detection = image
            self._pending_detection_flag = True

    def next_track(self):
        """
        Obtain a future on the next initiated face track. This does not notify
        of any preexisting tracks.

        :return: A future for the next DetectedFace object
        """

        # Create a future for the detection (they say we're not supposed to call this)
        # We will keep one copy and send another to the caller
        # Later on, after we track a new face, we'll complete the future
        future = Future()

        with self._next_track_futures_lock:
            # Lock, append the future to, and unlock the next track futures list
            self._next_track_futures.append(future)

        return future

    def recognize(self, index: int):
        """
        Obtain a future on the recognition of a face track.

        :param index: The track index
        """

        # Send off a request to recognize the face in this track
        return self._thread_pool_recognizers.submit(self._recognize_main, index)

    def _thread_detection_main(self):
        """
        Main function for detecting faces.

        This runs all the time, and it picks up the latest image.
        """

        # The latest frame
        frame: PIL.Image = None

        while True:
            with self._detection_kill_lock:
                # Test kill switch
                if self._detection_kill:
                    break

            with self._pending_detection_lock:
                # If a pending frame is available
                if self._pending_detection_flag:
                    # Save the frame
                    frame = self._pending_detection

                    # Clear pending frame slot
                    # We've kept it for ourselves
                    self._pending_detection = None
                    self._pending_detection_flag = False

            # If we've got a frame to work with
            if frame is not None:
                # Use the image as a numpy matrix
                frame_np = numpy.array(frame)

                # Prepare the image
                # TODO: Factor this out
                frame_np = cv2.pyrUp(frame_np)
                frame_np = cv2.medianBlur(frame_np, 3)

                # Detect all faces in the image
                faces: List[dlib.rectangle] = _detector(frame_np, 1)

                # Go over all detected faces
                for face in faces:
                    # The ID of the matching outstanding tracker
                    # If we cannot make a match, then we have seen a new face (or at least a misplaced one)
                    face_id_match = None

                    with self._trackers_lock:
                        # Loop through all outstanding trackers
                        for tracker_id in self._trackers.keys():
                            # Get the current tracker position
                            tracker_box = self._trackers[tracker_id].get_position()

                            # Tracker box coordinates
                            tb_l = int(tracker_box.left())  # left of tracker box
                            tb_r = int(tracker_box.left() + tracker_box.width())  # right of tracker box
                            tb_t = int(tracker_box.top())  # top of tracker box
                            tb_b = int(tracker_box.top() + tracker_box.height())  # bottom of track

                            # Find the center of the tracker box
                            tracker_center_x = tracker_box.left() + tracker_box.width() / 2
                            tracker_center_y = tracker_box.top() + tracker_box.height() / 2

                            # If the following two conditions hold, we have a match:
                            #  a) The face center is inside the tracker box
                            #  b) The tracker center is inside the face box

                            # Reject on (a) first
                            if face.center().x < tb_l or face.center().x > tb_r:
                                continue
                            if face.center().y < tb_t or face.center().y > tb_b:
                                continue

                            # Next, reject on (b)
                            if tracker_center_x < face.left() or tracker_center_x > face.right():
                                continue
                            if tracker_center_y < face.top() or tracker_center_y > face.bottom():
                                continue

                            # If neither (a) or (b) was rejected, we have match. Hooray!
                            face_id_match = tracker_id
                            break

                        # If no tracker match was found
                        if face_id_match is None:
                            # Create a dlib correlation tracker
                            # These are supposedly pretty sturdy...
                            new_tracker = dlib.correlation_tracker()

                            # Get next available tracker ID
                            # FIXME: For now, we don't reuse them (should we?)
                            tracker_id = self._next_tracker_id
                            self._next_tracker_id += 1

                            # Map the new tracker in
                            self._trackers[tracker_id] = new_tracker
                            self._tracker_images[tracker_id] = frame_np

                            # Add some padding to the face rectangle
                            # TODO: Make this slop configurable
                            track_left = face.left() - 10
                            track_top = face.top() - 20
                            track_right = face.right() + 10
                            track_bottom = face.bottom() + 20

                            # Start tracking the new face in full color
                            new_tracker.start_track(frame_np,
                                                    dlib.rectangle(track_left, track_top, track_right, track_bottom))

                            # Info about the detected face
                            detected = DetectedFace()
                            detected.index = tracker_id
                            detected.coords = (track_left, track_top, track_right, track_bottom)

                            with self._next_track_futures_lock:
                                # Complete all the next track futures
                                for future in self._next_track_futures:
                                    future.set_result(detected)
                                self._next_track_futures.clear()

            # Sleep for a bit
            time.sleep(3)  # TODO: This should dynamically reduce during face diversion and scale back up otherwise

    def _recognize_main(self, index: int) -> Optional[RecognizedFace]:
        """
        Main function for recognizing a face.

        This runs to completion on an as-needed basis given by a thread pool.
        """

        print(f'A recognition worker has kicked off for tracker {index}')

        with self._trackers_lock:
            if self._trackers.get(index) is None:
                print(f'Tracker {index} no longer exists')
                return None

            # Query the latest face bounding box from the tracker
            position: dlib.rectangle = self._trackers[index].get_position()

            # Get the image that corresponds to this tracker
            image = self._tracker_images[index]

        print(f'Details gathered for tracker {index}; stand by for pose prediction...')

        # Predict 68 unique points on the face
        prediction = _predictor(image, dlib.rectangle(
            int(position.left()),
            int(position.top()),
            int(position.right()),
            int(position.bottom())
        ))

        print(f'Face pose prediction succeeded on tracker {index}; computing vector embedding...')

        # Compute the 128-dimensional vector embedding of the face
        ident = numpy.array(_model.compute_face_descriptor(image, prediction, 1))

        print(f'Computed face embedding for tracker {index}; cross-referencing known faces...')

        with self._identities_lock:
            # Details about the best match
            best_match_fid = -1  # Impossible by our definition of face IDs (valid only if >= 0)
            best_match_distance = 0.6  # TODO: Make this user configurable (the maximum tolerance)

            for other_fid in self._identities.keys():
                # The other full-blown identity (128-dim vector embedding)
                other_ident = numpy.array(self._identities[other_fid])

                # In numpy, the norm of two vectors with ord=None and axis=1 is simply Euclidean distance
                distance = numpy.linalg.norm([ident - other_ident], ord=None, axis=1)

                # If this is a new best distance
                if distance < best_match_distance:
                    # Update best match details
                    best_match_fid = other_fid
                    best_match_distance = distance

        print(f'Cross-referencing for tracker {index} completed')

        if best_match_fid == -1:
            print(f'The face for tracker {index} is not known')
        else:
            print(f'The face for tracker {index} known as {best_match_fid} in the database')

        # Return info about the recognized face
        rec = RecognizedFace()
        rec.index = index
        rec.coords = position
        rec.fid = best_match_fid
        rec.ident = tuple(ident)
        return rec
