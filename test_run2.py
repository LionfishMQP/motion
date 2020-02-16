from pymavlink import mavutil
from multiprocessing import Process, Queue
import time
from sys import exit
import serial
import signal
import random
import math

# Pwm channel pins
# 0 - pitch
# 1 - roll
# 2 - up
# 3 - yaw
# 4 - forward
# 5 - lateral
# 6 - camera pan
# 7 - camera tilt
# 8 - lights 1 level

TURN_BUFFER = 2
PING_FORWARD_STOP = 2000
PING_EXPIRE_TIME = 3 # seconds
PING_CONF = 60

startMarker = 60
endMarker = 62

def handler(signum, frame):
    print('Handle Ctrl-C')
    handle_exit()
    exit()

def handle_exit():
    print("Exiting")
    exit()
    

def run(master, qFromArduino, qToArduino):
    main_loop_queue = Queue()
    main_loop_process = Process(target=main_loop, args=(master, main_loop_queue, qFromArduino, qToArduino,))
    #main_loop_process.daemon = True
    main_loop_process.start()

    cont_run = True
    while cont_run:
        command = input("Command: ")
        main_loop_queue.put(command)
        
        commands = command.split()
        verb = lookup_button(commands[0])
        if verb == -2:
            handle_exit()
        time.sleep(1)


def main_loop(master, main_loop_queue, qFromArduino, qToArduino):

    cmd_queue = Queue()

    forward_ping = -100
    forward_ping_time = 0
    forward_ping_conf = 0
    down_ping = -100
    down_ping_time = 0
    down_ping_conf = 0
    ping1, ping1_conf, ping2, ping2_conf = update_sensors(qFromArduino)

    if check_lifeSupport(qFromArduino):
        pass
        #kill processes and go to surface
    
    if ping1 != -100:
        forward_ping = ping1
        forward_ping_conf = ping1_conf
        forward_ping_time = time.time()
        # sensor 0, data, time taken
        cmd_queue.put((0, forward_ping, forward_ping_time, ping1_conf))
    if ping2 != -100:
        down_ping = ping2
        down_ping_conf = ping2_conf
        down_ping_time = time.time()
        # sensor 0, data, time taken
        cmd_queue.put((1, down_ping, down_ping_time, ping2_conf))

    cont_run = True
    while cont_run:
        try:

            if not main_loop_queue.empty():
                command = main_loop_queue.get()
                print("Given command: " + command + "\n")
                commands = command.split()
                verb = lookup_button(commands[0])
                if verb == -2:
                    handle_exit()

                if verb == 101:
                    if commands[1] == '1':
                        print("forward ping: " + str(forward_ping) + " mm,   conf: " + str(forward_ping_conf))
                        print("forward ping: " + str((forward_ping/25.4)) + " inches,   conf: " + str(forward_ping_conf))
                    elif commands[1] == '2':
                        print("down ping: " + str(down_ping) + " mm,   conf: " + str(down_ping_conf))
                        print("forward ping: " + str((down_ping / 25.4)) + " inches,   conf: " + str(down_ping_conf))
                
                if verb != -1:
                    motor_cmd_process = Process(target=motor_cmd, args=(master, verb, commands, cmd_queue))
                    motor_cmd_process.daemon = True
                    motor_cmd_process.start()
                else:
                    print("Unknown command, list of available commands: \n")
                    print_cmd_list()
                    print("")

            # update sensors
            ping1, ping1_conf, ping2, ping2_conf = update_sensors(qFromArduino)
            if ping1 != -100:
                forward_ping = ping1
                forward_ping_conf = ping1_conf
                cmd_queue.put((0, forward_ping, forward_ping_time, ping1_conf))
            if ping2 != -100:
                down_ping = ping2
                down_ping_conf = ping2_conf
                cmd_queue.put((1, down_ping, down_ping_time, ping2_conf))

            if check_lifeSupport(qFromArduino):
                pass
                #kill processes and go to surface

        except Exception as e:
            print("Incorrect command: " + str(e))
            exit()

