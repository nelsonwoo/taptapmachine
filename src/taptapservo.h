#ifndef TAP_TAP_SERVO_H
#define TAP_TAP_SERVO_H

#include <pigpio.h>
#include <memory>
#include <thread>
#include <chrono>

class TapTapServo
{
public:
    TapTapServo( int pin, int upPos )
        : gpio(pin), armUpPos(upPos)
    {
        move( armUpPos );
    }

    ~TapTapServo()
    {
        move();
    }

    // Adjust the servo arm ready position.
    int adjust( int v ) {
        armUpPos += v;
        move( armUpPos );
        return armUpPos;
    }

    // Move to the armPos and give some slack time to move.
    void move( int armPos = 0, int ms = 40 )
    {
        if (armPos) {
            gpioServo( gpio, armPos );
            std::this_thread::sleep_for( std::chrono::milliseconds(ms) );
            //time_sleep( sec ); // hope sleep_for is more accurate.
        }
        else {
            gpioServo( gpio, 1500 ); // Park at 90 deg.
            std::this_thread::sleep_for( std::chrono::milliseconds(100) );
            gpioServo( gpio, 0 );    // Stop further output.
        }
    }

    // Tap like a pro.
    void tap( int timeDown = 40, int timeUp = 40 )
    {
        move( 500, timeDown ); // all the way down.
        move( armUpPos, timeUp );
    }

    int gpio;
    int armUpPos;
};

// Singleton for pigpio initialization.
class ServoInit
{
public:
    ServoInit(const ServoInit&) = delete;
    ServoInit& operator = (const ServoInit&) = delete;
    static ServoInit& getInstance() {
        return instance;
    }

protected:
    ServoInit() {
        if (!bInitialized) bInitialized = (gpioInitialise() >= 0);
    }
    ~ServoInit() {
        if (bInitialized) gpioTerminate();
        bInitialized = false;
    }
    static ServoInit instance;
    bool bInitialized{ false };
};

#endif
