#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import asyncio
from enum import Enum
from threading import Lock, Thread

import cmd2
import cozmo

from cozmonaut.operation import Operation


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


class OperationInteract(Operation):
    """
    An abstract operation.
    """

    def __init__(self, args: dict):
        super().__init__(args)

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

        # The robot instances
        self._robot_a: cozmo.robot.Robot = None
        self._robot_b: cozmo.robot.Robot = None

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

    def _thread_interact_main(self):
        """
        The main function of the interact thread.
        """

        try:
            # Create an event loop for interaction
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

                        print(f'On connection #{i}, robot A was assigned serial number {robot.serial} (need A and B)')

                    # If this serial matches that desired for robot B
                    if robot.serial == self._wanted_serial_b:
                        # Keep the connection
                        keep = True

                        # Assign robot B
                        self._robot_b = robot

                        print(f'On connection #{i}, robot B was assigned serial number {robot.serial} (need A and B)')

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

            print('Beginning interactive procedure')

            print('+-----------------------------------------------------------------+')
            print('| IMPORTANT: We are assuming both Cozmos start on their chargers! |')
            print('+-----------------------------------------------------------------+')

            asyncio.gather(
                # The watchdog coroutine handles the shutdown protocol
                self._watchdog(),

                # Driver coroutines for Cozmos A and B
                # These routines take care of running individual bite-size tasks
                self._driver(1, self._robot_a),
                self._driver(2, self._robot_b),

                # The choreographer coroutine automates the robots from a high level
                self._choreographer(),

                # Explicitly provide our event loop
                # Without this, there will be an error along the lines of "no current event loop"
                loop=loop,
            )

            # Run the event loop until it stops (it's not actually forever)
            loop.run_forever()

            print('Goodbye!')
        finally:
            # Set the stopped flag
            with self._stopped_lock:
                self._stopped = True

    async def _watchdog(self):
        """
        The watchdog handles shutdown requests.
        """

        print('Watchdog has started')

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

                print('The event loop will stop soon')
            else:
                # Yield control
                await asyncio.sleep(0)

        print('Watchdog has stopped')

    async def _driver(self, index: int, robot: cozmo.robot.Robot):
        """
        The driver for a single robot.

        :param index: The robot index (1 for robot A or 2 for robot B)
        :param robot: The robot instance
        """

        # Convert robot index to robot letter
        # This is only used for user-friendly log messages
        letter = 'A' if index == 1 else 'B'

        print(f'Driver for robot {letter} has started')

        # Stop if this driver is not needed
        if robot is None:
            print(f'Robot {letter} is not available, so driver {letter} is stopping')
            return

        while not self._stopping:
            # Yield control
            await asyncio.sleep(0)

        print(f'Driver for robot {letter} has stopped')

    async def _choreographer(self):
        """
        The choreographer gives high-level commands to one or two robots.
        """

        print('Choreographer has started')

        while not self._stopping:
            # Yield control
            await asyncio.sleep(0)

        print('Choreographer has stopped')


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

        # Keep the operation
        self._op = op

        # Opt out of cmd2's built-in cmdline handling
        self.allow_cli_args = False

    def sigint_handler(self, signum: int, frame):
        # Quit the interface
        self.onecmd_plus_hooks(['quit'])


# Stay on the charger during the connection process
cozmo.robot.Robot.drive_off_charger_on_connect = False