def update_sensors(q):

    ping1_val = -100
    ping1_conf = 0
    ping2_val = -100
    ping2_conf = 0
    if not q.empty():
        val = q.get()
        if val[0] == 1:
            ping1_val = val[1]
            ping1_conf = val[2]
        elif val[0] == 0:
            ping2_val = val[1]
            ping2_conf = val[2]

        for i in range(q.qsize()):
            val = q.get()
            if val[0] == 1:
                ping1_val = val[1]
                ping1_conf = val[2]
            elif val[0] == 0:
                ping2_val = val[1]
                ping2_conf = val[2]
    return ping1_val, ping1_conf, ping2_val, ping2_conf

def check_lifeSupport(q):
    battLow = False
    leakDetected = False

    if not q.empty():
        val = q.get()
        if val[0] == 2:
            if val[1] > 12.2:
                print("Low Battery: " + val[1])
            else:
                battLow = True
        elif val[0] == 3:
            leakDetected = True

        for i in range(q.qsize()):
            val = q.get()
            if val[0] == 2:
               battLow = True
            elif val[0] == 3:
               leakDetected = True
  
    return leakDetected or battLow

def lookup_button(string_in):
    if string_in == "depth":
        return 0
    elif string_in == "stab":
        return 1
    elif string_in == "man":
        return 2
    elif string_in == "disarm":
        return 4
    elif string_in == "arm":
        return 6
    elif string_in == "lights":
        return 9
    elif string_in == "hold":
        return 10
    elif string_in == "camdown":
        return 11
    elif string_in == "camup":
        return 12
    elif string_in == "yaw":
        return 13
    elif string_in == "forward":
        return 14
    elif string_in == "reverse":
        return 15
    elif string_in == "dive":
        return 16
    elif string_in == "square":
        return 17
    elif string_in == "bottomHold":
        return 18
    elif string_in == "roomba":
        return 19
    elif string_in == "xyzNav":
        return 20
    elif string_in == "hud":
        return 100
    elif string_in == "ping":
        return 101
    elif string_in == "quit":
        return -2
    elif string_in == "q":
        return -2
    else:
        return -1


def motor_cmd(master, verb, commands, cmd_queue):
    if verb < 13:
        button_press(master, verb)
    elif verb == 13:
        # turn to given angle
        val = int(commands[1])  # throttle
        rel_angle = float(commands[2])  # target angle
        turn_angle(master, val, rel_angle)
    elif verb == 14:
        # drive forward
        val = int(commands[1])
        time_to_drive = float(commands[2])
        drive_forward(master, val, time_to_drive)
    elif verb == 15:
        # drive backward
        val = int(commands[1])
        time_to_drive = float(commands[2])
        drive_backward(master, val, time_to_drive)
    elif verb == 16:
        # dive to given depth
        val = int(commands[1])
        target_depth = float(commands[2])
        depth(master, val, target_depth)
    elif verb == 17:
        # run square
        drive_forward(master, 50, 8)
        clear_motors(master)
        time.sleep(1)

        turn_angle(master, 15, 90)
        drive_forward(master, 50, 4)
        clear_motors(master)
        time.sleep(1)

        turn_angle(master, 15, 90)
        drive_forward(master, 50, 8)
        clear_motors(master)
        time.sleep(1)

        turn_angle(master, 15, 90)
        drive_forward(master, 50, 4)
        clear_motors(master)
        time.sleep(1)

        turn_angle(master, 15, 90)
    
    elif verb == 18:
        #bottom hold
        in_time = int(commands[1])
        throttle = int(commands[2])
        target_distance = float(commands[3])
        bottom_hold(master, in_time, throttle, target_distance, cmd_queue)
    
    elif verb == 19:
        # run roomba
        throttle = int(commands[1])
        time_to_run = int(commands[2])
        roomba(master, time_to_run, throttle, cmd_queue)
    
    elif verb == 20:
        #xyz Navigation
        in_time = int(commands[1])
        throttle = int(commands[2])
        x = int(commands[3])
        y = int(commands[4])
        z = int(commands[5])
        xyzNav(master, in_time, throttle, x, y, z)

    elif verb == 100:
        # print hud
        print(get_message(master))
    else:
        pass


