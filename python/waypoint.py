import cozmo
from cozmo.util import distance_mm, speed_mmps


def drivefwd(robot: cozmo.robot.Robot):

    #robot.drive_straight((distance_mm(150), speed_mmps(50)).wait_for_completed(None))
    waypoint = robot.pose
    robot.drive_straight((distance_mm(150), speed_mmps(50)).wait_for_completed(None))
    robot.go_to_pose(waypoint).wait_for_completed()


cozmo.run_program(drivefwd)