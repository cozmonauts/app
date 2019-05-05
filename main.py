#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import asyncio

import cozmo


async def my_program(robot):
    await robot.say_text('my rahfulcopter goes soysoysoysoysoysoy').wait_for_completed()


async def _on_connect(conn: cozmo.conn.CozmoConnection):
    # Wait for the robot to be ready
    robot: cozmo.robot.Robot = await conn.wait_for_robot()

    # Make both talk simultaneously
    await my_program(robot)


def main():
    # Get the event loop
    loop = asyncio.get_event_loop()

    # Connect to two Cozmos
    conn1 = cozmo.connect_on_loop(loop)
    conn2 = cozmo.connect_on_loop(loop)

    # Create tasks for running the two Cozmos
    task1 = asyncio.ensure_future(_on_connect(conn1))
    task2 = asyncio.ensure_future(_on_connect(conn2))

    # Run the loop until both tasks complete
    loop.run_until_complete(asyncio.gather(task1, task2))


if __name__ == '__main__':
    cozmo.robot.Robot.drive_off_charger_on_connect = False
    main()