def turn_angle(master, val, rel_angle):
    if val > 0 and val <= 100:
        output = (val * 5) + 1500
        if rel_angle < 0:
            output = (-val * 5) + 1500

        org_heading = float(get_message(master)['heading'])
        curr_heading = org_heading

        while continue_turn(org_heading, curr_heading, rel_angle):
            write_pwm(master, 3, output)
            curr_heading = float(get_message(master)['heading'])

    elif val == 0:
        write_pwm(master, 3, 0)


def drive_forward(master, val, time_to_drive):
    if val > 0 and val <= 100:
        output = (val * 5) + 1500
        end_time = time.time() + time_to_drive
        while time.time() < end_time:
            write_pwm(master, 4, output)


def drive_backward(master, val, time_to_drive):
    if val > 0 and val <= 100:
        output = (-val * 5) + 1500
        end_time = time.time() + time_to_drive
        while time.time() < end_time:
            write_pwm(master, 4, output)


def depth(master, val, target_depth):
    if val > 0 and val <= 100:
        curr_depth = float(get_message(master)['alt'])
        output = (val * 5) + 1500
        if (target_depth - curr_depth) < 0:
            output = (-val * 5) + 1500   
            
        while abs(target_depth - curr_depth) > 0.2:
            write_pwm(master, 2, output)
            curr_depth = float(get_message(master)['alt'])
    elif val == 0:
        write_pwm(master, 2, 0)

def bottom_hold(master, in_time, throttle, target_distance, cmd_queue):
    end_time = time.time() + in_time
    
    ping1_ret, ping1_time_ret, ping1_conf, ping2_ret, ping2_time_ret, ping2_conf = check_sensors(cmd_queue)
    ping2 = ping2_ret/1000    
    curr_depth = float(get_message(master)['alt'])

    while time.time() <= end_time:
        ping1_ret, ping1_time_ret, ping1_conf, ping2_ret, ping2_time_ret, ping2_conf = check_sensors(cmd_queue)
        ping2 = ping2_ret/1000    
        curr_depth = float(get_message(master)['alt'])

        if abs(ping2 - target_distance) > 0.2:
            if ping2 > target_distance: 
                desired_depth = curr_depth - ping2 + target_distance
            else:
                desired_depth = curr_depth + (target_distance - ping2)
                
            depth(master, throttle, desired_depth)

def roomba(master, in_time, throttle, cmd_queue):
    output = (throttle * 5) + 1500
    end_time = time.time() + in_time

    ping1_ret, ping1_time_ret, ping1_conf, ping2_ret, ping2_time_ret, ping2_conf = check_sensors(cmd_queue)
    ping1 = ping1_ret
    ping2 = ping2_ret


    while time.time() <= end_time:
        ping1, ping1_time, ping1_conf, ping2, ping2_time, ping2_conf = check_sensors(cmd_queue)
        if object_forward(ping1) and ping_conf(ping1_conf):
            write_pwm(master, 4, 1500)
            time.sleep(0.5)
            turn_angle(master, 15, 95)
        else:
            write_pwm(master, 4, output)

    clear_motors(master)

