#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import argparse
import asyncio
import functools
import json
import math
import queue
import random
import time
from enum import Enum
from threading import Lock, Thread
from typing import Tuple

import cmd2
import cozmo
from PIL import Image, ImageDraw

from cozmonaut.operation import Operation
from cozmonaut.operation.interact import database
from cozmonaut.operation.interact.service.convo import ServiceConvo
from cozmonaut.operation.interact.service.face import DetectedFace, RecognizedFace, ServiceFace


class InteractMode(Enum):
    """
    A mode of interaction.

    We can run with both Cozmos accounted for, or we can run with just one or
    the other. This is useful for testing and development when a single
    developer might not have both Cozmos.
    """

    both = 1
    just_a = 2
    just_b = 3


class _RobotState(Enum):
    """
    The state of a Cozmo robot in our little world.
    """

    # Safe and sound on its charger
    home = 1

    # At its waypoint ready to work
    waypoint = 3

    # Greeting visitors of the TLC
    greet = 5

    # Having a conversation with the other Cozmo
    # The other Cozmo is assumed to be in its "home" state (not checked, though)
    convo = 6

    # Playing pong on its face
    pong = 7

    # Randomly playing on the table surface
    freeplay = 8


class _RobotAction(Enum):
    """
    An action that a Cozmo robot can do.

    Actions bring about changes in state.
    """

    # Drive from the charger to the waypoint
    drive_from_charger_to_waypoint = 1

    # Drive from the waypoint to the charger
    drive_from_waypoint_to_charger = 2


