"""
Copyright Kinvert All Rights Reserved
If you would like to use this code for
business or education please contact
us for permission at:
www.kinvert.com/
Free for personal use
"""

import cozmo
from cozmo.util import degrees
import random
import sys
import time

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("Cannot import from PIL. Do `pip3 install --user Pillow` to install")


def npc_cozmo(bx, by, bvx, bvy):
    return by + random.randint(-5, 5)


def draw_face(x, y, bx, by, px, py, vx, vy):
    dimensions = (128, 64)
    face_image = Image.new(
        'RGBA', dimensions, (0, 0, 0, 255))
    dc = ImageDraw.Draw(face_image)
    dc.ellipse([bx - 5, by - 5, bx + 5, by + 5], fill=(255, 255, 255, 255))
    dc.rectangle([px - 3, py - 10, px, py + 10], fill=(255, 255, 255, 255))
    dc.rectangle([vx + 3, vy - 10, vx, vy + 10], fill=(255, 255, 255, 255))
    return face_image


def impact(bx, by, bvx, bvy, paddleY, robot):
    if abs(paddleY - by) < 10:
        robot.play_audio(cozmo.audio.AudioEvents.SfxGameWin)
        cozmo.audio.AudioEvents.MusicCubeWhack
        bvx = bvx * -1
        bvy += (0.5 * (by - paddleY))
        if abs(bvy) < 0.2:
           bvy = 0.5
        bvx = bvx * 1.1
    return bvx, bvy


def kinvert_pong(robot: cozmo.robot.Robot):
    robot.set_head_angle(degrees(45)).wait_for_completed()

    over = 0
    bx = 90
    by = 40
    bvx = -2
    bvy = -1
    px = 5
    vx = 123

    #robot.say_text("I'm bored, I will play some pong").wait_for_completed()
    while not over:
        #py = 65 - robot.pose_pitch.degrees * 2
        py = npc_cozmo(bx, by, bvx, bvy)
        vy = npc_cozmo(bx, by, bvx, bvy)
        if by <= 2: bvy = bvy * -1
        if by > 61:
            bvy = bvy * -1
        if bx <= px and bx >= 0:
            bvx, bvy = impact(bx, by, bvx, bvy, py, robot)
        if bx >= vx and bx <= 128:
            bvx, bvy = impact(bx, by, bvx, bvy, vy, robot)
        bx += bvx
        by += bvy
        if bx < 0:
            time.sleep(0.5)
            robot.say_text("I win").wait_for_completed()
            robot.play_anim_trigger(cozmo.anim.Triggers.CodeLabWin).wait_for_completed()
            over = 1
        elif bx > 130:
            time.sleep(0.5)
            robot.say_text("I win").wait_for_completed()
            robot.play_anim_trigger(cozmo.anim.Triggers.CodeLabWin).wait_for_completed()
            over = 1

        face_image = draw_face(0, 0, bx, by, px, py, vx, vy)
        screen_data = cozmo.oled_face.convert_image_to_screen_data(face_image)
        robot.display_oled_face_image(screen_data, 0.1)
        if bvx < 0:
            time.sleep(0.1)
        else:
            time.sleep(0.01)


cozmo.run_program(kinvert_pong)