def xyzNav(master, in_time, throttle, relX, relY, relZ):
    end_time = time.time() + in_time

    relative_x = relX #only for testing
    relative_y = relY #
    relative_z = relZ #

    #relative_x, relative_y, relative_z = check_identification(cmd_queue)

    while time.time() <= end_time:
        #update relative data
        #relative_x, relative_y, relative_z = check_identification(cmd_queue)

        #dive to be on same z axis
        curr_depth = float(get_message(master)['alt'])
        depth_of_point = curr_depth + relative_z
        depth(master, 40, depth_of_point)

        #turn to have the point straight ahead
        tan_in_radians = math.tanh((relative_y/relative_x))
        angle_to_point = math.degrees(tan_in_radians)
        turn_angle(master, 15, angle_to_point)
        time.sleep(0.25)
        
        #move towards the point
        distance_to_point = (math.sqrt(relative_x*relative_x + relative_y*relative_y))/1000 #distance from mm to m
        if distance_to_point >= 8:
            closing_velocity = (50*5) + 1500
        elif distance_to_point >= 1 and distance_to_point < 8:
            closing_velocity = (distance_to_point * 3) + 1550 #16% @ 1m all the way to 60% at 8m
        else:
            closing_velocity = (15*5) + 1500

        write_pwm(master, 4, closing_velocity)
        time.sleep(0.5)
            

    clear_motors(master)

def check_identification(q):
    nav_x = -100
    nav_y = -100
    nav_z = -100
    if not q.empty():
        val = q.get()
        if val[0] == 2:
            nav_X = val[1]
            nav_y = val[2]
            nav_z = val[3]
        for i in range(q.qsize()):
            val = q.get()
            if val[0] == 2:
                nav_X = val[1]
                nav_y = val[2]
                nav_z = val[3]
    return nav_x, nav_y, nav_z

def check_sensors(q):

    ping1_val = -100
    ping1_time = 0
    ping1_conf = 0
    ping2_val = -100
    ping2_time = 0
    ping2_conf = 0
    if not q.empty():
        val = q.get()
        if val[0] == 0:
            ping1_val = val[1]
            ping1_time = val[2]
            ping1_conf = val[3]
        elif val[0] == 1:
            ping2_val = val[1]
            ping2_time = val[2]
            ping2_conf = val[3]

        for i in range(q.qsize()):
            val = q.get()
            if val[0] == 0:
                ping1_val = val[1]
                ping1_time = val[2]
                ping1_conf = val[3]
            elif val[0] == 1:
                ping2_val = val[1]
                ping2_time = val[2]
                ping2_conf = val[3]
    return ping1_val, ping1_time, ping1_conf, ping2_val, ping2_time, ping2_conf

def object_forward(ping):
    if (ping < PING_FORWARD_STOP) and ping != -100:
        return True
    else:
        return False

def ping_expire(ping_time):
    if (time.time() - ping_time) > PING_EXPIRE_TIME:
        return True
    else:
        return False

def ping_conf(conf):
    if conf > PING_CONF:
        return True
    else:
        return False

def button_press(master, verb):
    buttons = 1 << verb
    master.mav.manual_control_send(
        master.target_system,
        0,
        0,
        0,
        0,
        buttons)


def clear_motors(master):
    rc_channel_values = [0 for _ in range(8)]
    master.mav.rc_channels_override_send(
        master.target_system,  # target_system
        master.target_component,  # target_component
        *rc_channel_values)


def write_pwm(master, output_channel, output_val):
    rc_channel_values = [65535 for _ in range(8)]
    rc_channel_values[output_channel] = output_val
    master.mav.rc_channels_override_send(
        master.target_system,  # target_system
        master.target_component,  # target_component
        *rc_channel_values)


def continue_turn(org_heading, curr_heading, rel_angle):

    final_heading = org_heading + rel_angle
    if final_heading > 360:
        final_heading -= 360
    if final_heading < 0:
        final_heading += 360

    if (final_heading + TURN_BUFFER) > 360:
        if abs(final_heading - 360 - curr_heading) < TURN_BUFFER:
            return False
    if (final_heading - TURN_BUFFER) < 0:
        if abs(final_heading + 360 - curr_heading) < TURN_BUFFER:
            return False
    if abs(final_heading - curr_heading) < TURN_BUFFER:
        return False
    else:
        return True

def get_message(master):
    while True:
        msg = master.recv_match()
        if not msg:
            continue
        # print(msg.get_type())
        if msg.get_type() == 'VFR_HUD':
            # print("\n\n*****Got message: %s*****" % msg.get_type())
            # print("Message: %s" % msg)
            # print("\nAs dictionary: %s" % msg.to_dict())
            return msg.to_dict()


