#!/usr/bin/python3
#
# Move/Tap servo arms according to the color of the image target.

import cv2
import RPi.GPIO as GPIO
import pigpio # Less servo jitter. Need pigpiod running.
import time

# Servos and Arm positions.
RED   = 24 # GPIO pin.
WHITE = 22 # GPIO pin.
BLUE  = 17 # GPIO pin.
GREY  = 23 # GPIO pin but not connected.  We assume the 4th color meaning none of the above.
gpins = [RED, WHITE, BLUE, GREY]

class Color:
    @classmethod
    def text(cls, c):
        if c == RED:
            return "RED  "
        if c == WHITE:
            return "WHITE"
        if c == BLUE:
            return "BLUE "
        if c == GREY:
            return "GREY "

frame_height = 480
frame_width = 640

class Pixel:
    move = 1 # Number of pixel to move in the moveXX() functions.
    color_differential = 32 # Differential of RGB values to call a specific color.
    color_threshold = 48 # Minimum RGB value to identify a color.
    def __init__(self, y=0, x=0):
        self.y = y
        self.x = x
    def __repr__(self):
        return f'Pixel({self.y},{self.x})'
    def moveUp(self):
        self.y -= Pixel.move
        if self.y < 0:
            self.y = 0
    def moveLeft(self):
        self.x -= Pixel.move
        if self.x < 0:
            self.x = 0
    def moveDown(self):
        self.y += Pixel.move
        if self.y >= frame_height:
            self.y = frame_height-1
    def moveRight(self):
        self.x += Pixel.move
        if self.x >= frame_width:
            self.x = frame_width-1
    def drawCrossHair(self, frame, radius=10):
        """Draw the cross-hair on the frame."""
        for _y in range(self.y-radius, self.y+radius+1):
            if _y != self.y:
                frame[_y][self.x] = Pixel.flipColor(frame[_y][self.x])
        for _x in range(self.x-radius, self.x+radius+1):
            if _x != self.x:
                frame[self.y][_x] = Pixel.flipColor(frame[self.y][_x])
    def getColor(self, frame):
        """Get the color code of this target from the frame."""
        b, g, r = ( frame[self.y][self.x] )
        # Our scheme to determine the color at the target.
        if r > g+Pixel.color_differential and r > b+Pixel.color_differential:
            return RED
        elif b > r+Pixel.color_differential and b > g+Pixel.color_differential:
            return BLUE
        elif r > Pixel.color_threshold and b > Pixel.color_threshold and g > Pixel.color_threshold:
            return WHITE
        else:
            return GREY
    @classmethod
    def flipColor(cls, pixel):
        b, g, r = ( pixel )
        return (255-b, 255-g, 255-r)

#target = [Pixel(280,402), Pixel(278,370), Pixel(278,335), Pixel(275,303), Pixel(273,270), Pixel(271,240), Pixel(268,205), Pixel(265,189)]
target = [Pixel(273,408), Pixel(271,376), Pixel(271,341), Pixel(271,309), Pixel(271,276), Pixel(272,246), Pixel(273,220)]
        
class Servo:
    def __init__(self, gpin, angle=45.0):
        global pwm
        self.gpin = gpin
        self.angleUp = angle # degrees.
        self.angleDisplacement = 9 # degrees. #<--- TUNE THIS
        self.tapDuration = 0.07 # seconds. #<--- TUNE THIS
        self.postTapDuration = 0.15 # seconds #<--- TUNE THIS
        pwm.set_mode(self.gpin, pigpio.OUTPUT)
        pwm.set_PWM_frequency(self.gpin, 50)  # My servo operates at 50Hz.
        pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp)) # Move arm to the ready position.
    def __del__(self):
        global pwm
        pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(90.0)) # Raise arm all the way up for maintenance.
        time.sleep(self.tapDuration)
        pwm.set_PWM_dutycycle(self.gpin, 0)
        pwm.set_PWM_frequency(self.gpin, 0)
    def __repr__(self):
        return f'servo[{Color.text(self.gpin)}] = Servo({Color.text(self.gpin)}, {self.angleUp}) # tapDur={self.tapDuration}s,{self.postTapDuration}s'
    def tap(self):
        global pwm
        pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp-self.angleDisplacement)) # Lower arm.
        time.sleep(self.tapDuration) # Wait slightly for the arm to tap.
        pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp)) # Raise arm.
        time.sleep(self.postTapDuration) # Wait slightly for the arm to return.
    def tuneAngle(self, change=1):        
        self.angleUp += change
        if self.angleUp < 12.0:
            self.angleUp = 12.0
        elif self.angleUp > 178.0:
            self.angleUp = 178.0     
        pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp)) # Raise arm to new position
    
    @classmethod
    def translateDegree(cls, deg):
        """ Pulse width 500 is 0 deg; 2500 is 180 deg. """
        if deg < 0.0:
            deg = 0.0
        elif deg > 180.0:
            deg = 180.0
        return deg*2000.0/180.0 + 500.0

