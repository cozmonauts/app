#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

import cozmo


async def my_program(robot):
    await robot.say_text('my rahfulcopter goes soysoysoysoysoysoy').wait_for_completed()


if __name__ == '__main__':
    cozmo.robot.Robot.drive_off_charger_on_connect = False
    cozmo.run_program(my_program, use_viewer=True)