def print_cmd_list():
    print("arm - arm the motors")
    print("disarm - disarm the motors")
    print("depth - depth mode")
    print("stab - stabilize mode")
    print("man - manual mode")
    print("lights - toggle lights")
    print("hold - hold last sent command")
    print("camdown - move camera down")
    print("camup - move camera up")
    print("yaw <0-100% throttle> <relative degrees> - turn robot")
    print("forward <0-100% throttle> <time in seconds> - drive forward for x seconds")
    print("reverse <0-100% throttle> <time in seconds> - drive reverse for x seconds")
    print("dive <0-100% throttle> <target depth (m)> - dive to given depth")
    print("square - travel in a rectangle")
    print("roomba <0-100% throttle> <time in seconds> - execute roomba search pattern for a given time")
    print("xyzNav <time in seconds> <0-100% throttle> <Relative X> <Relative Y> <Relative Z>- Move to a relative XYZ position")
    print("bottomHold <time in seconds> <0-100% throttle> <Distance from bottom(M)>")
    print("hud - print out the hud data")
    print("ping <ID> - return ping data from given ID, start at 1")
    print("square - run a rectangle")
    print("q - quit the program")


# Arduino -------------------------------------------------------------------


def recv_from_arduino(ser):
    global startMarker, endMarker

    ck = ""
    x = "z"  # any value that is not an end- or startMarker
    byteCount = -1  # to allow for the fact that the last increment will be one too many

    # wait for the start character
    while ord(x) != startMarker:
        x = ser.read()

    # save data until the end marker is found
    while ord(x) != endMarker:
        if ord(x) != startMarker:
            ck = ck + x.decode("utf-8")
            byteCount += 1
        x = ser.read()

    return (ck)


def arduino_comms(qToArduino, qFromArduino):
    ser = serial.Serial("/dev/serial/by-path/platform-70090000.xusb-usb-0:2.3:1.0", 115200, timeout=0)

    while True:
        if ser.inWaiting() > 0:
            try:
                dataRecvd = recv_from_arduino(ser)
                #print("Reply Received  " + dataRecvd)
                process_arduino_data(dataRecvd, qFromArduino)
            except:
                # print("cannot read")
                pass


def process_arduino_data(message, qFromArduino):
    recvMessage = message.split()
    messType = int(recvMessage[1])
    messId = int(recvMessage[2])
    messData = int(recvMessage[3])
    confData = int(recvMessage[4])
    #print("Type: " + str(messType) + ", id: " + str(messId) + ", data: " + str(messData))
    if messType == 0:
        if messId == 1:
            qFromArduino.put((0, messData, confData))
        elif messId == 2:
            qFromArduino.put((1, messData, confData))
        # ping sensor update
        # qFromArduino # send received data to jetson
    elif messType == 1:
        pass
        # spear move update
    elif messType == 2:#BATTERY 
	if messId == 1:#VOLTAGE
            qFromArduino.put((2, messData, confData))
        elif messId == 2:#CURRENT
            qFromArduino.put((3, messData, confData))
    elif messType == 3:#leak
	print("**************SOS - LEAK DETECTED**************")
        qFromArduino.put((4, messData, confData))
	print("**************SOS - LEAK DETECTED**************")


# def actuate_spear(send_input):
#     if type(input) == 'int':
#         ser.write(("<" + str(send_input) + ">").encode('utf-8'))
#     else:
#         print("incorrect data type sent to spear")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, handler)
    qToArduino = Queue()
    qFromArduino = Queue()

    # Create the connection
    master = mavutil.mavlink_connection('udpin:0.0.0.0:15000')
    # Wait a heartbeat before sending commands
    master.wait_heartbeat()

    arduinoProcess = Process(target=arduino_comms, args=(qToArduino, qFromArduino,))
    arduinoProcess.daemon = True
    arduinoProcess.start()

    run(master, qFromArduino, qToArduino)
