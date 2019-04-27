import cozmo
from cozmo.util import degrees, radians, distance_mm, speed_mmps
#from cozmo.objects import LightCube1Id, LightCube2Id, LightCube3Id

#import asyncio
import time
import math
#from . import util

# Choose on which side of the charger (when facing it), Cozmo should put its cubes.
# SIDE = 1 (left), SIDE = -1 (right)
#SIDE = -1

# Pitch value when head is horizonal, calculated later.
pitch_threshold = 0

retries = 5

########################## Animations ##########################

def play_animation(robot: cozmo.robot.Robot, anim_trig, body = False, lift = False, parallel = False):
    # anim_trig = cozmo.anim.Triggers."Name of trigger" (this is an object)
    # Refer to "http://cozmosdk.anki.com/docs/generated/cozmo.anim.html#cozmo.anim.Triggers" for animations' triggers
    # Refer to "http://cozmosdk.anki.com/docs/generated/cozmo.robot.html#cozmo.robot.Robot.play_anim_trigger" for playing the animation

    robot.play_anim_trigger(anim_trig,loop_count = 1, in_parallel = parallel,
                            num_retries = 0, use_lift_safe = False,
                            ignore_body_track = body, ignore_head_track=False,
                            ignore_lift_track = lift).wait_for_completed()

def frustrated(robot: cozmo.robot.Robot):
    trigger = cozmo.anim.Triggers.FrustratedByFailureMajor  
    play_animation(robot,trigger)

def celebrate(robot: cozmo.robot.Robot):
    trigger = cozmo.anim.Triggers.CodeLabCelebrate  
    play_animation(robot,trigger,body=True,lift=True,parallel=True)


def find_charger():
    global robot

    while(True):
        
        behavior = robot.start_behavior(cozmo.behavior.BehaviorTypes.LookAroundInPlace) # start_behavior() is acozmo function
        try: 
            seen_charger = robot.world.wait_for_observed_charger(timeout=10,include_existing=True)
        except:
            seen_charger = None
        behavior.stop()
        if(seen_charger != None):
            #print(seen_charger)
            return seen_charger
        frustrated(robot)
        robot.say_text('Charge?',duration_scalar=0.5).wait_for_completed()
    return None

def go_to_charger():
    # Driving towards charger without much precision
    global robot

    charger = None
    ''' cf. 08_drive_to_charger_test.py '''
    # see if Cozmo already knows where the charger is
    if robot.world.charger:
        # make sure Cozmo was not delocalised after observing the charger
        if robot.world.charger.pose.is_comparable(robot.pose):
            print("Cozmo already knows where the charger is!")
            charger = robot.world.charger
        else:
            # Cozmo knows about the charger, but the pose is not based on the
            # same origin as the robot (e.g. the robot was moved since seeing
            # the charger) so try to look for the charger first
            pass
    if not charger:
        charger = find_charger()
    
    action = robot.go_to_object(charger,distance_from_object=distance_mm(80), in_parallel=False, num_retries=5)
    action.wait_for_completed()
    return charger

def disp_coord(charger: cozmo.objects.Charger):
    # Debugging function used to diplay coordinates of objects
    # (Not currently used)
    global robot

    r_coord = robot.pose.position #.x .y .z, .rotation otherwise
    r_zRot = robot.pose_angle.degrees # or .radians
    c_coord = charger.pose.position
    c_zRot = charger.pose.rotation.angle_z.degrees

    print('Recorded coordinates of the robot and charger:')
    print('Robot:',end=' ')
    print(r_coord)
    print(r_zRot)
    print('Charger:',end=' ')
    print(c_coord)
    print(c_zRot)
    print('\n')

PI = 3.14159265359
def clip_angle(angle=3.1415):
	# Allow Cozmo to turn the least possible. Without it, Cozmo could
	# spin on itself several times or turn for instance -350 degrees
	# instead of 10 degrees. 
    global PI

    # Retreive supplementary turns (in radians)
    while(angle >= 2*PI):
        angle -= 2*PI
    while(angle <= -2*PI):
        angle += 2*PI
    # Select shortest rotation to reach the target
    if(angle > PI):
    	angle -= 2*PI
    elif(angle < -PI):
    	angle += 2*PI
    return angle

