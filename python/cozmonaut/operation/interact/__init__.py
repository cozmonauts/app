#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import asyncio
import functools
import json
import math
import random
from enum import Enum
from threading import Thread
from typing import Tuple

import cozmo

import cozmonaut.operation.interact.database
from cozmonaut.operation import AbstractOperation
from .face_tracker import FaceTracker, DetectedFace, RecognizedFace


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


class OperationInteract(AbstractOperation):
    """
    The interactive mode operation.

    In this mode, one or two Cozmos are commanded to meet and greet passersby.
    """

    def __init__(self, args: dict):
        """
        Initialize interact operation.

        :param args: The dictionary of string arguments
        """
        super().__init__(args)

        # The wanted serial numbers for connected Cozmos
        # The Cozmo SDK makes connections non-deterministically
        # One day the left Cozmo might be A, another it might be B
        # By supplying serial numbers, we can take control of this
        self._wanted_serial_a = args.get('ser-a', '45a18821')  # These are actual serial numbers
        self._wanted_serial_b = args.get('ser-b', '0241c714')  # These are actual serial numbers

        # Grab the mode of interaction from arguments
        self._mode = InteractMode[args.get('mode', 'both')]

        # The interact thread
        # We use this to stay asynchronous
        self._thread: Thread = None

        # The robot instances
        # Each one corresponds to the real deal
        self._robot_a: cozmo.robot.Robot = None
        self._robot_b: cozmo.robot.Robot = None

        # The face trackers
        # Each one corresponds to an assigned robot
        self._face_tracker_a: FaceTracker = None
        self._face_tracker_b: FaceTracker = None

        # The active robot index
        # It can be 0 (none), 1 (Cozmo A), or 2 (Cozmo B)
        self._active_robot = 0

        # The index of the last robot that was active
        # This is initialized to 2 as a hack so we start with 1
        self._last_active_robot = 2

        # Whether or not to enable face tracking
        self._enable_face_tracking = False

        # Whether or not there is a pending advance from charger
        self._pending_advance_from_charger = False

        # Whether or not there is a pending interact
        self._pending_interact = False

        # Whether or not there is a pending return to charger
        self._pending_return_to_charger = False

        # Whether or not there is a pending low battery test
        self._pending_low_battery_test = False

        # Whether or not the "faces" diversion is requested
        self._req_diversion_faces = False

        # Whether or not the "converse" diversion is requested
        self._req_diversion_converse = False

        # Whether or not the "wander" diversion is requested
        self._req_diversion_wander = False

    def start(self):
        """
        Start the interactive mode.
        """
        super().start()

        # Spawn the interact thread
        self._thread = Thread(target=self._interact_main)
        self._thread.start()

    def stop(self):
        """
        Stop the interactive mode.
        """
        super().stop()

        print('Interactive mode is stopping, so returning the Cozmos')
        self._pending_return_to_charger = True

        # Wait for the interact thread to die
        self._thread.join()
        self._thread = None

    def _interact_main(self):
        """
        The main function of the interact thread.
        """

        # Create an event loop on this thread
        loop = asyncio.new_event_loop()

        # Print some stuff about the mode
        if self._mode == InteractMode.both:
            print('Configured for both Cozmos A and B')
            print(f'Want Cozmo A to have serial number {self._wanted_serial_a}')
            print(f'Want Cozmo B to have serial number {self._wanted_serial_b}')
        elif self._mode == InteractMode.just_a:
            print('Configured for just Cozmo A')
            print(f'Want Cozmo A to have serial number {self._wanted_serial_a}')
        elif self._mode == InteractMode.just_b:
            print('Configured for just Cozmo B')
            print(f'Want Cozmo B to have serial number {self._wanted_serial_b}')

        print('Establishing as many connections as possible')

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
                print('No more Cozmos available (this is normal)')
                break

            # The connection index is just the length of the connections list
            i = len(connections)

            print(f'Established connection #{i}')

            # Keep the connection
            connections.insert(i, conn)

        # Go over all the connections we've made
        for i in range(0, len(connections)):
            conn = connections[i]

            # Whether or not to keep the connection
            # We only keep the ones we need, but we don't know which those are until we've connected to everyone
            # (well, we COULD short-circuit once we've populated self._robot_a and self._robot_b objects, but ugh...)
            keep = False

            # Wait for the robot on this connection
            robot = loop.run_until_complete(conn.wait_for_robot())

            print(f'Robot on connection #{i} has serial number {robot.serial}')

            # If we're assigning both Cozmos
            if self._mode == InteractMode.both:
                # If this serial matches that desired for robot A
                if robot.serial == self._wanted_serial_a:
                    # Keep the connection
                    keep = True

                    # Assign robot A
                    self._robot_a = robot

                    print(f'On connection #{i}, robot A was assigned serial number {robot.serial} (need both A and B)')

                # If this serial matches that desired for robot B
                if robot.serial == self._wanted_serial_b:
                    # Keep the connection
                    keep = True

                    # Assign robot B
                    self._robot_b = robot

                    print(f'On connection #{i}, robot B was assigned serial number {robot.serial} (need both A and B)')

            # If we're assigning just Cozmo A
            if self._mode == InteractMode.just_a:
                # If this serial matches that desired for robot A
                if robot.serial == self._wanted_serial_a:
                    # Keep the connection
                    keep = True

                    # Assign robot A
                    self._robot_a = robot

                    print(f'On connection #{i}, robot A was assigned serial number {robot.serial} (need just A)')

            # If we're assigning just Cozmo B
            if self._mode == InteractMode.just_b:
                # If this serial matches that desired for robot B
                if robot.serial == self._wanted_serial_b:
                    # Keep the connection
                    keep = True

                    # Assign robot B
                    self._robot_b = robot

                    print(f'On connection #{i}, robot B was assigned serial number {robot.serial} (need just B)')

            # If we're not keeping this connection
            if not keep:
                print(f'Connection #{i} is not needed, so disconnecting it')

                # Abort the connection
                conn.abort(0)

        # Stop if we're missing a Cozmo
        if self._mode == InteractMode.both:
            # Whether or not one is missing
            missing = False

            # Look at A
            if self._robot_a is None:
                missing = True
                print('Configured for both, but Cozmo A is missing')

            # Look at B
            if self._robot_b is None:
                missing = True
                print('Configured for both, but Cozmo B is missing')

            # If one is missing
            if missing:
                print('At least one Cozmo is missing, so refusing to continue')
                return
        elif self._mode == InteractMode.just_a:
            # Look at A
            if self._robot_a is None:
                print('Cozmo A is missing, so refusing to continue')
                return
        elif self._mode == InteractMode.just_b:
            # Look at B
            if self._robot_b is None:
                print('Cozmo B is missing, so refusing to continue')
                return

        print('Setting up face trackers')

        # Create face trackers
        self._face_tracker_a = FaceTracker()
        self._face_tracker_b = FaceTracker()

        print('Loading known faces from database')

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

                # Register identity with both face trackers
                # That way both Cozmos will be able to recognize the face
                self._face_tracker_a.add_identity(fid, ident)
                self._face_tracker_b.add_identity(fid, ident)

        # Start the face trackers
        self._face_tracker_a.start()
        self._face_tracker_b.start()

        print('Beginning interactive procedure')

        print('+-----------------------------------------------------------------+')
        print('| IMPORTANT: We are assuming both Cozmos start on their chargers! |')
        print('+-----------------------------------------------------------------+')

        asyncio.gather(
            # Driver coroutines for Cozmos A and B
            self._driver(1, self._robot_a),
            self._driver(2, self._robot_b),

            # The governor coroutine manages the whole thing
            self._governor(),

            # Explicitly provide our event loop
            # Without this, there will be an error along the lines of 'no current event loop'
            loop=loop,
        )

        # Run the event loop until it stops (it's not actually forever)
        loop.run_forever()

        print('Tearing down face trackers')

        # TODO: Save to the database

        # Stop the trackers
        self._face_tracker_a.stop()
        self._face_tracker_b.stop()

        print('Goodbye!')

    async def _driver(self, index: int, robot: cozmo.robot.Robot):
        """
        A driver is the main function for operating a single Cozmo robot.

        Drivers take command from the governor.

        :param index: The robot index (1=A, 2=B)
        :param robot: The robot instance
        """

        print(f'Driver started for Cozmo {"A" if index == 1 else "B"} (robot #{index})')

        # Enable color imaging on this Cozmo
        robot.camera.color_image_enabled = True
        robot.camera.image_stream_enabled = True

        # Listen for camera frames from this Cozmo
        # We use functools to create a partially-bound function that sneaks in our index and robot parameters
        robot.camera.add_event_handler(cozmo.robot.camera.EvtNewRawCameraImage,
                                       functools.partial(self._driver_on_evt_new_raw_camera_image, index, robot))

        # Sub-coroutines
        sub = asyncio.gather(
            self._watch_battery(index, robot),
            self._watch_faces(index, robot),
            self._diversion_faces(index, robot),
        )

        # The waypoint pose
        waypoint: cozmo.util.Pose = None

        while not (self.stopped and self._active_robot != index):
            # If this Cozmo robot is active
            if self._active_robot == index:
                # If an advance is pending
                if self._pending_advance_from_charger:
                    #
                    # SECTION FOR DRIVING FROM THE CHARGER
                    # (the waypoint pose is saved here)
                    #

                    # Drive off the contacts
                    # We need to do this to get access to other drive commands
                    await robot.drive_off_charger_contacts().wait_for_completed()

                    # Drive to the waypoint
                    await robot.drive_straight(distance=cozmo.util.distance_mm(250),
                                               speed=cozmo.util.speed_mmps(100)).wait_for_completed()

                    # Save the robot pose as the waypoint (based on Eric's routine)
                    waypoint = robot.pose

                    # Clear pending flag
                    self._pending_advance_from_charger = False

                    print(f'Driver indicates Cozmo {"A" if index == 1 else "B"} (robot #{index}) is done advancing')

                # If interaction is pending
                if self._pending_interact:
                    #
                    # SECTION FOR INTERACTING/CONVERSING
                    #

                    # Clear pending flag
                    self._pending_interact = False

                    print(f'Driver indicates Cozmo {"A" if index == 1 else "B"} (robot #{index}) is done interacting')

                # If a return to charger is pending
                if self._pending_return_to_charger:
                    #
                    # SECTION FOR RETURNING TO THE CHARGER
                    # (the saved waypoint pose is used here)
                    #

                    # Return to the saved waypoint (based on Eric's routine)
                    await robot.go_to_pose(waypoint).wait_for_completed()

                    # Turn toward the charger
                    await robot.turn_in_place(cozmo.util.degrees(180)).wait_for_completed()

                    #
                    # BEGIN INTEGRATED CHARGER RETURN CODE
                    # This is based on Herman's routines
                    #

                    # Look a little bit down but not straight ahead
                    # We need the camera to be able to see the charger
                    await robot.set_head_angle(cozmo.util.degrees(0)).wait_for_completed()

                    # Cozmo's accelerometer is located in his head
                    # We need to take a baseline reading before we use accelerometer during charger parking
                    pitch_threshold = math.fabs(robot.pose_pitch.degrees) + 1

                    # Drive to the charger
                    await self._driver_go_to_charger_coarse(robot)

                    # If the charger location is known (it should be)
                    if robot.world.charger is not None:
                        # Invalidate the charger pose
                        if robot.world.charger.pose.is_comparable(robot.pose):
                            robot.world.charger.pose.invalidate()

                    # Look for the charger again
                    await self._driver_find_charger(robot)

                    # Add finishing touches to our staging
                    await self._driver_go_to_charger_fine(robot)

                    # Face away from the charger (very precisely)
                    await robot.turn_in_place(cozmo.util.degrees(180),
                                              angle_tolerance=cozmo.util.degrees(2)).wait_for_completed()

                    # Point head forward-ish and lift lift out of way of charger
                    await robot.set_lift_height(height=0.5, max_speed=10, in_parallel=True).wait_for_completed()
                    await robot.set_head_angle(cozmo.util.degrees(0), in_parallel=True).wait_for_completed()

                    print('Begin strike phase')
                    print('The robot will try to strike the base of the charger')

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
                            print('Timed out while waiting for robot to strike the charger')
                            break
                        elif math.fabs(robot.pose_pitch.degrees) >= pitch_threshold:
                            print('The robot seems to have struck the charger (this is normal)')
                            break

                    # Striking done, stop motors
                    robot.stop_all_motors()

                    # Wait a little
                    await asyncio.sleep(0.5)

                    print('Begin flattening phase')
                    print('The robot will try to flatten out on the charger')

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
                            print('Timed out while waiting for robot to flatten out on the charger')
                            break
                        elif math.fabs(robot.pose_pitch.degrees) > 20:
                            print('Robot pitch has reached an unexpected value (drove on wall?)')
                            break
                        elif math.fabs(robot.pose_pitch.degrees) < pitch_threshold:
                            print('The robot seems to have flattened out on the charger (this is normal)')
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
                        print('The robot is on the charger... Let\'s celebrate!')

                        # Play a celebration animation
                        await robot.drive_off_charger_contacts().wait_for_completed()
                        await robot.play_anim_trigger(cozmo.anim.Triggers.CodeLabCelebrate, ignore_body_track=True,
                                                      ignore_lift_track=True, in_parallel=True).wait_for_completed()
                        await robot.backup_onto_charger(max_drive_time=3)
                    else:
                        print('The charger was not detected! Assuming we\'re on it?')  # TODO: What do? Call for help...

                    #
                    # END INTEGRATED CHARGER RETURN CODE
                    #

                    # Clear all pending flags
                    self._pending_advance_from_charger = False
                    self._pending_interact = False
                    self._pending_return_to_charger = False
                    self._pending_low_battery_test = False

                    # Clear active robot
                    self._last_active_robot = index
                    self._active_robot = 0

                    print(f'Driver indicates Cozmo {"A" if index == 1 else "B"} (robot #{index}) is done returning')

            # Yield control
            await asyncio.sleep(0)

        # Await sub-coroutines
        await sub

        print(f'Driver for Cozmo {"A" if index == 1 else "B"} (robot #{index}) stopping')

    def _driver_on_evt_new_raw_camera_image(self, index: int, robot: cozmo.robot.Robot,
                                            evt: cozmo.robot.camera.EvtNewRawCameraImage, **kwargs):
        """
        Called by the Cozmo SDK when a camera frame comes in.

        :param index: The robot index (ours)
        :param robot: The robot instance (ours)
        :param evt: The event (SDK)
        :param kwargs: Excess keyword arguments
        """

        # The camera frame image
        image = evt.image

        # If face tracking is enabled
        if self._enable_face_tracking:
            # The face tracker for this Cozmo robot
            tracker: FaceTracker = None

            # Pick the corresponding face tracker
            if index == 1:
                tracker = self._face_tracker_a
            elif index == 2:
                tracker = self._face_tracker_b

            # Update the Cozmo-corresponding tracker with the new camera frame
            tracker.update(image)

    async def _driver_find_charger(self, robot: cozmo.robot.Robot) -> cozmo.objects.Charger:
        """
        Locate the nearest charger from the perspective of a robot.

        Part of the driver routine for a single Cozmo robot.

        :param robot: The robot instance
        """

        print('Starting to look for the charger')

        rnd = 1

        # Be persistent, Cozmo!
        while True:
            print(f'Look for charger (round {rnd})')
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
                print('The charger was found!')
                return seen_charger
            else:
                print('The charger was not found! :(')

                # Play frustrated animation
                await robot.play_anim_trigger(cozmo.anim.Triggers.FrustratedByFailureMajor).wait_for_completed()

                # Ask for help
                # TODO: Is is okay that this happens here? I know we talked about asking for help...
                await robot.say_text('A little help?').wait_for_completed()

    async def _driver_go_to_charger_coarse(self, robot: cozmo.robot.Robot):
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
                print('The charger pose is already known')

                # Just take the charger reference
                charger = robot.world.charger

        # If we don't yet have the charger reference
        if not charger:
            # Find the charger
            charger = await self._driver_find_charger(robot)

        # Drive to the charger the first time
        # This is a ballpark maneuver; we'll fine-tune it next
        await robot.go_to_object(charger, distance_from_object=cozmo.util.distance_mm(80),
                                 num_retries=5).wait_for_completed()

    async def _driver_go_to_charger_fine(self, robot: cozmo.robot.Robot):
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
        distance = math.sqrt((virtual_pos[0] - robot_pos[0]) ** 2 + (virtual_pos[1] - robot_pos[1]) ** 2 + (
                virtual_pos[2] - robot_pos[2]) ** 2)

        # Angle of vector going from robot's origin to target's position
        vec = (virtual_pos[0] - robot_pos[0], virtual_pos[1] - robot_pos[1], virtual_pos[2] - robot_pos[2])
        theta_t = math.atan2(vec[1], vec[0])

        # Face the target position
        angle = self._util_wrap_radians(theta_t - robot_rot_xy)
        await robot.turn_in_place(cozmo.util.radians(angle)).wait_for_completed()

        # Drive toward the target position
        await robot.drive_straight(cozmo.util.distance_mm(distance), cozmo.util.speed_mmps(speed)).wait_for_completed()

        # Face the charger
        angle = self._util_wrap_radians(charger_rot_xy - theta_t)
        await robot.turn_in_place(cozmo.util.radians(angle)).wait_for_completed()

        try:
            charger = await robot.world.wait_for_observed_charger(timeout=2, include_existing=True)
        except cozmo.exceptions.CozmoSDKException:
            print('Charger not seen, so can\'t verify positioning')

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
        distance = math.sqrt((virtual_pos[0] - robot_pos[0]) ** 2 + (virtual_pos[1] - robot_pos[1]) ** 2 + (
                virtual_pos[2] - robot_pos[2]) ** 2)

        distance_tol = 5
        angle_tol = 5 * math.pi / 180
        if distance < distance_tol and math.fabs(robot_rot_xy - charger_rot_xy) < angle_tol:
            print('Successfully aligned')
        else:
            print('Did not align successfully')  # TODO: Should we retry here?

    @staticmethod
    def _util_wrap_radians(angle: float):
        while angle >= 2 * math.pi:
            angle -= 2 * math.pi
        while angle <= -2 * math.pi:
            angle += 2 * math.pi

        if angle > math.pi:
            angle -= 2 * math.pi
        elif angle < -math.pi:
            angle += 2 * math.pi

        return angle

    async def _diversion_faces(self, index: int, robot: cozmo.robot.Robot):
        """
        The faces diversion.

        :param index: The robot index
        :param robot: The robot instance
        """

        while not self.stopped:
            # Yield while not stopping and faces diversion is not requested for this robot
            while not self.stopped and not (self._active_robot == index and self._req_diversion_faces):
                await asyncio.sleep(0)

            print('Engaging faces diversion')

            # Enable face tracking
            # The face watcher coroutine does the meet-and-greet for now
            self._enable_face_tracking = True

            # Yield while faces diversion is requested for this robot
            while not self.stopped and self._active_robot == index and self._req_diversion_faces:
                await asyncio.sleep(0)

            # Disable face tracking
            self._enable_face_tracking = False

            print('Disengaging faces diversion')

            # Yield control
            await asyncio.sleep(0)

    async def _governor(self):
        """
        The governor is responsible for commanding the endeavor. It decides
        which Cozmo should be out and about, and it decides when to reign one or
        both in.

        The governor can operate independently, or it can take command from the
        user under manual override from C code.
        """

        print('Governor started')

        while not (self.stopped and self._active_robot == 0):
            # If no robot is currently active
            if self._active_robot == 0:
                print(f'Robot {self._last_active_robot} is no longer active')

                # Pick the next active robot
                # It is the opposite of the last active robot
                if self._last_active_robot == 1:
                    self._active_robot = 2
                elif self._last_active_robot == 2:
                    self._active_robot = 1

                print(f'Governor has activated robot {self._active_robot}')

                # Advance from charger
                self._pending_advance_from_charger = True

                # Yield while advancing
                while self._pending_advance_from_charger:
                    await asyncio.sleep(0)

                print(f'Governor detects robot {self._active_robot} has advanced')

                # Set up for interaction
                self._pending_interact = True

                # FIXME: The faces diversion is hardcoded
                self._pending_diversion = True
                self._req_diversion_faces = True

                # Yield while interacting
                while self._pending_interact:
                    await asyncio.sleep(0)

            # Yield control
            await asyncio.sleep(0)

        print('Governor is scheduling event loop termination')

        # Schedule the event loop to terminate
        loop = asyncio.get_event_loop()
        loop.call_soon(loop.stop)

    async def _watch_battery(self, index: int, robot: cozmo.robot.Robot):
        """
        A battery watcher for a single Cozmo robot.

        :param index: The robot index (1=A, 2=B)
        :param robot: The robot instance
        """

        print(f'Battery watcher started for Cozmo {"A" if index == 1 else "B"} (robot #{index})')

        while not self.stopped:
            # If this robot is active (implies not charging)
            if self._active_robot == index:
                # Detect low battery for auto retreat
                if robot.battery_voltage < 3.5 or self._pending_low_battery_test:
                    # If a low battery test is pending
                    if self._pending_low_battery_test:
                        print('+--------------------------------+')
                        print('| Testing low battery condition! |')
                        print('+--------------------------------+')

                    print('The battery is low, so return to charger')

                    # Invoke return to charger
                    self._pending_return_to_charger = True

                    # Yield while returning to charger
                    while self._pending_return_to_charger:
                        await asyncio.sleep(0)

                    # Clear pending test flag
                    self._pending_low_battery_test = False

            # Sleep for a bit
            await asyncio.sleep(3)  # TODO: Wait for however long

        print(f'Battery watcher for Cozmo {"A" if index == 1 else "B"} (robot #{index}) stopping')

    async def _watch_faces(self, index: int, robot: cozmo.robot.Robot):
        """
        A face watcher for a single Cozmo robot.

        :param index: The robot index (1=A, 2=B)
        :param robot: The robot instance
        """

        print(f'Face watcher started for Cozmo {"A" if index == 1 else "B"} (robot #{index})')

        # The face tracker for this Cozmo robot
        tracker: FaceTracker = None

        # Pick the corresponding face tracker
        if index == 1:
            tracker = self._face_tracker_a
        elif index == 2:
            tracker = self._face_tracker_b

        while not self.stopped:
            # If face tracking is not yet enabled
            if not self._enable_face_tracking:
                print('Waiting for face tracking to be enabled')

                # Yield while face tracking is not enabled
                while not self._enable_face_tracking:
                    await asyncio.sleep(0)

            # If this robot is active (implies not charging)
            if self._active_robot == index:
                print('Waiting to detect a face')

                # Submit a work order to detect a face (on a background thread)
                # Keeping it in concurrent future form will let us cancel it easily
                face_det_future = tracker.next_track()

                # While detection is not done
                while not face_det_future.done():
                    # If face tracking is disabled, cancel detection
                    if not self._enable_face_tracking:
                        print('Face tracking early disable, cancelling detection')
                        face_det_future.cancel()
                        break

                    # Yield control
                    await asyncio.sleep(0)

                # Bail out if face tracking is disabled
                if not self._enable_face_tracking:
                    continue

                # The detected face
                face_det: DetectedFace = face_det_future.result()

                # The index of the tracked face
                # These are unique through time, so we'll never see this exact index again
                # (well, unless we get a signed 64-bit integer overflow)
                face_index = face_det.index

                # The coordinates of the detected face
                # This is a 4-tuple of the form (left, top, right, and bottom) with int components
                face_coords = face_det.coords

                print(f'Detected face {face_index} at {face_coords}')

                # TODO: Center on the face

                # Submit a work order to recognize the detected face (uses a background thread)
                # The face tracker is holding onto the original picture of the detected face
                # FIXME: This might actually be bad, as the detection is more lenient than recognition
                #  The detector might pick up a motion-blurred face, but then recognition might be bad
                #  This is not a priority for the group presentation, however, as we can control how fast we turn
                face_rec: RecognizedFace = await asyncio.wrap_future(tracker.recognize(face_index))

                # The face ID
                # This corresponds to the ID assigned to the matched face identity during program startup
                # In our implementation, this is the AUTO_INCREMENT field in the database table
                face_id = face_rec.fid

                # The face identity
                # This is a 128-tuple of doubles for the face vector (AKA encoding, embedding, descriptor, etc.)
                face_ident = face_rec.ident

                print(f'Recognized face {face_index} at {face_coords} as ID {face_id}')

                if face_id == -1:
                    print('We do not know this face')

                    # Ask for a name
                    num = random.randrange(3)
                    if num == 0:
                        await robot.say_text('Who are you?').wait_for_completed()
                    elif num == 1:
                        await robot.say_text('What is your name?').wait_for_completed()
                    elif num == 2:
                        await robot.say_text('Please say your name.').wait_for_completed()

                    # TODO: Get this from either speech rec or the command-line
                    name = 'Bob'

                    # Encode the identity to a string for storage in the database
                    face_ident_enc = self._face_ident_encode(face_ident)

                    # Insert face into the database and get the assigned face ID (thanks Herman, this is easy to use)
                    face_id = database.insertNewStudent(name, face_ident_enc)

                    # Add identity to both Cozmo A and B face trackers
                    # This lets us recognize this face again in the same session
                    # On subsequent sessions, we'll read from the database
                    self._face_tracker_a.add_identity(face_id, face_ident)
                    self._face_tracker_b.add_identity(face_id, face_ident)

                    # Repeat the name
                    num = random.randrange(3)
                    if num == 0:
                        await robot.say_text(f'Hi, {name}!').wait_for_completed()
                    elif num == 1:
                        await robot.say_text(f'Hello there, {name}!').wait_for_completed()
                    elif num == 2:
                        await robot.say_text(f'Nice to meet you, {name}!').wait_for_completed()
                else:
                    print('We know this face')

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

            # Yield control
            await asyncio.sleep(0)  # TODO: Should we sleep for longer?

        print(f'Face watcher for Cozmo {"A" if index == 1 else "B"} (robot #{index}) stopping')

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


# Do not leave the charger automatically
cozmo.robot.Robot.drive_off_charger_on_connect = False
