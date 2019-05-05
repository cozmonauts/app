#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import asyncio
import random
from enum import Enum
from threading import Thread

import cozmo

from cozmonaut.operation import AbstractOperation


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
        self._thread = None

        # The robot instances
        # Each one corresponds to the real deal
        self._robot_a = None
        self._robot_b = None

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
        sub = asyncio.gather(self._watch_battery(index, robot))

        while not (self.stopped and self._active_robot != index):
            # If this Cozmo robot is active
            if self._active_robot == index:
                # If an advance is pending
                if self._pending_advance_from_charger:
                    # Drive off the contacts
                    # We need to do this to get access to other drive commands
                    await robot.drive_off_charger_contacts().wait_for_completed()

                    # Drive to the waypoint
                    await robot.drive_straight(distance=cozmo.util.Distance(distance_mm=250),
                                               speed=cozmo.util.Speed(speed_mmps=100)).wait_for_completed()

                    # Clear pending flag
                    self._pending_advance_from_charger = False

                # If interaction is pending
                if self._pending_interact:
                    print('interact')

                    # Clear pending flag
                    self._pending_interact = False

                # If a return to charger is pending
                if self._pending_return_to_charger:
                    # Drive backward
                    await robot.drive_straight(distance=cozmo.util.Distance(distance_mm=-250),
                                               speed=cozmo.util.Speed(speed_mmps=100)).wait_for_completed()

                    # Drive back onto the contacts
                    await robot.drive_straight(distance=cozmo.util.Distance(distance_mm=-60),
                                               speed=cozmo.util.Speed(speed_mmps=20)).wait_for_completed()

                    # Clear pending flag
                    self._pending_return_to_charger = False

                    # Clear active robot
                    self._last_active_robot = self._active_robot
                    self._active_robot = 0

            # Yield control
            await asyncio.sleep(0)

        # Await sub-coroutines
        await sub

        print(f'Driver for Cozmo {"A" if index == 1 else "B"} (robot #{index}) stopping')

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

                        # Clear pending flag
                        self._pending_low_battery_test = False

                    print('The battery is low, so return to charger')

                    # Invoke return to charger
                    self._pending_return_to_charger = True

                if random.randrange(25) == 0:
                    self._pending_low_battery_test = True  # FIXME

            # Sleep for a bit
            await asyncio.sleep(3)

        print(f'Battery watcher for Cozmo {"A" if index == 1 else "B"} (robot #{index}) stopping')


# Do not leave the charger automatically
cozmo.robot.Robot.drive_off_charger_on_connect = False
