#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import asyncio
import math
from enum import Enum
from threading import Thread

import cozmo

from cozmonaut.operation import AbstractOperation
from .face_tracker import FaceTracker


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

        # Whether or not there is a pending advance from charger
        self._pending_advance_from_charger = False

        # Whether or not there is a pending interact
        self._pending_interact = False

        # Whether or not there is a pending return to charger
        self._pending_return_to_charger = False

        # Whether or not there is a pending low battery test
        self._pending_low_battery_test = False

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

        # FIXME: Remove this
        tyler_face = (
            -0.103433,
            0.0713784,
            0.0813356,
            -0.0747395,
            -0.157589,
            -0.0386992,
            -0.0319699,
            -0.00274016,
            0.0867231,
            -0.0220311,
            0.242471,
            0.0148122,
            -0.252416,
            -0.0551133,
            -0.0037139,
            0.0990293,
            -0.113765,
            -0.0226992,
            -0.0938466,
            -0.0400318,
            0.126524,
            0.102942,
            0.0550079,
            0.0616467,
            -0.145211,
            -0.260875,
            -0.105383,
            -0.0524487,
            0.00731247,
            -0.135143,
            0.0509941,
            0.124918,
            -0.109638,
            -0.0350157,
            0.0340424,
            0.0950269,
            -0.0593138,
            -0.0289018,
            0.215726,
            -0.0228096,
            -0.149361,
            0.0423131,
            0.0110523,
            0.264083,
            0.194999,
            0.0382402,
            0.0235397,
            -0.0508239,
            0.100998,
            -0.320135,
            0.0635357,
            0.134587,
            0.0839489,
            0.050831,
            0.0836643,
            -0.125788,
            0.0253968,
            0.212677,
            -0.222989,
            0.0768562,
            -0.0297501,
            -0.215015,
            -0.0410392,
            -0.110664,
            0.166501,
            0.0996042,
            -0.129823,
            -0.148502,
            0.147683,
            -0.152009,
            -0.145286,
            0.145061,
            -0.140681,
            -0.147379,
            -0.37368,
            0.0436715,
            0.353895,
            0.153631,
            -0.225468,
            0.0191243,
            -0.01694,
            0.0200662,
            0.0228013,
            0.0611707,
            -0.0946287,
            -0.0709029,
            -0.121012,
            0.0488099,
            0.17418,
            -0.0588228,
            -0.0645145,
            0.26763,
            0.092387,
            0.115437,
            0.0444944,
            0.0116651,
            -0.00945554,
            -0.0874052,
            -0.132031,
            0.0409098,
            0.0522451,
            -0.105967,
            -0.020343,
            0.127948,
            -0.15351,
            0.168118,
            -0.0352881,
            -0.045533,
            -0.0601219,
            -0.0499158,
            -0.139128,
            0.0365747,
            0.188973,
            -0.290735,
            0.218931,
            0.203897,
            0.0409592,
            0.125365,
            0.0873372,
            0.0437877,
            -0.0335225,
            -0.054352,
            -0.145829,
            -0.065083,
            0.144216,
            -0.0487921,
            0.0604078,
            0.0337079
        )
        self._face_tracker_a.add_identity(42, tyler_face)
        self._face_tracker_b.add_identity(42, tyler_face)

        # TODO: Load from the database

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

        # Sub-coroutines
        sub = asyncio.gather(
            self._watch_battery(index, robot),
            self._watch_faces(index, robot),
        )

        # The waypoint pose
        waypoint: cozmo.util.Pose = None

        while not (self.stopped and self._active_robot != index):
            # If this Cozmo robot is active
            if self._active_robot == index:
                # If an advance is pending
                if self._pending_advance_from_charger:
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
                    print('interact')

                    # TODO
                    await robot.turn_in_place(cozmo.util.degrees(90)).wait_for_completed()
                    await robot.drive_straight(distance=cozmo.util.distance_mm(50),
                                               speed=cozmo.util.speed_mmps(20)).wait_for_completed()

                    # Clear pending flag
                    self._pending_interact = False

                    print(f'Driver indicates Cozmo {"A" if index == 1 else "B"} (robot #{index}) is done interacting')

                # If a return to charger is pending
                if self._pending_return_to_charger:
                    # Return to the waypoint
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
                        print('The charger was not detected! Assuming we\'re on it?')  # TODO: What do?

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

    async def _driver_find_charger(self, robot: cozmo.robot.Robot):
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
            print('Did not align successfully')  # TODO: Should retry

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

                # Interact with people
                self._pending_interact = True

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

        while not self.stopped:
            # If this robot is active (implies non charging)
            if self._active_robot == index:
                pass

            # Sleep for a bit
            await asyncio.sleep(1)  # TODO: Wait for however long

        print(f'Face watcher for Cozmo {"A" if index == 1 else "B"} (robot #{index}) stopping')


# Do not leave the charger automatically
cozmo.robot.Robot.drive_off_charger_on_connect = False
