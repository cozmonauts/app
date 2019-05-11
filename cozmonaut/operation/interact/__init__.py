#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import argparse
import asyncio
import queue
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
        letter = 'A' if index == 1 else 'B'

        print(f'Driver for robot {letter} has started')

        # Stop if this driver is not needed
        if robot is None:
            print(f'Robot {letter} is not available, so driver {letter} is stopping')
            return

        # Get the state queue for the robot
        state_queue = None
        if index == 1:
            state_queue = self._robot_queue_a
        elif index == 2:
            state_queue = self._robot_queue_b

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

                if state_current == _RobotState.home:
                    if state_next == _RobotState.waypoint:
                        # GOTO waypoint -> home
                        state_final = state_next

                        # Drive from the charger to the waypoint
                        await self._do_drive_from_charger_to_waypoint(index, robot)

                # If the state did not change
                if state_final == state_current:
                    print(f'Failed to transition from state "{state_current.name}" to state "{state_next.name}"')

                # Update the current state
                if index == 1:
                    self._robot_state_a = state_final
                elif index == 2:
                    self._robot_state_b = state_final

        print(f'Driver for robot {letter} has stopped')

    async def _do_drive_from_charger_to_waypoint(self, index: int, robot: cozmo.robot.Robot):
        """
        Action for driving from charger to waypoint.

        :param index: The robot index
        :param robot: The robot instance
        """

        # Convert robot index to robot letter
        letter = 'A' if index == 1 else 'B'

        print(f'Robot {letter} is departing from charger and heading to waypoint')

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

        print(f'Robot {letter} is departing from waypoint and heading to charger')

        # TODO: Add charger return code

    async def _choreographer(self):
        """
        The choreographer gives high-level commands to one or two robots.
        """

        print('Choreographer has started')

        while not self._stopping:
            # TODO

            # Yield control
            await asyncio.sleep(0)

        print('Choreographer has stopped')

    def _manual_advance(self, index: int):
        """
        Manually advance the given robot.

        This drives the robot from its charger to its waypoint.

        Thread-safe and non-blocking.

        :param index: The robot index
        """

        # Get the state queue for the robot
        state_queue = None
        if index == 1:
            state_queue = self._robot_queue_a
        elif index == 2:
            state_queue = self._robot_queue_b

        # Drive from the charger to the waypoint
        if state_queue is not None:
            state_queue.put(_RobotAction.drive_from_charger_to_waypoint)


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

    def do_advance(self, args):
        """Drive the selected Cozmo from its charger to its waypoint."""

        # Require a robot to be selected
        if self._selected_robot is None:
            print('No robot selected')
            return

        print('Advancing selected robot from charger')

        # Go to waypoint state
        self._get_robot_state_queue().put(_RobotState.waypoint)

    def do_return(self, args):
        """Drive the selected Cozmo from its waypoint to its charger."""

        # Require a robot to be selected
        if self._selected_robot is None:
            print('No robot selected')
            return

        print('Returning selected robot to charger')

        # Go to home state
        self._get_robot_state_queue().put(_RobotState.home)

    def do_converse(self, args):
        """Start conversation activity."""
        raise NotImplementedError

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