servo = {}

def init():
    # Initialize Servos.
    global pwm
    global cap
    global target
    global servo
    pwm = pigpio.pi()
    servo[RED  ] = Servo(RED  , 12.0) # tapDur=0.08s,0.17s
    servo[WHITE] = Servo(WHITE, 41.0) # tapDur=0.08s,0.17s
    servo[BLUE ] = Servo(BLUE , 13.0) # tapDur=0.08s,0.17s
    servo[GREY ] = Servo(GREY , 45.0) # tapDur=0.08s,0.17s
    
    cap = cv2.VideoCapture(0)  # The image is from the video device.
    cap.set( cv2.CAP_PROP_FRAME_WIDTH, frame_width )
    cap.set( cv2.CAP_PROP_FRAME_HEIGHT, frame_height )
    #cap.set( cv2.CAP_PROP_FPS, 15 )
    
def cleanup():
    global cap
    global pwm
    global servo
    # Clean up.
    for gpin in gpins:
        print(repr(servo[gpin]))
        del servo[gpin]
    for tgt in target:
        print(repr(tgt), end=', ')
    print('')
    cap.release()
    cv2.destroyAllWindows()
    
def printButtons(buttons):
    ti = time.time()
    print(ti, end=' ')
    for k in buttons:
        print(Color.text(k), end=' ')
    print('')
    return ti

def main():
    global servo
    
    safetyOn = True
    targetMovable = 0
    servoInFocus = GREY
    oldButtons = []
    newButtons = []
    
    init()
    
    while True:
        ret, frame = cap.read() # Capture 1 frame from image input.
        if not ret:
            break

        # Display the image for a little while and handle keyboard.
        if safetyOn:
            for tgt in target:
                tgt.drawCrossHair(frame)
        cv2.imshow('live video', frame)
        key = cv2.waitKey(1) #<----- update

        # Quit.
        if (key==ord('q')):
            print('Quit')
            break
        
        # Flip the safety on/off.
        elif (key==ord('s')):
            safetyOn = not safetyOn
            if safetyOn:
                print('Safety ON')
            else:
                print('Safety OFF')
            
        
        # Cycle through targets.
        elif (key==ord('n')):
            targetMovable += 1
            if targetMovable >= len(target):
                targetMovable = 0
                
        # Move target.
        elif (key==ord('i')):
            for idx in range(targetMovable, len(target)):
                target[idx].moveUp()
            print(repr(target[targetMovable]))
        elif (key==ord('j')):
            for idx in range(targetMovable, len(target)):
                target[idx].moveLeft()
            print(repr(target[targetMovable]))
        elif (key==ord('k')):
            for idx in range(targetMovable, len(target)):
                target[idx].moveDown()
            print(repr(target[targetMovable]))
        elif (key==ord('l')):
            for idx in range(targetMovable, len(target)):
                target[idx].moveRight()
            print(repr(target[targetMovable]))
                
        # Test arms.
        elif (key==ord('1')):
            servoInFocus = WHITE
            servo[servoInFocus].tap()
            print(repr(servo[servoInFocus]))
        elif (key==ord('2')):
            servoInFocus = RED
            servo[servoInFocus].tap()
            print(repr(servo[servoInFocus]))
        elif (key==ord('3')):
            servoInFocus = BLUE
            servo[servoInFocus].tap()
            print(repr(servo[servoInFocus]))
            
        # Fine-tune arm height.
        elif (key==ord('+') or key==ord('=')):
            servo[servoInFocus].tuneAngle(1.0)
            print(repr(servo[servoInFocus]))
        elif (key==ord('-') or key==ord('_')):
            servo[servoInFocus].tuneAngle(-1.0)
            print(repr(servo[servoInFocus]))
            
        # Run servo tests.
        elif (key==ord('?')):
            for k in [WHITE, RED, BLUE]:
                for i in range(0, len(target)):
                    servo[k].tap()
            for i in range(0, len(target)):
                servo[WHITE].tap()
                servo[RED].tap()
                servo[BLUE].tap()


        # Load the color code into newButtons.
        newButtons = []
        for tgt in target:
            k = tgt.getColor(frame)
            newButtons.append(k)
            
        if (key==ord('p')):
            printButtons(newButtons)
        
        # Discard and try again if GREY is detected.
        if GREY in newButtons:
            continue

        # Main dish here.
        if not safetyOn:
            if not oldButtons == newButtons:
                #printButtons(newButtons)
                #cv2.imwrite(f'{ti}.jpg', frame)
                # Safety Off ... Fire !!!!!!!!
                for k in newButtons:
                    servo[k].tap()
                oldButtons = newButtons
                time.sleep(0.20)
    #endwhile

    cleanup()

if __name__ == "__main__":
    main()