def check_tol(charger: cozmo.objects.Charger,dist_charger=40):
    # Check if the position tolerance in front of the charger is respected
    global robot,PI

    distance_tol = 5 # mm, tolerance for placement error
    angle_tol = 5*PI/180 # rad, tolerance for orientation error

    try: 
        charger = robot.world.wait_for_observed_charger(timeout=2,include_existing=True)
    except:
        print('WARNING: Cannot see the charger to verify the position.')

    # Calculate positions
    r_coord = [0,0,0]
    c_coord = [0,0,0]
    # Coordonates of robot and charger
    r_coord[0] = robot.pose.position.x #.x .y .z, .rotation otherwise
    r_coord[1] = robot.pose.position.y
    r_coord[2] = robot.pose.position.z
    r_zRot = robot.pose_angle.radians # .degrees or .radians
    c_coord[0] = charger.pose.position.x
    c_coord[1] = charger.pose.position.y
    c_coord[2] = charger.pose.position.z
    c_zRot = charger.pose.rotation.angle_z.radians

    # Create target position 
    # dist_charger in mm, distance if front of charger
    c_coord[0] -=  dist_charger*math.cos(c_zRot)
    c_coord[1] -=  dist_charger*math.sin(c_zRot)

    # Direction and distance to target position (in front of charger)
    distance = math.sqrt((c_coord[0]-r_coord[0])**2 + (c_coord[1]-r_coord[1])**2 + (c_coord[2]-r_coord[2])**2)

    if(distance < distance_tol and math.fabs(r_zRot-c_zRot) < angle_tol):
    	return 1
    else: 
    	return 0

def final_adjust(charger: cozmo.objects.Charger,dist_charger=40,speed=40,critical=False):
    # Final adjustement to properly face the charger.
    # The position can be adjusted several times if 
    # the precision is critical, i.e. when climbing
    # back onto the charger.  
    global robot,PI

    while(True):
        # Calculate positions
	    r_coord = [0,0,0]
	    c_coord = [0,0,0]
	    # Coordonates of robot and charger
	    r_coord[0] = robot.pose.position.x #.x .y .z, .rotation otherwise
	    r_coord[1] = robot.pose.position.y
	    r_coord[2] = robot.pose.position.z
	    r_zRot = robot.pose_angle.radians # .degrees or .radians
	    c_coord[0] = charger.pose.position.x
	    c_coord[1] = charger.pose.position.y
	    c_coord[2] = charger.pose.position.z
	    c_zRot = charger.pose.rotation.angle_z.radians

	    # Create target position 
	    # dist_charger in mm, distance if front of charger
	    c_coord[0] -=  dist_charger*math.cos(c_zRot)
	    c_coord[1] -=  dist_charger*math.sin(c_zRot)

	    # Direction and distance to target position (in front of charger)
	    distance = math.sqrt((c_coord[0]-r_coord[0])**2 + (c_coord[1]-r_coord[1])**2 + (c_coord[2]-r_coord[2])**2)
	    vect = [c_coord[0]-r_coord[0],c_coord[1]-r_coord[1],c_coord[2]-r_coord[2]]
	    # Angle of vector going from robot's origin to target's position
	    theta_t = math.atan2(vect[1],vect[0])

	    print('CHECK: Adjusting position')
	    # Face the target position
	    angle = clip_angle((theta_t-r_zRot))
	    robot.turn_in_place(radians(angle)).wait_for_completed()
	    # Drive toward the target position
	    robot.drive_straight(distance_mm(distance),speed_mmps(speed)).wait_for_completed()
	    # Face the charger
	    angle = clip_angle((c_zRot-theta_t))
	    robot.turn_in_place(radians(angle)).wait_for_completed()

        # In case the robot does not need to climb onto the charger
	    if not critical:
	        break
	    elif(check_tol(charger,dist_charger)):
	    	print('CHECK: Robot aligned relativ to the charger.')
	    	break
    return

def restart_procedure(charger: cozmo.objects.Charger):
    global robot

    robot.stop_all_motors()
    robot.set_lift_height(height=0.5,max_speed=10,in_parallel=True).wait_for_completed()
    robot.pose.invalidate()
    charger.pose.invalidate()
    print('ABORT: Driving away')
    #robot.drive_straight(distance_mm(150),speed_mmps(80),in_parallel=False).wait_for_completed()
    robot.drive_wheels(80,80,duration=2)
    turn_around()
    robot.set_lift_height(height=0,max_speed=10,in_parallel=True).wait_for_completed()
    # Restart procedure
    get_on_charger()
    return

