import cozmo
import time
from cozmo.util import degrees, distance_mm, speed_mmps


def test(robot: cozmo.robot.Robot):

    waypoint = robot.pose
    robot.start_freeplay_behaviors()
    time.sleep(60)
    robot.stop_freeplay_behaviors()
    time.sleep(5)
    robot.go_to_pose(waypoint).wait_for_completed()

    
cozmo.run_program(test)

