#!/usr/bin/python3
#
# Move/Tap servo arms according to the color of the image target.

import cv2
import RPi.GPIO as GPIO
import pigpio # Less servo jitter. Need pigpiod running.
import time

# Servo colors.
RED   = 24 # GPIO pin.
WHITE = 22 # GPIO pin.
BLUE  = 17 # GPIO pin.
GREY  = 23 # GPIO pin but not connected.  We assume the 4th color meaning none of the above.
gpins = [RED, WHITE, BLUE, GREY]

# Webcam resolution.
frame_height = 480
frame_width = 640

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

class Pixel:
    move = 1 # Number of pixel to move targets.
    color_differential = 32 # Differential of RGB values to call a specific color.
    color_threshold = 0 # Minimum RGB value to identify a color.
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

class Servo:
    pwm = pigpio.pi()
    def __init__(self, gpin, angle=45.0):
        self.gpin = gpin
        self.angleUp = angle # degrees.
        self.angleDisplacement = 9 # degrees. #<--- TUNE THIS
        self.tapDuration = 0.05 # seconds. #<--- TUNE THIS
        self.postTapDuration = 0.11 # seconds #<--- TUNE THIS
        Servo.pwm.set_mode(self.gpin, pigpio.OUTPUT)
        Servo.pwm.set_PWM_frequency(self.gpin, 50)  # My servo operates at 50Hz.
        Servo.pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp)) # Move arm to the ready position.
    def __del__(self):
        Servo.pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(90.0)) # Raise arm all the way up for maintenance.
        time.sleep(self.tapDuration)
        Servo.pwm.set_PWM_dutycycle(self.gpin, 0)
        Servo.pwm.set_PWM_frequency(self.gpin, 0)
    def __repr__(self):
        return f'{Color.text(self.gpin)}: Servo({Color.text(self.gpin)}, {self.angleUp}),'
    def tap(self):
        Servo.pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp-self.angleDisplacement)) # Lower arm.
        time.sleep(self.tapDuration) # Wait slightly for the arm to tap.
        Servo.pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp)) # Raise arm.
        time.sleep(self.postTapDuration) # Wait slightly for the arm to return.
    def tuneAngle(self, change=1):
        self.angleUp += change
        if self.angleUp < 12.0:
            self.angleUp = 12.0
        elif self.angleUp > 178.0:
            self.angleUp = 178.0
        Servo.pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp)) # Raise arm to new position

    @classmethod
    def translateDegree(cls, deg):
        """ Pulse width 500 is 0 deg; 2500 is 180 deg. """
        if deg < 0.0:
            deg = 0.0
        elif deg > 180.0:
            deg = 180.0
        return deg*2000.0/180.0 + 500.0