class OperationInteract(Operation):
    """
    The interact operation.
    """

    def __init__(self, args: dict):
        """
        Initialize the interact operation.

        Operation arguments:
          - sera (str) Serial number for robot A
          - serb (str) Serial number for robot B
          - mode (str) One of 'just_a', 'just_b', or 'both'

        :param args: The arguments as described
        """

        super().__init__(args)

        # The terminal interface
        self._term = None

        # Unpack wanted serial numbers
        self._wanted_serial_a = args.get('sera', '0241c714')  # Default to an actual serial number
        self._wanted_serial_b = args.get('serb', '45a18821')  # Default to an actual serial number

        # Unpack interaction mode
        self._mode = InteractMode[args.get('mode', 'both')]  # Default to both

        # The interact thread
        # We'll run the event loop on this thread asynchronously
        self._thread_interact: Thread = None

        # A kill switch for the operation (thread-safe)
        self._should_stop = False
        self._should_stop_lock = Lock()

        # An indicator telling if the operation stopped (thread-safe)
        # This goes True even if the operation naturally dies
        self._stopped = False
        self._stopped_lock = Lock()

        # An indicator telling if the operation is in the middle of stopping (not thread-safe)
        self._stopping = False

        # Indicators telling if the current activity should cancel for each Cozmo robot
        self._cancel_a = False
        self._cancel_b = False

        # An indicator telling if the activity is completed
        self._complete = False

        # An indicator telling if we should swap
        self._swap = False

        # The conversation service
        self._service_convo = ServiceConvo()

        # The face services for robots
        self._service_face_a = ServiceFace()
        self._service_face_b = ServiceFace()

        # The robot instances
        self._robot_a: cozmo.robot.Robot = None
        self._robot_b: cozmo.robot.Robot = None

        # States for the robots
        self._robot_state_a: _RobotState = None
        self._robot_state_b: _RobotState = None

        # Queues for robot actions
        self._robot_queue_a = queue.Queue()
        self._robot_queue_b = queue.Queue()

        # Waypoints for the robots
        self._robot_waypoint_a: cozmo.util.Pose = None
        self._robot_waypoint_b: cozmo.util.Pose = None

    def start(self):
        """
        Start the interact operation.
        """

        super().start()

        # Spawn the interact thread
        self._thread_interact = Thread(target=self._thread_interact_main, name='Interact')
        self._thread_interact.start()

    def stop(self):
        """
        Stop the interact operation.
        """

        super().stop()

        # Set the interact thread kill switch
        with self._should_stop_lock:
            self._should_stop = True

        # Wait for the interact thread to die
        if self._thread_interact is not None:
            self._thread_interact.join()
            self._thread_interact = None

    def is_running(self):
        """
        Check if the interact operation is running.

        :return: True if such is the case, otherwise False
        """

        # If we haven't stopped, we're running
        with self._stopped_lock:
            return not self._stopped

    @property
    def term(self):
        """
        :return: The terminal interface
        """
        return self._term

    @term.setter
    def term(self, value):
        """
        :param value: The terminal interface
        """
        self._term = value

    def _thread_interact_main(self):
        """
        The main function of the interact thread.
        """

        try:
            # Create an event loop for interaction
            loop = asyncio.new_event_loop()

            # Print some stuff about the mode
            if self._mode == InteractMode.both:
                self._tprint('Configured for both Cozmos A and B')
                self._tprint(f'Want Cozmo A to have serial number {self._wanted_serial_a}')
                self._tprint(f'Want Cozmo B to have serial number {self._wanted_serial_b}')
            elif self._mode == InteractMode.just_a:
                self._tprint('Configured for just Cozmo A')
                self._tprint(f'Want Cozmo A to have serial number {self._wanted_serial_a}')
            elif self._mode == InteractMode.just_b:
                self._tprint('Configured for just Cozmo B')
                self._tprint(f'Want Cozmo B to have serial number {self._wanted_serial_b}')

            self._tprint('Establishing as many connections as possible')

            # A list of connections we've made
            # We will connect to all available Cozmos one-by-one
            # This is because we can't interleave connection and wait_for_robot() calls
            # If we call wait_for_robot(), we can no longer make any more connections (Cozmo SDK bug?)
            # (well, we can, but it leads to a weird problem where two robot objects control one Cozmo robot IRL)
            connections = []

            # Make as many connections as we can
            while True:
                # Make the next connection
                try:
                    conn = cozmo.connect_on_loop(loop)
                except cozmo.exceptions.CozmoSDKException:
                    # We've reached the end of available connections
                    self._tprint('No more Cozmos available (this is normal)')
                    break

                # The connection index is just the length of the connections list
                i = len(connections)

                self._tprint(f'Established connection #{i}')

                # Keep the connection
                connections.insert(i, conn)

            # Go over all the connections we've made
            for i in range(0, len(connections)):
                conn = connections[i]

                # Whether or not to keep the connection
                # We only keep the ones we need, but we don't know which those are until we've connected to everyone
                keep = False

                # Wait for the robot on this connection
                robot = loop.run_until_complete(conn.wait_for_robot())

                self._tprint(f'Robot on connection #{i} has serial number {robot.serial}')

                # If we're assigning both Cozmos
                if self._mode == InteractMode.both:
                    # If this serial matches that desired for robot A
                    if robot.serial == self._wanted_serial_a:
                        # Keep the connection
                        keep = True

                        # Assign robot A
                        self._robot_a = robot

                        self._tprint(
                            f'On connection #{i}, robot A was assigned serial number {robot.serial} (need A and B)')

                    # If this serial matches that desired for robot B
                    if robot.serial == self._wanted_serial_b:
                        # Keep the connection
                        keep = True

                        # Assign robot B
                        self._robot_b = robot

                        self._tprint(
                            f'On connection #{i}, robot B was assigned serial number {robot.serial} (need A and B)')

                # If we're assigning just Cozmo A
                if self._mode == InteractMode.just_a:
                    # If this serial matches that desired for robot A
                    if robot.serial == self._wanted_serial_a:
                        # Keep the connection
                        keep = True

                        # Assign robot A
                        self._robot_a = robot

                        self._tprint(
                            f'On connection #{i}, robot A was assigned serial number {robot.serial} (need just A)')

                # If we're assigning just Cozmo B
                if self._mode == InteractMode.just_b:
                    # If this serial matches that desired for robot B
                    if robot.serial == self._wanted_serial_b:
                        # Keep the connection
                        keep = True

                        # Assign robot B
                        self._robot_b = robot

                        self._tprint(
                            f'On connection #{i}, robot B was assigned serial number {robot.serial} (need just B)')

                # If we're not keeping this connection
                if not keep:
                    self._tprint(f'Connection #{i} is not needed, so disconnecting it')

                    # Abort the connection
                    conn.abort(0)

            # Stop if we're missing a Cozmo
            if self._mode == InteractMode.both:
                # Whether or not one is missing
                missing = False

                # Look at A
                if self._robot_a is None:
                    missing = True
                    self._tprint('Configured for both, but Cozmo A is missing')

                # Look at B
                if self._robot_b is None:
                    missing = True
                    self._tprint('Configured for both, but Cozmo B is missing')

                # If one is missing
                if missing:
                    self._tprint('At least one Cozmo is missing, so refusing to continue')
                    return
            elif self._mode == InteractMode.just_a:
                # Look at A
                if self._robot_a is None:
                    self._tprint('Cozmo A is missing, so refusing to continue')
                    return
            elif self._mode == InteractMode.just_b:
                # Look at B
                if self._robot_b is None:
                    self._tprint('Cozmo B is missing, so refusing to continue')

            self._tprint('Beginning interactive procedure')

            self._tprint('+-----------------------------------------------------------------+')
            self._tprint('| IMPORTANT: We are assuming both Cozmos start on their chargers! |')
            self._tprint('+-----------------------------------------------------------------+')

            # Assume both Cozmos start on their chargers (as advertised ^^^)
            self._robot_state_a = _RobotState.home
            self._robot_state_b = _RobotState.home

            asyncio.gather(
                # The watchdog coroutine handles the shutdown protocol
                self._watchdog(),

                # Driver coroutines for Cozmos A and B
                # These routines take care of running individual bite-size tasks
                self._driver(1, self._robot_a),
                self._driver(2, self._robot_b),

                # The choreographer coroutine automates the robots from a high level
                # self._choreographer(),  TODO

                # Explicitly provide our event loop
                # Without this, there will be an error along the lines of "no current event loop"
                loop=loop,
            )

            self._tprint('Setting up face services')

            # Create face services
            self._service_face_a = ServiceFace()
            self._service_face_b = ServiceFace()

            self._tprint('Loading known faces from database')

            # Query known faces from database
            known_faces = database.loadStudents()

            # If there are known faces
            if known_faces is not None:
                # Loop through them
                # We received their IDs and string-encoded identities from the database
                for (fid, ident_enc) in known_faces:
                    # Decode string-encoded identity
                    # The result is a 128-tuple of 64-bit floats
                    ident = self._face_ident_decode(ident_enc)

                    # Register identity with both face services
                    # That way both Cozmos will be able to recognize the face
                    self._service_face_a.add_identity(fid, ident)
                    self._service_face_b.add_identity(fid, ident)

            # Stop the face services
            self._service_face_a.start()
            self._service_face_b.start()

            # Run the event loop until it stops (it's not actually forever)
            loop.run_forever()

            # Stop the face services
            self._service_face_a.stop()
            self._service_face_b.stop()

            self._tprint('Goodbye!')
        finally:
            # Set the stopped flag
            with self._stopped_lock:
                self._stopped = True

    async def _watchdog(self):
        """
        The watchdog handles shutdown requests.
        """

        self._tprint('Watchdog has started')

        while not self._stopping:
            # Check if we should stop
            # There shouldn't be much contention on this lock
            with self._should_stop_lock:
                should_stop = self._should_stop

            # If we should stop, start stopping
            if should_stop:
                # Set the stopping indicator
                # All well-behaved loops (those that check this indicator) should start shutting down
                self._stopping = True

                # Get the event loop
                loop = asyncio.get_event_loop()

                # Politely ask the loop to stop soon
                loop.call_soon(loop.stop)

                self._tprint('The event loop will stop soon')
            else:
                # Yield control
                await asyncio.sleep(0)

        self._tprint('Watchdog has stopped')

    async def _driver(self, index: int, robot: cozmo.robot.Robot):
        """
        The driver for a single robot.

        :param index: The robot index (1 for robot A or 2 for robot B)
        :param robot: The robot instance
        """

        # Convert robot index to robot letter
        letter = 'A' if index == 1 else 'B'

        self._tprint(f'Driver for robot {letter} has started')

        # Stop if this driver is not needed
        if robot is None:
            self._tprint(f'Robot {letter} is not available, so driver {letter} is stopping')
            return

        # Enable color imaging on the robot
        robot.camera.color_image_enabled = True
        robot.camera.image_stream_enabled = True

        # Listen for camera frames from this Cozmo
        # We create a partially-bound function that sneaks in our index and robot parameters
        robot.camera.add_event_handler(cozmo.robot.camera.EvtNewRawCameraImage,
                                       functools.partial(self._driver_on_evt_new_raw_camera_image, index, robot))

        # Get the robot-specific data
        state_queue = None
        service_face = None
        if index == 1:
            state_queue = self._robot_queue_a
            service_face = self._service_face_a
        elif index == 2:
            state_queue = self._robot_queue_b
            service_face = self._service_face_b

        # Start the face service
        service_face.start()

        while not self._stopping:
            # Yield control
            await asyncio.sleep(0)

            # Try to get the next state
            state_next: _RobotState = None
            try:
                state_next = state_queue.get_nowait()
            except queue.Empty:
                pass

            # If a state was dequeued
            if state_next is not None:
                # Get the current state
                state_current = None
                if index == 1:
                    state_current = self._robot_state_a
                elif index == 2:
                    state_current = self._robot_state_b

                # The state we actually ended up going to
                # By default, this is the current state
                # On a successful transition, we'll update this
                state_final = state_current

                # The task to wait on
                task = None

                if state_current == _RobotState.home:
                    if state_next == _RobotState.waypoint:
                        # GOTO home -> waypoint
                        state_final = state_next

                        # Drive from the charger to the waypoint
                        task = asyncio.ensure_future(self._do_drive_from_charger_to_waypoint(index, robot))
                elif state_current == _RobotState.waypoint:
                    if state_next == _RobotState.home:
                        # GOTO waypoint -> home
                        state_final = state_next

                        # Drive from the waypoint to the charger
                        task = asyncio.ensure_future(self._do_drive_from_waypoint_to_charger(index, robot))
                    elif state_next == _RobotState.convo:
                        # GOTO waypoint -> convo
                        state_final = state_next

                        # Carry out the conversation
                        task = asyncio.ensure_future(self._do_convo(index, robot))
                    elif state_next == _RobotState.greet:
                        # GOTO waypoint -> greet
                        state_final = state_next

                        # Carry out greeting
                        task = asyncio.ensure_future(self._do_meet_and_greet(index, robot))
                    elif state_next == _RobotState.freeplay:
                        # GOTO waypoint -> freeplay
                        state_final = state_next

                        # Carry out freeplay
                        task = asyncio.ensure_future(self._do_freeplay(index, robot))
                    elif state_next == _RobotState.pong:
                        # GOTO waypoint -> pong
                        state_final = state_next

                        # Carry out pong
                        task = asyncio.ensure_future(self._do_pong(index, robot))
                elif state_current == _RobotState.convo:
                    if state_next == _RobotState.waypoint:
                        # GOTO convo -> waypoint
                        state_final = state_next

                        # Return to the waypoint
                        task = asyncio.ensure_future(self._do_return_to_waypoint(index, robot))
                elif state_current == _RobotState.greet:
                    if state_next == _RobotState.waypoint:
                        # GOTO greet -> waypoint
                        state_final = state_next

                        # Return to the waypoint
                        task = asyncio.ensure_future(self._do_return_to_waypoint(index, robot))
                elif state_current == _RobotState.freeplay:
                    if state_next == _RobotState.waypoint:
                        # GOTO freeplay -> waypoint
                        state_final = state_next

                        # Return to the waypoint
                        task = asyncio.ensure_future(self._do_return_to_waypoint(index, robot))
                elif state_current == _RobotState.pong:
                    if state_next == _RobotState.waypoint:
                        # GOTO pong -> waypoint
                        state_final = state_next

                        # Return to the waypoint
                        task = asyncio.ensure_future(self._do_return_to_waypoint(index, robot))

                # If the state did not change
                if state_final == state_current:
                    self._tprint(f'Failed to transition from state "{state_current.name}" to state "{state_next.name}"')

                # Update the current state
                if index == 1:
                    self._robot_state_a = state_final
                elif index == 2:
                    self._robot_state_b = state_final

                if task is not None:
                    # Wait for the task
                    # This prevents any issues with multiple simultaneous movements
                    await task

        # Stop the face service
        service_face.stop()

        self._tprint(f'Driver for robot {letter} has stopped')

    def _driver_on_evt_new_raw_camera_image(self, index: int, robot: cozmo.robot.Robot,
                                            evt: cozmo.robot.camera.EvtNewRawCameraImage, **kwargs):
        """
        Called by the Cozmo SDK when a camera frame comes in.

        :param index: The robot index
        :param robot: The robot instance
        :param evt: The handled event
        :param kwargs: Excess keyword arguments
        """

        # The camera frame image
        image = evt.image

        # The face service for this Cozmo robot
        face: ServiceFace = None

        # Pick the corresponding face service
        if index == 1:
            face = self._service_face_a
        elif index == 2:
            face = self._service_face_b

        # Update the Cozmo-corresponding face service with the new camera frame
        face.update(image)

    async def _do_drive_from_charger_to_waypoint(self, index: int, robot: cozmo.robot.Robot):
        """
        Action for driving from charger to waypoint.

        :param index: The robot index
        :param robot: The robot instance
        """

        # Convert robot index to robot letter
        letter = 'A' if index == 1 else 'B'

        self._tprint(f'Robot {letter} is departing from charger and heading to waypoint')

        # Drive off the charger contacts
        await robot.drive_off_charger_contacts().wait_for_completed()

        # Drive forward to the waypoint
        await robot.drive_straight(
            distance=cozmo.util.distance_mm(250),
            speed=cozmo.util.speed_mmps(50),
        ).wait_for_completed()

        # Save robot waypoint
        if index == 1:
            self._robot_waypoint_a = robot.pose
        elif index == 2:
            self._robot_waypoint_b = robot.pose

    async def _do_drive_from_waypoint_to_charger(self, index: int, robot: cozmo.robot.Robot):
        """
        Action for driving from waypoint to charger.

        :param index: The robot index
        :param robot: The robot instance
        """

        # Convert robot index to robot letter
        letter = 'A' if index == 1 else 'B'

        self._tprint(f'Robot {letter} is departing from waypoint and heading to charger')

        # Turn toward the charger
        await robot.turn_in_place(cozmo.util.degrees(180)).wait_for_completed()

        #
        # BEGIN INTEGRATED CHARGER RETURN CODE
        # This uses Herman's routines
        #

        # Look a little bit down but not straight ahead
        # We need the camera to be able to see the charger
        await robot.set_head_angle(cozmo.util.degrees(0)).wait_for_completed()

        # Cozmo's accelerometer is located in his head
        # We need to take a baseline reading before we use accelerometer during charger parking
        pitch_threshold = math.fabs(robot.pose_pitch.degrees) + 1

        # Drive to the charger
        await self._charger_return_go_to_charger_coarse(robot)

        # If the charger location is known (it should be)
        if robot.world.charger is not None:
            # Invalidate the charger pose
            if robot.world.charger.pose.is_comparable(robot.pose):
                robot.world.charger.pose.invalidate()

        # Look for the charger again
        await self._charger_return_find_charger(robot)

        # Add finishing touches to our staging
        await self._charger_return_go_to_charger_fine(robot)

        # Face away from the charger (very precisely)
        await robot.turn_in_place(cozmo.util.degrees(180),
                                  angle_tolerance=cozmo.util.degrees(2)).wait_for_completed()

        # Point head forward-ish and lift lift out of way of charger
        await robot.set_lift_height(height=0.5, max_speed=10, in_parallel=True).wait_for_completed()
        await robot.set_head_angle(cozmo.util.degrees(0), in_parallel=True).wait_for_completed()

        self._tprint('Begin strike phase')
        self._tprint('The robot will try to strike the base of the charger')

        # Start driving backward pretty quickly
        robot.drive_wheel_motors(-60, -60)

        # Timeout and elapsed time for strike phase
        timeout = 3
        elapsed = 0
        delta = 0.05

        # Wait until we hit the charger
        # Cozmo will start to pitch forward, and that breaks the loop
        while True:
            # Wait one phase delta
            await asyncio.sleep(delta)
            elapsed += delta

            if elapsed >= timeout:
                self._tprint('Timed out while waiting for robot to strike the charger')
                break
            elif math.fabs(robot.pose_pitch.degrees) >= pitch_threshold:
                self._tprint('The robot seems to have struck the charger (this is normal)')
                break

        # Striking done, stop motors
        robot.stop_all_motors()

        # Wait a little
        await asyncio.sleep(0.5)

        self._tprint('Begin flattening phase')
        self._tprint('The robot will try to flatten out on the charger')

        # Start driving backward a little slower
        # We want to avoid driving up onto the back wall of the charger
        robot.drive_wheel_motors(-35, -35)

        # Timeout and elapsed time for flattening phase
        timeout = 5
        elapsed = 0
        delta = 0.05

        # Wait until we flatten back out
        # The pitch returns to flat which indicates fully onboard
        while True:
            # Wait one phase time
            await asyncio.sleep(delta)
            elapsed += delta

            if elapsed >= timeout:
                self._tprint('Timed out while waiting for robot to flatten out on the charger')
                break
            elif math.fabs(robot.pose_pitch.degrees) > 20:
                self._tprint('Robot pitch has reached an unexpected value (drove on wall?)')
                break
            elif math.fabs(robot.pose_pitch.degrees) < pitch_threshold:
                self._tprint('The robot seems to have flattened out on the charger (this is normal)')
                break

        # Flattening done, stop motors
        robot.stop_all_motors()

        # Wait a little
        await asyncio.sleep(0.5)

        # Lower lift and nestle in
        await robot.set_lift_height(height=0, max_speed=10, in_parallel=True).wait_for_completed()
        await robot.backup_onto_charger(max_drive_time=3)

        # Sometimes robot.backup_onto_charger times out as gravity needs to let Cozmo fall onto contacts
        await asyncio.sleep(1)

        # If we made it onto the charger contacts
        if robot.is_on_charger:
            self._tprint('The robot is on the charger... Let\'s celebrate!')

            # Play a celebration animation
            await robot.drive_off_charger_contacts().wait_for_completed()
            await robot.play_anim_trigger(cozmo.anim.Triggers.CodeLabCelebrate, ignore_body_track=True,
                                          ignore_lift_track=True, in_parallel=True).wait_for_completed()
            await robot.backup_onto_charger(max_drive_time=3)
        else:
            self._tprint('The charger was not detected! Assuming we\'re on it?')  # TODO: What do? Call for help...

        # Set completed flag
        self._complete = True

        #
        # END INTEGRATED CHARGER RETURN CODE
        # (some component functions follow)
        #

    async def _charger_return_find_charger(self, robot: cozmo.robot.Robot) -> cozmo.objects.Charger:
        """
        Locate the nearest charger from the perspective of a robot.

        Part of the driver routine for a single Cozmo robot.

        :param robot: The robot instance
        """

        self._tprint('Starting to look for the charger')

        rnd = 1

        # Be persistent, Cozmo!
        while True:
            self._tprint(f'Look for charger (round {rnd})')

            rnd += 1

            # Remember the robot pose before looking around
            pose_before = robot.pose

            # Start to look around at the surroundings
            # The Cozmo app will pick up on any visible charger
            behave = robot.start_behavior(cozmo.behavior.BehaviorTypes.LookAroundInPlace)

            # Yield control
            await asyncio.sleep(0)

            # While we're looking around, keep an eye out for chargers
            try:
                seen_charger = await robot.world.wait_for_observed_charger(timeout=3, include_existing=True)
            except cozmo.exceptions.CozmoSDKException:
                seen_charger = None

            # Stop looking around
            # We may or may not have seen a charger
            behave.stop()

            # Go back to the pose before looking around
            await robot.go_to_pose(pose_before).wait_for_completed()

            # If we saw a charger, use that one
            if seen_charger is not None:
                self._tprint('The charger was found!')
                return seen_charger
            else:
                self._tprint('The charger was not found! :(')

                # Play frustrated animation
                await robot.play_anim_trigger(cozmo.anim.Triggers.FrustratedByFailureMajor).wait_for_completed()

                # Ask for help
                # TODO: Is is okay that this happens here? I know we talked about asking for help...
                await robot.say_text('A little help?').wait_for_completed()

    async def _charger_return_go_to_charger_coarse(self, robot: cozmo.robot.Robot):
        """
        Coarsely drive a robot up to the first seen charger.

        This ballparks it. There must be further correction.

        :param robot: The robot instance
        """

        # The charger reference
        charger = None

        # If the charger location is known
        if robot.world.charger is not None:
            # If the charger pose is in the same coordinate frame as the robot
            # This might not be the case if the robot gets picked up by a person or falls ("delocalizing")
            if robot.world.charger.pose.is_comparable(robot.pose):
                self._tprint('The charger pose is already known')

                # Just take the charger reference
                charger = robot.world.charger

        # If we don't yet have the charger reference
        if not charger:
            # Find the charger
            charger = await self._charger_return_find_charger(robot)

        # Drive to the charger the first time
        # This is a ballpark maneuver; we'll fine-tune it next
        await robot.go_to_object(
            charger,
            distance_from_object=cozmo.util.distance_mm(80),
            num_retries=5
        ).wait_for_completed()

    async def _charger_return_go_to_charger_fine(self, robot: cozmo.robot.Robot):
        """
        The fine part of charger goto functionality.

        Make sure you have called the coarse variant first.

        :param robot: The robot instance
        """

        # Grab the charger reference
        charger = robot.world.charger

        # Assumed distance from charger
        charger_distance = 40

        # Speed at which to drive
        speed = 40

        # Positions of robot and charger
        robot_pos = robot.pose.position.x_y_z
        charger_pos = charger.pose.position.x_y_z

        # Rotations of robot and charger in XY plane (i.e. on up-and-down Z-axis)
        robot_rot_xy = robot.pose_angle.radians
        charger_rot_xy = charger.pose.rotation.angle_z.radians

        # Compute virtual target position
        # This coordinate space is in Cozmo's head
        virtual_pos = (
            charger_pos[0] - charger_distance * math.cos(charger_rot_xy),
            charger_pos[1] - charger_distance * math.sin(charger_rot_xy),
            charger_pos[2],
        )

        # Direction and distance to target position (in front of charger)
        distance = math.sqrt(
            (virtual_pos[0] - robot_pos[0]) ** 2 +
            (virtual_pos[1] - robot_pos[1]) ** 2 +
            (virtual_pos[2] - robot_pos[2]) ** 2
        )

        # Angle of vector going from robot's origin to target's position
        vec = (virtual_pos[0] - robot_pos[0], virtual_pos[1] - robot_pos[1], virtual_pos[2] - robot_pos[2])
        theta_t = math.atan2(vec[1], vec[0])

        # Face the target position
        angle = self._charger_return_wrap_radians(theta_t - robot_rot_xy)
        await robot.turn_in_place(cozmo.util.radians(angle)).wait_for_completed()

        # Drive toward the target position
        await robot.drive_straight(cozmo.util.distance_mm(distance),
                                   cozmo.util.speed_mmps(speed)).wait_for_completed()

        # Face the charger
        angle = self._charger_return_wrap_radians(charger_rot_xy - theta_t)
        await robot.turn_in_place(cozmo.util.radians(angle)).wait_for_completed()

        try:
            charger = await robot.world.wait_for_observed_charger(timeout=2, include_existing=True)
        except cozmo.exceptions.CozmoSDKException:
            self._tprint('Charger not seen, so can\'t verify positioning')

        # Positions of robot and charger
        robot_pos = robot.pose.position.x_y_z
        charger_pos = charger.pose.position.x_y_z

        # Rotations of robot and charger in XY plane (i.e. on up-and-down Z-axis)
        robot_rot_xy = robot.pose_angle.radians
        charger_rot_xy = charger.pose.rotation.angle_z.radians

        # Compute virtual target position
        # This coordinate space is in Cozmo's head
        virtual_pos = (
            charger_pos[0] - charger_distance * math.cos(charger_rot_xy),
            charger_pos[1] - charger_distance * math.sin(charger_rot_xy),
            charger_pos[2],
        )

        # Direction and distance to target position (in front of charger)
        distance = math.sqrt(
            (virtual_pos[0] - robot_pos[0]) ** 2 +
            (virtual_pos[1] - robot_pos[1]) ** 2 +
            (virtual_pos[2] - robot_pos[2]) ** 2
        )

        distance_tol = 5
        angle_tol = 5 * math.pi / 180

        if distance < distance_tol and math.fabs(robot_rot_xy - charger_rot_xy) < angle_tol:
            self._tprint('Successfully aligned')
        else:
            self._tprint('Did not align successfully')  # TODO: Should we retry here?

    @staticmethod
    def _charger_return_wrap_radians(angle: float):
        while angle >= 2 * math.pi:
            angle -= 2 * math.pi
        while angle <= -2 * math.pi:
            angle += 2 * math.pi

        if angle > math.pi:
            angle -= 2 * math.pi
        elif angle < -math.pi:
            angle += 2 * math.pi

        return angle

    async def _do_convo(self, index: int, robot: cozmo.robot.Robot):
        """
        Action for carrying out a conversation.

        Data:
          - name (str) The conversation name

        :param index: The robot index
        :param robot: The robot instance
        """

        # Convert robot index to robot letter
        letter = 'A' if index == 1 else 'B'

        self._tprint(f'Robot {letter} is engaging in conversation')

        # Turn toward other Cozmo
        # TODO: Use the index to determine angle to look at other Cozmo
        await robot.turn_in_place(cozmo.util.degrees(180)).wait_for_completed()

        # Get the requested conversation
        name = None
        if index == 1:
            name = self._robot_queue_a.get()
        elif index == 2:
            name = self._robot_queue_b.get()

        self._tprint(f'Requested conversation {name}')

        # Load the conversation
        convo = self._service_convo.load(name)

        if convo is None:
            # Uh oh! That conversation does not exist...
            self._tprint(f'There is no conversation named "{name}"')
        else:
            # Perform the conversation
            fut = asyncio.ensure_future(convo.perform(
                # One of these may be None, but that's okay
                # The service will take care of handling that
                robot_a=self._robot_a,
                robot_b=self._robot_b,
            ))

            # While the conversation is in progress
            while not fut.done():
                # Get the cancel state
                cancel = None
                if index == 1:
                    cancel = self._cancel_a
                elif index == 2:
                    cancel = self._cancel_b

                # Handle cancelling
                if cancel:
                    self._tprint('Conversation cancelling')

                    # Reset the cancel state
                    if index == 1:
                        self._cancel_a = False
                    elif index == 2:
                        self._cancel_b = False

                    broken = True
                    break

                # Yield control
                await asyncio.sleep(0)

    async def _do_freeplay(self, index: int, robot: cozmo.robot.Robot):
        """
        Action for carrying out a conversation.

        :param index: The robot index
        :param robot: The robot instance
        """

        # Convert robot index to robot letter
        letter = 'A' if index == 1 else 'B'

        self._tprint(f'Robot {letter} is engaging in freeplay')

        # Start freeplay mode
        robot.start_freeplay_behaviors()

        # Sleep during freeplay
        while True:
            # Get the cancel state
            cancel = None
            if index == 1:
                cancel = self._cancel_a
            elif index == 2:
                cancel = self._cancel_b

            # Handle cancelling
            if cancel:
                self._tprint('Freeplay cancelling')

                # Reset the cancel state
                if index == 1:
                    self._cancel_a = False
                elif index == 2:
                    self._cancel_b = False

                break

            # Yield control
            await asyncio.sleep(0)

        # Stop freeplay mode
        robot.stop_freeplay_behaviors()

        # Sleep after freeplay
        await asyncio.sleep(2)

        # Play happy animation
        await robot.play_anim_trigger(cozmo.anim.Triggers.DriveEndHappy).wait_for_completed()

    async def _do_pong(self, index: int, robot: cozmo.robot.Robot):
        """
        Action for playing pong.

        :param index: The robot index
        :param robot: The robot instance
        """

        # Convert robot index to robot letter
        letter = 'A' if index == 1 else 'b'

        self._tprint(f'Robot {letter} is engaging in pong')

        # Look upward
        await robot.set_head_angle(cozmo.util.degrees(45)).wait_for_completed()

        over = False

        # The initial ball position
        ball_x = 90
        ball_y = 40

        # The initial ball velocity
        ball_vel_x = -2
        ball_vel_y = -1

        # The paddle x-axis offsets
        p1_x = 5
        p2_x = 123

        # Hear ye
        await robot.say_text("I'm bored, I will play some pong").wait_for_completed()

        # While the game is not over
        while not over:
            # Get the cancel state
            cancel = None
            if index == 1:
                cancel = self._cancel_a
            elif index == 2:
                cancel = self._cancel_b

            # Handle cancelling
            if cancel:
                self._tprint('Pong cancelling')

                # Reset the cancel state
                if index == 1:
                    self._cancel_a = False
                elif index == 2:
                    self._cancel_b = False

                break

            # Update paddles based on ball position and velocity
            p1_y = self._pong_compute_paddle_y(ball_x, ball_y, ball_vel_x, ball_vel_y)
            p2_y = self._pong_compute_paddle_y(ball_x, ball_y, ball_vel_x, ball_vel_y)

            # Reflect ball of top of screen
            if ball_y <= 2:
                ball_vel_y = ball_vel_y * -1

            # Reflect ball off bottom of screen
            if ball_y > 61:
                ball_vel_y = ball_vel_y * -1

            # If ball is to the left of paddle 1
            # This would indicate possible impact or win
            if p1_x >= ball_x >= 0:
                ball_vel_x, ball_vel_y = self._pong_check_impact(ball_x, ball_y, ball_vel_x, ball_vel_y, p1_y, robot)

            # If ball is to the right of paddle 2
            # This would indicate possible impact or win
            if p2_x <= ball_x <= 128:
                ball_vel_x, ball_vel_y = self._pong_check_impact(ball_x, ball_y, ball_vel_x, ball_vel_y, p2_y, robot)

            ball_x += ball_vel_x
            ball_y += ball_vel_y

            # If ball passed a paddle
            if ball_x < 0 or ball_x > 130:
                # Small delay
                await asyncio.sleep(0.5)

                # Say he won
                await robot.say_text("I win").wait_for_completed()

                # Play win animation
                await robot.play_anim_trigger(cozmo.anim.Triggers.CodeLabWin).wait_for_completed()

                # The game is over, but we will still update the face
                over = True

            # Update the face image
            face = self._pong_draw_face(0, 0, ball_x, ball_y, p1_x, p1_y, p2_x, p2_y)

            # Convert face image to screen
            screen = cozmo.oled_face.convert_image_to_screen_data(face)

            # Update Cozmo's face
            robot.display_oled_face_image(screen, 0.1)

            # Sleep for a bit
            await asyncio.sleep(0.02)

        # Set completion flag
        self._complete = True

    def _pong_compute_paddle_y(self, ball_x, ball_y, ball_vel_x, ball_vel_y):
        # Set paddle height to ball height with a random slop for effect
        return ball_y + random.randint(-5, 5)

    def _pong_draw_face(self, x, y, ball_x, ball_y, p2_x, p2_y, p1_x, p1_y):
        # The new face image
        face = Image.new('RGBA', (128, 64), (0, 0, 0, 255))

        # Drawing context
        draw = ImageDraw.Draw(face)

        # Draw ball
        draw.ellipse([ball_x - 5, ball_y - 5, ball_x + 5, ball_y + 5], fill=(255, 255, 255, 255))

        # Draw paddle 1 (left)
        draw.rectangle([p1_x + 3, p1_y - 10, p1_x, p1_y + 10], fill=(255, 255, 255, 255))

        # Draw paddle 2 (right)
        draw.rectangle([p2_x - 3, p2_y - 10, p2_x, p2_y + 10], fill=(255, 255, 255, 255))

        return face

    def _pong_check_impact(self, ball_x, ball_y, ball_vel_x, ball_vel_y, paddle_y, robot):
        # If the ball hit the paddle (within y-tolerance)
        if abs(paddle_y - ball_y) < 10:
            # Play the impact sound effect
            robot.play_audio(cozmo.audio.AudioEvents.SfxGameWin)

            ball_vel_x = ball_vel_x * -1
            ball_vel_y += (0.5 * (ball_y - paddle_y))

            if abs(ball_vel_y) < 0.2:
                ball_vel_y = 0.5

            # ball_vel_x = max([min([ball_vel_x * (float(random.randrange(9, 11)) / 10), 2]), 0.5])
            ball_vel_x = ball_vel_x * 1.1

        return ball_vel_x, ball_vel_y

    async def _do_meet_and_greet(self, index: int, robot: cozmo.robot.Robot):
        """
        Action for carrying out a conversation.

        :param index: The robot index
        :param robot: The robot instance
        """

        # Convert robot index to robot letter
        letter = 'A' if index == 1 else 'B'

        self._tprint(f'Robot {letter} is engaging in greeting')

        # Get the robot-specific services
        service_face = None
        if index == 1:
            service_face = self._service_face_a
        elif index == 2:
            service_face = self._service_face_b

        # Tilt the head upward to look for faces
        await robot.set_head_angle(cozmo.robot.MAX_HEAD_ANGLE).wait_for_completed()

        broken = False
        while not self._stopping and not broken:
            self._tprint('Waiting to detect a face')

            # Get the cancel state
            cancel = None
            if index == 1:
                cancel = self._cancel_a
            elif index == 2:
                cancel = self._cancel_b

            # Handle cancelling
            if cancel:
                self._tprint('Meet and greet cancelling')

                # Reset the cancel state
                if index == 1:
                    self._cancel_a = False
                elif index == 2:
                    self._cancel_b = False

                broken = True
                break

            # Submit a work order to detect a face (on a background thread)
            # Keeping it in concurrent future form will let us cancel it easily
            face_det_future = service_face.next_track()

            # While detection is not done
            while not face_det_future.done():
                # Get the cancel state
                cancel = None
                if index == 1:
                    cancel = self._cancel_a
                elif index == 2:
                    cancel = self._cancel_b

                # Handle cancelling
                if cancel:
                    self._tprint('Meet and greet cancelling')

                    # Reset the cancel state
                    if index == 1:
                        self._cancel_a = False
                    elif index == 2:
                        self._cancel_b = False

                    broken = True
                    break

                # Yield control
                await asyncio.sleep(0)

            if broken:
                break

            # The detected face
            face_det: DetectedFace = face_det_future.result()

            # The index of the tracked face
            # These are unique through time, so we'll never see this exact index again
            # (well, unless we get a signed 64-bit integer overflow)
            face_index = face_det.index

            # The coordinates of the detected face
            # This is a 4-tuple of the form (left, top, right, and bottom) with int components
            face_coords = face_det.coords

            self._tprint(f'Detected face {face_index} at {face_coords}')

            # TODO: Center on the face

            # Submit a work order to recognize the detected face (uses a background thread)
            # The face service is holding onto the original picture of the detected face
            # FIXME: This might actually be bad, as the detection is more lenient than recognition
            #  The detector might pick up a motion-blurred face, but then recognition might be bad
            #  This is not a priority for the group presentation, however, as we can control how fast we turn
            face_rec: RecognizedFace = await asyncio.wrap_future(service_face.recognize(face_index))

            # The face ID
            # This corresponds to the ID assigned to the matched face identity during program startup
            # In our implementation, this is the AUTO_INCREMENT field in the database table
            face_id = face_rec.fid

            # The face identity
            # This is a 128-tuple of doubles for the face vector (AKA encoding, embedding, descriptor, etc.)
            face_ident = face_rec.ident

            self._tprint(f'Recognized face {face_index} at {face_coords} as ID {face_id}')

            if face_id == -1:
                self._tprint('We do not know this face')

                # Ask for a name
                num = random.randrange(3)
                if num == 0:
                    await robot.say_text('Who are you? Please type your name.').wait_for_completed()
                elif num == 1:
                    await robot.say_text('What is your name? Please type it.').wait_for_completed()
                elif num == 2:
                    await robot.say_text('I don\'t know you. Please type your name.').wait_for_completed()

                # Get the name of the face
                # This is implemented as console input
                self._tprint('PLEASE PRESS THE ENTER KEY')  # This is a bad bad user experience, I know, but ugh...
                name = input('NAME: ')

                # Encode the identity to a string for storage in the database
                face_ident_enc = self._face_ident_encode(face_ident)

                # Insert face into the database and get the assigned face ID (thanks Herman, this is easy to use)
                face_id = database.insertNewStudent(name, face_ident_enc)

                # Add identity to both Cozmo A and B face services
                # This lets us recognize this face again in the same session
                # On subsequent sessions, we'll read from the database
                self._service_face_a.add_identity(face_id, face_ident)
                self._service_face_b.add_identity(face_id, face_ident)

                # Repeat the name
                num = random.randrange(3)
                if num == 0:
                    await robot.say_text(f'Hi, {name}!').wait_for_completed()
                elif num == 1:
                    await robot.say_text(f'Hello there, {name}!').wait_for_completed()
                elif num == 2:
                    await robot.say_text(f'Nice to meet you, {name}!').wait_for_completed()
            else:
                self._tprint('We know this face')

                # Get name and time last seen for this face
                name, time_last_seen = database.determineStudent(face_id)

                # Update time last seen for face
                database.checkForStudent(face_id)

                # TODO: Maybe we can add some "welcome back"-style messages that use the time last seen!

                # Welcome the person back
                num = random.randrange(3)
                if num == 0:
                    await robot.say_text(f'Welcome back, {name}!').wait_for_completed()
                elif num == 1:
                    await robot.say_text(f'Hello again, {name}!').wait_for_completed()
                elif num == 2:
                    await robot.say_text(f'Good to see you, {name}!').wait_for_completed()

    @staticmethod
    def _face_ident_decode(ident_enc: str) -> Tuple[float, ...]:
        """
        Decode a string-encoded face identity.

        :param ident_enc: The encoded identity
        :return: The decoded identity
        """

        # Load the 128-tuple of floats from JSON
        ident = json.loads(ident_enc)

        return ident

    @staticmethod
    def _face_ident_encode(ident: Tuple[float, ...]) -> str:
        """
        Encode a face identity to string.

        :param ident: The decoded identity
        :return: The encoded identity
        """

        # Dump the 128-tuple of floats into JSON
        ident_json = json.dumps(ident)

        return ident_json

    async def _do_return_to_waypoint(self, index: int, robot: cozmo.robot.Robot):
        """
        Action for returning to waypoint.

        :param index: The robot index
        :param robot: The robot instance
        """

        # Convert robot index to robot letter
        letter = 'A' if index == 1 else 'B'

        self._tprint(f'Robot {letter} is returning to waypoint')

        # Get the robot waypoint
        waypoint = None
        if index == 1:
            waypoint = self._robot_waypoint_a
        elif index == 2:
            waypoint = self._robot_waypoint_b

        # Return to the saved waypoint (based on Eric's routine)
        await robot.go_to_pose(waypoint).wait_for_completed()

    async def _choreographer(self):
        """
        The choreographer gives high-level commands to one or two robots.

        Following the algorithm designed by David.
        """

        self._tprint('Choreographer has started')

        # The Cozmo choice
        choice = 1

        # The idle flag
        idle = False

        # The current chosen queue
        queue_choice = None

        while not self._stopping:
            # Get the queue for the chosen robot
            if choice == 1:  # Chosen A
                queue_choice = self._robot_queue_a
            elif choice == 2:  # Chosen B
                queue_choice = self._robot_queue_b

            queue_choice.put(_RobotState.waypoint)
            queue_choice.put(_RobotState.greet)

            while self._is_battery_good(choice):
                if idle:
                    self._swap = False
                    queue_choice.put(_RobotState.waypoint)
                    queue_choice.put(_RobotState.greet)
                    idle = False

                # Pick a random activity
                rand_activity = random.randrange(1, 200)

                if rand_activity == 1:
                    self._tprint('Going to do conversation')

                    # Cancel greeting
                    if choice == 1:  # Chosen A
                        self._cancel_a = True
                    elif choice == 2:  # Chosen B
                        self._cancel_b = True

                    # Clear complete flag
                    self._complete = False

                    queue_choice.put(_RobotState.waypoint)
                    queue_choice.put(_RobotState.convo)

                    # Pick a random conversation
                    convos = self._service_convo.list()
                    convo_num = random.randrange(1, len(convos))
                    convo_name = convos[convo_num]
                    queue_choice.put(convo_name)

                    # While conversation is running
                    while not self._stopping and self._is_battery_good(choice) and not self._complete:
                        # Yield control
                        await asyncio.sleep(0)

                    self._tprint('Choreographer detected conversation complete')

                    # Set idle flag
                    idle = True
                elif rand_activity == 2:
                    self._tprint('Going to do pong')

                    # Cancel greeting
                    if choice == 1:  # Chosen A
                        self._cancel_a = True
                    elif choice == 2:  # Chosen B
                        self._cancel_b = True

                    # Clear complete flag
                    self._complete = False

                    queue_choice.put(_RobotState.waypoint)
                    queue_choice.put(_RobotState.pong)

                    # While pong is running
                    while not self._stopping and self._is_battery_good(choice) and not self._complete:
                        # Yield control
                        await asyncio.sleep(0)

                    self._tprint('Choreographer detected pong complete')

                    # Set idle flag
                    idle = True
                elif rand_activity == 3:
                    self._tprint('Going to do freeplay')

                    # Cancel greeting
                    if choice == 1:  # Chosen A
                        self._cancel_a = True
                    elif choice == 2:  # Chosen B
                        self._cancel_b = True

                    # Clear complete flag
                    self._complete = False

                    queue_choice.put(_RobotState.waypoint)
                    queue_choice.put(_RobotState.freeplay)

                    # While the freeplay mode is running
                    start = time.clock()
                    while not self._stopping and self._is_battery_good(choice):
                        if time.clock() - start > 20:  # Only stay in freeplay for twenty seconds
                            break

                        # Yield control
                        await asyncio.sleep(0)

                    # Cancel freeplay
                    if choice == 1:  # Chosen A
                        self._cancel_a = True
                    elif choice == 2:  # Chosen B
                        self._cancel_b = True

                    # Set idle flag
                    idle = True

                # Clear the completion flag
                self._complete = False

                # Sleep for a fixed time
                await asyncio.sleep(0.5)

        # Cancel greeting
        if choice == 1:  # Chosen A
            self._cancel_a = True
        elif choice == 2:  # Chosen B
            self._cancel_b = True

        # Clear complete flag
        self._complete = False

        queue_choice.put(_RobotState.waypoint)
        queue_choice.put(_RobotState.home)

        # While driving to home
        while not self._stopping and self._is_battery_good(choice) and not self._complete:
            # Yield control
            await asyncio.sleep(0)

        self._tprint('Choreographer detected driven to home')

        # Swap the Cozmos
        if choice == 1:
            choice = 2
        elif choice == 2:
            choice = 1

        # Get the queue for the chosen robot
        queue_choice = None
        if choice == 1:  # Chosen A
            queue_choice = self._robot_queue_a
        elif choice == 2:  # Chosen B
            queue_choice = self._robot_queue_b

        if choice == 1:
            if not self._robot_state_a == _RobotState.home:
                queue_choice.put(_RobotState.waypoint)
                queue_choice.put(_RobotState.home)
        elif choice == 2:
            if not self._robot_state_b == _RobotState.home:
                queue_choice.put(_RobotState.waypoint)
                queue_choice.put(_RobotState.home)

        self._tprint('Choreographer has stopped')

    def _is_battery_good(self, index: int):
        """
        Test if the battery on a robot is good.

        :param index: The robot index
        :return: True if such is the case, otherwise False
        """

        # Get the battery potential
        potential = 0
        if index == 1:
            potential = self._robot_a.battery_voltage
        elif index == 2:
            potential = self._robot_b.battery_voltage

        # If the battery is good...
        return potential > 3.5

    def _tprint(self, text: str):
        """
        Terminal print.

        This is kinda like print(), but it doesn't trample our terminal prompt.

        :param text: The text to print
        """

        # Lock the terminal interface
        with self._term.terminal_lock:
            # Asynchronously print to the terminal
            # They call this an "alert" in cmd2
            self._term.async_alert(text)