def get_on_charger():
    global robot,pitch_threshold

    robot.set_head_angle(degrees(0),in_parallel=False).wait_for_completed()
    pitch_threshold = math.fabs(robot.pose_pitch.degrees)
    pitch_threshold += 1 # Add 1 degree to threshold
    print('Pitch threshold: ' + str(pitch_threshold))

    # Drive towards charger
    go_to_charger()

    # Let Cozmo first look for the charger once again. The coordinates
    # tend to be too unprecise if an old coordinate system is kept.
    if robot.world.charger is not None and robot.world.charger.pose.is_comparable(robot.pose):
        robot.world.charger.pose.invalidate()
    charger = find_charger()

    # Adjust position in front of the charger
    final_adjust(charger,critical=True)
    
    # Turn around and start going backward
    turn_around()
    robot.drive_wheel_motors(-120,-120)
    robot.set_lift_height(height=0.5,max_speed=10,in_parallel=True).wait_for_completed()
    robot.set_head_angle(degrees(0),in_parallel=True).wait_for_completed()

    # This section allow to wait for Cozmo to arrive on its charger
    # and detect eventual errors. The whole procedure will be restarted
    # in case something goes wrong.
    timeout = 1 # seconds before timeout
    t = 0
    # Wait for back wheels to climb on charger
    while(True):
        time.sleep(.1)
        t += 0.1
        if(t >= timeout):
            print('ERROR: robot timed out before climbing on charger.')
            restart_procedure(charger)
            return
        elif(math.fabs(robot.pose_pitch.degrees) >= pitch_threshold):
            print('CHECK: backwheels on charger.')
            break
    # Wait for front wheels to climb on charger
    timeout = 2
    t = 0
    while(True):
        time.sleep(.1)
        t += 0.1
        if(math.fabs(robot.pose_pitch.degrees) > 20 or t >= timeout):
            # The robot is climbing on charger's wall -> restart
            print('ERROR: robot climbed on charger\'s wall or timed out.')
            restart_procedure(charger)
            return
        elif(math.fabs(robot.pose_pitch.degrees) < pitch_threshold):
            print('CHECK: robot on charger, backing up on pins.')
            robot.stop_all_motors()
            break

    # Final backup onto charger's contacts
    robot.set_lift_height(height=0,max_speed=10,in_parallel=True).wait_for_completed()
    robot.backup_onto_charger(max_drive_time=3)
    if(robot.is_on_charger):
    	print('PROCEDURE SUCCEEDED')
    else: 
    	restart_procedure(charger)
    	return

    # Celebrate success
    robot.drive_off_charger_contacts().wait_for_completed()
    celebrate(robot) # A small celebration where only the head moves
    robot.backup_onto_charger(max_drive_time=3)
    return

########################## Battery related code ##########################

def check_battery():
	global robot

	if(robot.battery_voltage < 3.5):
		print('Battery is low, directly docking to charger without cleaning up.')
		return 1
	else:
		return 0

########################## General code ##########################

def turn_around():
    global robot
    robot.turn_in_place(degrees(-180)).wait_for_completed()
    return

########################## Main ##########################

robot = None

def init_robot(cozmo_robot: cozmo.robot.Robot):
    global robot
    robot = cozmo_robot

def execute_procedure():
    low_battery = check_battery()
    if not low_battery:
        get_on_charger()#clean_up_cubes() #search for faces!!!!
    get_on_charger()
    return

def cozmo_program(cozmo_robot: cozmo.robot.Robot):
    global robot
    init_robot(cozmo_robot)

    # Get off charger if on it
    if(robot.is_on_charger):
    	robot.drive_off_charger_contacts().wait_for_completed()
    	robot.drive_straight(distance_mm(110),speed_mmps(80)).wait_for_completed()

    execute_procedure()
    return

if __name__ == "__main__":
    cozmo.robot.Robot.drive_off_charger_on_connect = False
    cozmo.run_program(cozmo_program,use_viewer=True,use_3d_viewer=False)