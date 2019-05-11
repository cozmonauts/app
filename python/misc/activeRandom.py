#This function will have cozmo do random things while cozmo is undocked from charger

import random
import pong
import cozmo
from cozmo.util import degrees, distance_mm, speed_mmps


def doSomething():

    #this limits the function to only work a few times a day
    randomEvent = random.randint(1,10000) #chooses an event

    #will access cozmo's behavior class to perform random activities while idle
    if randomEvent == 1:
        robot.start_freeplay_behaviors()
        time.sleep(120)
        robot.stop_freeplay_behaviors()
        time.sleep(2)
        robot.play_anim_trigger(cozmo.anim.Triggers.DriveEndHappy).wait_for_completed()
        time.pause(2)
        robot.go_to_pose(my_waypoint).wait_for_completed()

    #starts a random conversation using startConver function
    elif randomEvent == 2:
        robot.drive_straight(distance_mm(200), speed_mmps(50)).wait_for_completed()
        robot.turn_in_place(degrees(180)).wait_for_completed()
        startConver()
        robot.go_to_pose(my_waypoint).wait_for_completed()

    #Plays the pong function
    elif randomEvent == 3:
        robot.run_program(kinvert_pong).wait_for_completed()
        robot.go_to_pose(my_waypoint).wait_for_completed()

#cozmo.run_program(doSomething)