class InteractInterface(cmd2.Cmd):
    """
    Terminal interface for the interact operation.
    """

    intro = ''
    prompt = '(cozmo) '

    def __init__(self, op: OperationInteract):
        """
        Create an interact operation terminal interface.

        :param op: The interact operation
        """

        super().__init__()

        # Opt out of cmd2's built-in cmdline handling
        self.allow_cli_args = False

        # Keep the operation
        self._op = op

        # The selected robot index
        self._selected_robot: int = None

        # Our own conversation service
        # We use this to offer tab completions
        self._service_convo = ServiceConvo()

    def sigint_handler(self, signum: int, frame):
        # Quit the interface
        self.onecmd_plus_hooks(['quit'])

    select_parser = argparse.ArgumentParser()
    select_parser.add_argument('robot', type=str, help='robot to select (a/b or 1/2 to select, all else deselects)')

    @cmd2.with_argparser(select_parser)
    def do_select(self, args):
        """Change the selected Cozmo for future commands."""

        # Get the requested robot index
        self._selected_robot = self._robot_char_to_index(args.robot)

        if self._selected_robot == 1:
            print('Selected robot A')
        elif self._selected_robot == 2:
            print('Selected robot B')
        else:
            print('Deselected robot')

    def do_selected(self, args):
        """Query the selected robot."""

        if self._selected_robot == 1:
            print('Robot A is selected')
        elif self._selected_robot == 2:
            print('Robot B is selected')
        else:
            print('No robot selected')

    state_parser = argparse.ArgumentParser()
    state_parser.add_argument('robot', type=str, help='robot to query (a/b or 1/2, all else fails)')

    @cmd2.with_argparser(state_parser)
    def do_state(self, args):
        """Query the state of a single robot."""

        # Get the requested robot index
        index = self._robot_char_to_index(args.robot)

        # Get the robot state
        state = None
        if index == 1:  # Robot A
            # noinspection PyProtectedMember
            state = self._op._robot_state_a
        elif index == 2:  # Robot B
            # noinspection PyProtectedMember
            state = self._op._robot_state_b
        else:
            print(f'Invalid robot: "{args.robot}"')

        # Print name and number of state
        if state is not None:
            print(f'{state.value}: "{state.name}"')

    def do_cancel(self, args):
        """Cancel the activity on the selected Cozmo robot."""

        # Require a robot to be selected
        if self._selected_robot is None:
            print('No robot selected')
            return

        print('Cancelling the activity')

        # Set the appropriate cancel flag
        if self._selected_robot == 1:  # Robot A
            # noinspection PyProtectedMember
            self._op._cancel_a = True
        elif self._selected_robot == 2:  # Robot B
            # noinspection PyProtectedMember
            self._op._cancel_b = True

    def do_waypoint(self, args):
        """Drive the selected Cozmo to its waypoint."""

        # Require a robot to be selected
        if self._selected_robot is None:
            print('No robot selected')
            return

        print('Attempting to drive to waypoint')

        # Go to waypoint state
        self._get_robot_state_queue().put(_RobotState.waypoint)

    def do_home(self, args):
        """Drive the selected Cozmo from its waypoint to its charger."""

        # Require a robot to be selected
        if self._selected_robot is None:
            print('No robot selected')
            return

        print('Attempting to return to charger')

        # Go to home state
        self._get_robot_state_queue().put(_RobotState.home)

    convo_parser = argparse.ArgumentParser()
    convo_parser.add_argument('name', type=str, help='the conversation name')

    @cmd2.with_argparser(convo_parser)
    def do_convo(self, args):
        """Start conversation activity."""

        # Require a robot to be selected
        if self._selected_robot is None:
            print('No robot selected')
            return

        print('Attempting to start conversation activity')
        print(f'Requesting conversation "{args.name}"')

        # Go to convo state
        queue = self._get_robot_state_queue()
        queue.put(_RobotState.convo)
        queue.put(args.name)

    def do_greet(self, args):
        """Start meet and greet activity."""

        # Require a robot to be selected
        if self._selected_robot is None:
            print('No robot selected')
            return

        print('Attempting to start meet and greet activity')

        # Go to greet state
        self._get_robot_state_queue().put(_RobotState.greet)

    def do_freeplay(self, args):
        """Start freeplay activity."""

        # Require a robot to be selected
        if self._selected_robot is None:
            print('No robot selected')
            return

        print('Attempting to start freeplay activity')

        # Go to freeplay state
        self._get_robot_state_queue().put(_RobotState.freeplay)

    def do_pong(self, args):
        """Start pong activity."""

        # Require a robot to be selected
        if self._selected_robot is None:
            print('No robot selected')
            return

        print('Attempting to start pong activity')

        # Go to freeplay state
        self._get_robot_state_queue().put(_RobotState.pong)

    def do_swap(self, args):
        """Issue a manual swap."""

        print('Attempting to swap the Cozmos')

        # Set the swap flag
        self._op._swap = True

    def _get_robot_state_queue(self):
        """Get the state queue for the selected robot."""

        if self._selected_robot == 1:
            # noinspection PyProtectedMember
            return self._op._robot_queue_a
        elif self._selected_robot == 2:
            # noinspection PyProtectedMember
            return self._op._robot_queue_b

    @staticmethod
    def _robot_char_to_index(char: any) -> int:
        """
        Convert a robot character (e.g. 'a', 'B', '1', etc.) to its index.

        On error, this function returns zero.

        :param char: The robot character
        :return: The robot index
        """

        if char == 'a' or char == 'A' or char == '1':
            return 1
        elif char == 'b' or char == 'B' or char == '2':
            return 2
        else:
            return 0


# Stay on the charger during the connection process
cozmo.robot.Robot.drive_off_charger_on_connect = False
