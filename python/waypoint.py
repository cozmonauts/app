import cozmo
import chargerReturn
from cozmo.util import distance_mm, speed_mmps

def driveFWD(robot: cozmo.robot.Robot):
    robot.drive_straight(distance_mm(250), speed_mmps(50)).wait_for_completed()
   # waypoint = robot.pose
    #robot.drive_straight(distance_mm(150), speed_mmps(50)).wait_for_completed()
    #robot.go_to_pose(waypoint).wait_for_completed()
    chargerReturn.cozmo_program(robot)

cozmo.run_program(driveFWD)