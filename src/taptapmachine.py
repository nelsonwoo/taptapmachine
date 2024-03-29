#!/usr/bin/python3
#
# Move/Tap servo arms according to the color of the image target.

import cv2
import RPi.GPIO as GPIO
import pigpio # Less servo jitter. Need pigpiod running.
import time

# Servo colors.
WHITE = 22 # GPIO pin.
RED   = 23 # GPIO pin.
BLUE  = 17 # GPIO pin.
GREY  = 25 # GPIO pin but not connected.  We assume the 4th color meaning none of the above.

colorText = {
    WHITE: "WHITE",
    RED  : "RED  ",
    BLUE : "BLUE ",
    GREY : "GREY ",
    }

# Webcam resolution.
frame_height = 270
frame_width = 480

class Pixel:
    move = 1 # Number of pixel to move targets.
    color_differential = 60 # Differential of RGB values to call a specific color.
    color_threshold = 100 # Minimum RGB value to identify a color.
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
        b,g,r = (frame[self.y][self.x])
        cv2.putText( frame, f'{colorText[self.getColor(frame)]}({r},{g},{b})', (self.x+10,self.y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2, cv2.LINE_AA )
        for i in range(1, 5):
            frame[self.y][self.x+i] = frame[self.y][self.x-i] = \
            frame[self.y+i][self.x] = frame[self.y-i][self.x] = Pixel.flipColor(frame[self.y][self.x])
    def getColor(self, frame):
        """Get the color code of this target from the frame."""
        b, g, r = ( frame[self.y][self.x] )
        # Our scheme to determine the color at the target.
        if g > Pixel.color_threshold and r > Pixel.color_threshold and b > Pixel.color_threshold: # r > Pixel.color_threshold and b > Pixel.color_threshold and g > Pixel.color_threshold:
            return WHITE
        if r > b+Pixel.color_differential:
            return RED
        if b > r+Pixel.color_differential: # and b > g+Pixel.color_differential:
            return BLUE
        else:
            return GREY
    @classmethod
    def flipColor(cls, pixel):
        b, g, r = ( pixel )
        return (255-b, 255-g, 255-r)

class Servo:
    pwm = pigpio.pi()
    def __init__(self, gpin, angle=135.0):
        self.gpin = gpin
        self.angleUp = angle # degrees.
        self.angleDisplacement = 20 # 18 is good
        self.tapDuration0 =     0.045 # seconds. #<--- 0.045
        self.postTapDuration0 = 0.100 # seconds. #<--- 0.105
        self.tapDuration = 0.0
        self.postTapDuration = 0.0
        Servo.pwm.set_mode(self.gpin, pigpio.OUTPUT)
        Servo.pwm.set_PWM_frequency(self.gpin, 50)  # My servo operates at 50Hz.
        Servo.pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp)) # Move arm to the ready position.
        self.faster(reset=True)
    def cleanup(self):
        Servo.pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(90.0)) # Park arm all the way up for maintenance.
        time.sleep(self.tapDuration)
        Servo.pwm.set_PWM_dutycycle(self.gpin, 0)
        Servo.pwm.set_PWM_frequency(self.gpin, 0)
    def __repr__(self):
        return f'{colorText.get(self.gpin)}: Servo({colorText.get(self.gpin)}, {self.angleUp}),'
    def faster(self, reset=False):
        #self.tapDuration -= 0.001
        self.postTapDuration -= 0.001
        if reset:
            self.tapDuration = self.tapDuration0
            self.postTapDuration = self.postTapDuration0
        print("self.tapDuration0 =    ", self.tapDuration)
        print("self.postTapDuration0 =", self.postTapDuration)

    def tap(self):
        #Servo.pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp-self.angleDisplacement)) # Lower arm.
        Servo.pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(0)) # Lower arm.
        time.sleep(self.tapDuration) # Wait slightly for the arm to tap.
        Servo.pwm.set_servo_pulsewidth(self.gpin, Servo.translateDegree(self.angleUp)) # Raise arm.
        time.sleep(self.postTapDuration)
    def tuneAngle(self, change=1):
        self.angleUp += change
        if self.angleUp < 11.0:
            self.angleUp = 11.0
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
            RED  : Servo(RED  , 24.0),
            WHITE: Servo(WHITE, 33.0),
            BLUE : Servo(BLUE , 23.0),
            GREY : Servo(GREY , 45.0),
            }
        # There are only 8 pixels in the frame for the game. The 9th pixel tracks the GO! signal.
        self.target = [Pixel(26,269), Pixel(49,271), Pixel(73,272), Pixel(98,274), Pixel(128,276), Pixel(159,279), Pixel(194,282), Pixel(231,284), Pixel(94,186), ]
    def cleanup(self):
        # Report the servo and target settings in case the next run wants to know.
        for k, v in self.servo.items():
            v.cleanup()
            print(repr(v))
        print('self.target = [', end = '')
        for tgt in self.target:
            print(repr(tgt), end=', ')
        print(']')
    def printButtons(self, buttons):
        ti = time.time()
        print(ti, end=' ')
        for k in buttons:
            print(colorText.get(k), end=' ')
        print('')
        return ti
    def run(self):
        safetyOn = True
        targetMovable = 0
        servoInFocus = GREY
        oldButtons = []
        newButtons = []
        level = 0
        tapCount = 0
        cameraWait = 0.170  # <-- Tune this
        while True:
            ret, frame = cap.read() # Capture 1 frame from image input.
            if not ret:
                break

            # Display the image for a little while and handle keyboard.
            for tgt in self.target:
                tgt.drawCrossHair(frame)
            
            cv2.imshow('live video', frame)
            key = cv2.waitKey(1)

            #match key: # Since Python 3.10.  Mine at 3.9.2.
            #	case ord('q'):

            # Quit.
            if (key==ord('q')):
                print('Quit')
                break

            # Reset Level.
            elif (key==ord('r')):
                print('Reset Level')
                self.servo[WHITE].faster(reset=True)
                self.servo[RED].faster(reset=True)
                self.servo[BLUE].faster(reset=True)
                level = 0

            elif (key==ord('f')):
                self.servo[WHITE].faster()
                self.servo[RED].faster()
                self.servo[BLUE].faster()

            # Flip the safety on/off.
            elif (key==ord('s')):
                safetyOn = not safetyOn
                if safetyOn:
                    print('Safety ON')
                else:
                    print('Safety OFF')
                    level += 1
                    tapCount = 0
                    tapMax = 30 if level < 4 else level*5 + 15

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
                if not safetyOn:
                    print(f"Grey")
                continue

            if (key==ord('p')):
                self.printButtons(newButtons)

            # Discard and try again if the text "GO!" is still in this frame.
            if self.target[-1].getColor(frame) == WHITE:
                time.sleep(0)
                continue

            # Main dish here.
            if not safetyOn:
                if not oldButtons == newButtons:
                    #j = 0
                    # Safety Off ... Fire !!!!!!!!
                    if tapCount == 0:
                        tiStart = time.time()

                    for k in newButtons[:8]:
                        self.servo[k].tap()
                        tapCount += 1

                    self.printButtons(newButtons) # Debug print.
                    cv2.imwrite(f'{tapCount}.png', frame)

                    oldButtons = newButtons
                    time.sleep(cameraWait) # Wait before taking another image.

        #endwhile
    #enddef

def main():
    # TO-DO: How to control precisely the cleanup of resources?

    # Fire up the webcam and set capture properties. Assume the frame size is ok.
    global cap
    cap = cv2.VideoCapture(0)
    cap.set( cv2.CAP_PROP_FRAME_WIDTH, frame_width )
    cap.set( cv2.CAP_PROP_FRAME_HEIGHT, frame_height )
    cap.set( cv2.CAP_PROP_FPS, 30 )

    # Run the machine.
    tpm = TapTapMachine()
    tpm.run()
    tpm.cleanup()

    # Done with the webcam.
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