class TapTapMachine:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __init__(self):
        # Initialize Servos.
        self.servo = {
            RED  : Servo(RED  , 14.0),
            WHITE: Servo(WHITE, 41.0),
            BLUE : Servo(BLUE , 18.0),
            GREY : Servo(GREY , 45.0),
            }
        # There are only 8 pixels in the frame. The last pixel tracks the GO! signal.
        self.target = [Pixel(297,444), Pixel(297,409), Pixel(297,374), Pixel(297,340), Pixel(297,305), Pixel(297,272), Pixel(300,239), Pixel(297,213), Pixel(207,361), ]
    def cleanup(self):
        # Report the servo and target settings in case the next run wants to know.
        for gpin in gpins:
            print(repr(self.servo[gpin]))
            del self.servo[gpin]
        print('self.target = [', end = '')
        for tgt in self.target:
            print(repr(tgt), end=', ')
        print(']')
    def printButtons(self, buttons):
        ti = time.time()
        print(ti, end=' ')
        for k in buttons:
            print(Color.text(k), end=' ')
        print('')
        return ti
    def run(self):
        safetyOn = True
        targetMovable = 0
        servoInFocus = GREY
        oldButtons = []
        newButtons = []
        while True:
            ret, frame = cap.read() # Capture 1 frame from image input.
            if not ret:
                break

            # Display the image for a little while and handle keyboard.
            if safetyOn:
                for tgt in self.target:
                    tgt.drawCrossHair(frame)
            cv2.imshow('live video', frame)
            key = cv2.waitKey(1)

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
                if targetMovable >= len(self.target):
                    targetMovable = 0

            # Move target.
            elif (key==ord('i')):
                for idx in range(targetMovable, len(self.target)):
                    self.target[idx].moveUp()
                print(repr(self.target[targetMovable]))
            elif (key==ord('j')):
                for idx in range(targetMovable, len(self.target)):
                    self.target[idx].moveLeft()
                print(repr(self.target[targetMovable]))
            elif (key==ord('k')):
                for idx in range(targetMovable, len(self.target)):
                    self.target[idx].moveDown()
                print(repr(self.target[targetMovable]))
            elif (key==ord('l')):
                for idx in range(targetMovable, len(self.target)):
                    self.target[idx].moveRight()
                print(repr(self.target[targetMovable]))

            # Test arms.
            elif (key==ord('1')):
                servoInFocus = WHITE
                self.servo[servoInFocus].tap()
                print(repr(self.servo[servoInFocus]))
            elif (key==ord('2')):
                servoInFocus = RED
                self.servo[servoInFocus].tap()
                print(repr(self.servo[servoInFocus]))
            elif (key==ord('3')):
                servoInFocus = BLUE
                self.servo[servoInFocus].tap()
                print(repr(self.servo[servoInFocus]))

            # Fine-tune arm height.
            elif (key==ord('+') or key==ord('=')):
                self.servo[servoInFocus].tuneAngle(1.0)
                print(repr(self.servo[servoInFocus]))
            elif (key==ord('-') or key==ord('_')):
                self.servo[servoInFocus].tuneAngle(-1.0)
                print(repr(self.servo[servoInFocus]))

            # Run servo tests.
            elif (key==ord('?')):
                for k in [WHITE, RED, BLUE]:
                    for i in range(0, len(self.target)):
                        self.servo[k].tap()
                for i in range(0, len(self.target)):
                    self.servo[WHITE].tap()
                    self.servo[RED].tap()
                    self.servo[BLUE].tap()


            # Load the color code from image into newButtons.
            newButtons = []
            for tgt in self.target:
                k = tgt.getColor(frame)
                newButtons.append(k)

            # Discard and try again if GREY is detected.
            if GREY in newButtons:
                continue

            if (key==ord('p')):
                self.printButtons(newButtons)
            
            # Sometimes I started too soon before the GO! signal. This prevents using that frame.
            kGo = self.target[-1].getColor(frame)
            if kGo == WHITE:
                continue

            # Main dish here.
            if not safetyOn:
                if not oldButtons == newButtons:
                    #ti = self.printButtons(newButtons) # Debug print.
                    #j = 0
                    #cv2.imwrite(f'{ti}.{j}.png', frame)
                    # Safety Off ... Fire !!!!!!!!
                    for k in newButtons[:8]:
                        self.servo[k].tap()
                        #j += 1
                        #ret, frame = cap.read() # To see what is in between taps.
                        #cv2.imwrite(f'{ti}.{j}.png', frame)
                    oldButtons = newButtons
                    time.sleep(0.21) # Wait before taking another image.
        #endwhile
    #enddef

def main():
    # TO-DO: How to control precisely the cleanup of cap??

    # Fire up the webcam and set capture properties.
    global cap
    cap = cv2.VideoCapture(0)
    cap.set( cv2.CAP_PROP_FRAME_WIDTH, frame_width )
    cap.set( cv2.CAP_PROP_FRAME_HEIGHT, frame_height )
    #cap.set( cv2.CAP_PROP_FPS, 15 )

    # Run the machine.
    tpm = TapTapMachine()
    tpm.run()
    tpm.cleanup()
    
    # Done with the webcam.
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

