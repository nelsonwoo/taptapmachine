#include <iostream>
#include <algorithm>
#include <memory>
#include <opencv2/opencv.hpp>
#include "taptapservo.h"

using namespace cv;

// The value are GPIO pins.
enum ColorE {
    white = 22,
    red   = 23,
    blue  = 17,
    grey  = 25, // non-connected
};

//Vec3b getPixelBGR(const Mat& mat, const Point& pt)
//{
//    return mat.at<Vec3b>(pt);
//}

ColorE getPixelColorE(const Mat& mat, const Point& pt)
{
    static const uchar color_differential{ 70 }; // prominent color
    static const uchar color_threshold{ 140 }; // differentiate between white and grey
    auto v{ mat.at<Vec3b>(pt) };
    auto b{ v[0] };
    auto g{ v[1] };
    auto r{ v[2] };
    if (r > b+color_differential) return ColorE::red;
    if (b > r+color_differential) return ColorE::blue;
    if (g > color_threshold) return ColorE::white;
    return ColorE::grey;
}

void invertPixelColor(Mat& mat, const Point& pt, ColorE color = ColorE::grey)
{
    Vec3b v{ mat.at<Vec3b>(pt) };
    switch (color) {
    case ColorE::grey:
        v[0] = 255 - v[0];
        v[1] = 255 - v[1];
        v[2] = 255 - v[2];
        break;
    case ColorE::white: v[0] = v[1] = v[2] = 255; break;
    case ColorE::red  : v[0] = v[1] = 0; v[2] = 255; break;
    case ColorE::blue : v[0] = 255; v[1] = v[2] = 0; break;
    }
    mat.at<Vec3b>(pt) = v;
}

// Return if the Point is grey (return false) or not grey (return true).
bool drawCrossHair(Mat& mat, const Point& pt, ColorE color = ColorE::grey)
{
    auto k{ getPixelColorE(mat, pt) };
    for (int i{ -5 }; i < 6; ++i) {
        if (i == 0) continue;
        invertPixelColor(mat, Point(pt.x+i,pt.y+i), k);
        invertPixelColor(mat, Point(pt.x+i,pt.y-i), k);
        invertPixelColor(mat, Point(pt.x,pt.y+i));
        invertPixelColor(mat, Point(pt.x+i,pt.y));
    }
    return ColorE::grey != k;
}

// The number of correct taps to clear each game level, starts at Level 1.
// 30, 30, 30, 35, 40, 45, ...
int tapCountInLevel(int gameLevel) {
    return std::max( 15+5*gameLevel, 30 );
}

// Time limit for each game level.
// 30000, 25000, 20000, 20000, 20000, 20000, ...
int millisecInLevel(int gameLevel) {
    return std::max( 35000-5000*gameLevel, 20000 );
}

void printLevelSummary(int gameLevel, int msElapsed) {
    std::cerr << "\nLevel " << gameLevel << ". ";
    std::cerr << "Taps " << tapCountInLevel(gameLevel) << ". ";
    std::cerr << "Time " << msElapsed << "ms. ";
    std::cerr << "Average " << msElapsed/tapCountInLevel(gameLevel) << "ms/tap.";
    std::cerr << "\n";
}


int main()
{
    // Initialize the camera.
    VideoCapture cap{0};
    if (!cap.isOpened()) return 4;
    cap.set( CAP_PROP_FRAME_WIDTH, 640 );
    cap.set( CAP_PROP_FRAME_HEIGHT, 360 );
    cap.set( CAP_PROP_FPS, 30 ); // i.e. 33ms per frame

    // Prepare the viewport.
    std::string window_name{ "My Camara" };
    namedWindow(window_name);

    // The servos for the GPIO pins, but we only need 3. We never use pin 40 anyway.
    constexpr size_t MAX_GPIO_PIN{ 40 };
    std::array<std::shared_ptr<TapTapServo>, MAX_GPIO_PIN> servo;

    // Note: The ServoInit class singletom initializes pigpio resources.


    // Setup here /////////////////////////////////////////
    // The first 8 Points are the button colors to tap.
    // The second _last_ detects the GAME OVER text.
    // The _last_ Point detects the READY text.
    Point target[]{
        {253,30}, {253,69}, {250,107}, {248,145}, {246,189}, {244,238}, {239,288}, {233,317}, {226,155}, {242,113},
    };
    // The amount of time at servo arm down/up positions.  Wait time before taking next frame.
    int timeDown{ 35 }; // milliseconds
    int timeUp{ 125 }; // milliseconds
    int timeCamera{ 200 }; // milliseconds
    // The 3 servos with their Up positions.
    servo[ColorE::white] = std::make_shared<TapTapServo>( ColorE::white, 736 );
    servo[ColorE::red] = std::make_shared<TapTapServo>( ColorE::red, 733 );
    servo[ColorE::blue] = std::make_shared<TapTapServo>( ColorE::blue, 741 );
    // Setup here /////////////////////////////////////////


    // Text for display.
    char colorText[MAX_GPIO_PIN];
    colorText[ColorE::white] = 'W';
    colorText[ColorE::red  ] = 'R';
    colorText[ColorE::blue ] = 'B';
    colorText[ColorE::grey ] = '.';

    constexpr size_t tgtSize{ sizeof(target)/sizeof(target[0]) };
    int tgtInFocus{ 0 };
    ColorE servoInFocus{ ColorE::white };

    constexpr int TEST_BASE_LEVEL{ 0 };
    int gameLevel{ TEST_BASE_LEVEL };
    int lvTapCount{ 30 };
    int tapped{ 0 };

    bool safetyOn{ true };
    bool gameReady{ false };
    bool keepRunning{ true };

    std::chrono::high_resolution_clock::time_point tpStart;
    Mat frame;

    //// Video output to audit what the camera sees later.
    //std::unique_ptr<VideoWriter> pVideo{};

    do {
        cap >> frame;
        if (frame.empty()) break;

        // Draw the cross hair over the target pixels.
        // Examime for uncertain color.
        bool bNoGrey{ true };
        for (const auto& tgt : target) {
            bNoGrey &= drawCrossHair(frame, tgt);
        }

        // Accept keyboard input while safety is on.
        if (safetyOn) {
            imshow(window_name, frame);
            switch (waitKey(1)) {
            case 'q':
            case 27: // Press 'Esc' or 'q' to quit.
                // Generate the code that can be reused.
                // Could use a resource file but I'm lazy.
                std::cerr << "    Point target[]{\n        ";
                for (const auto& tgt : target)
                    std::cerr << "{" << tgt.x << "," << tgt.y << "}, ";
                std::cerr << "\n    };\n";
                std::cerr << "    int timeDown{ " << timeDown << " }; // milliseconds\n";
                std::cerr << "    int timeUp{ " << timeUp << " }; // milliseconds\n";
                std::cerr << "    int timeCamera{ " << timeCamera << " }; // milliseconds\n";
                std::cerr << "    ... ColorE::white, " << servo[ColorE::white]->adjust(0) << " );\n";
                std::cerr << "    ... ColorE::red,   " << servo[ColorE::red  ]->adjust(0) << " );\n";
                std::cerr << "    ... ColorE::blue,  " << servo[ColorE::blue ]->adjust(0) << " );\n";

                keepRunning = false;
                break;
            case 's': // Press 's' to start tapping in the level.
                safetyOn = false;
                ++ gameLevel;
                lvTapCount = tapCountInLevel(gameLevel);
                tapped = 0;
                // Enable dynamic timing for fun. Need tuning.
                //timeUp = (millisecInLevel(gameLevel) - lvTapCount*(timeDown+20) - lvTapCount/8*timeCamera) / lvTapCount;
                break;
            case 'r': // Press 'r' to reset to the first level.
                std::cerr << "Reset.\n";
                gameLevel = TEST_BASE_LEVEL;
                break;

            // Move targets.
/*UP*/      case 'i': for (int i{ tgtInFocus }; i < tgtSize; ++i) --target[i].y; break;
/*DOWN*/    case 'k': for (int i{ tgtInFocus }; i < tgtSize; ++i) ++target[i].y; break;
/*LEFT*/    case 'j': for (int i{ tgtInFocus }; i < tgtSize; ++i) --target[i].x; break;
/*RIGHT*/   case 'l': for (int i{ tgtInFocus }; i < tgtSize; ++i) ++target[i].x; break;
/*next*/    case 'n': if (++tgtInFocus >= tgtSize) tgtInFocus = 0; break;
            // Test Arms.
/*WHITE*/   case '1': servo[servoInFocus = ColorE::white]->tap( timeDown, timeUp ); break;
/*RED*/     case '2': servo[servoInFocus = ColorE::red  ]->tap( timeDown, timeUp ); break;
/*BLUE*/    case '3': servo[servoInFocus = ColorE::blue ]->tap( timeDown, timeUp ); break;
            // Tune arm time.
/*LONGER*/  case '5': ++timeUp; break;
/*SHORTER*/ case 't': --timeUp; break;
/*LONGER*/  case 'g': ++timeDown; break;
/*SHORTER*/ case 'b': --timeDown; break;
            // Tune arm height.
            case '=':
/*HIGHER*/  case '+': servo[servoInFocus]->adjust(1); break;
            case '-':
/*LOWER*/   case '_': servo[servoInFocus]->adjust(-1); break;
            }//switch
        }


        // Proceed if safety is off.
        // bNoGrey prevents uncertainties. Better go back and take another frame.
        if (!safetyOn && bNoGrey) {

            if (!gameReady) {
                // READY ?
                if (ColorE::blue != getPixelColorE(frame, target[tgtSize-1])) continue;

                // The game is ready for tapping at this point and on.
                //std::cerr << "Level Start.\n";

                // Start an audit video on this level.
                /*
                char filename[64];
                sprintf( filename, "level%02d.avi", gameLevel );
                pVideo = std::make_unique<VideoWriter>(filename, VideoWriter::fourcc('M','J','P','G'), 1, Size(640,360));
                pVideo->write(frame); // Keep in a video for debugging.
                */

                gameReady = true;
                tpStart = std::chrono::high_resolution_clock::now();
            }

            // GAME OVER ?
            if (ColorE::white == getPixelColorE(frame, target[tgtSize-2])) {
                std::cerr << "Game Over.\n";
                safetyOn = true;
                gameReady = false;
                //pVideo = nullptr; // flush video by going out of scope.
                continue;
            }

            // Actual tapping.
            for (int i{ 0 }; i < 8; ++i) {
                auto k{ getPixelColorE(frame, target[i]) };
                if (ColorE::grey == k) break; // sanity check
                servo[k]->tap(timeDown, timeUp);
                std::cerr << colorText[k];
                if (++tapped >= lvTapCount) {
                    auto tpEnd{ std::chrono::high_resolution_clock::now() };
                    std::cerr << '\n';
                    printLevelSummary(gameLevel, (tpEnd-tpStart).count()/1'000'000); //Lazy.
                    safetyOn = true;
                    gameReady = false;
                    //pVideo = nullptr; // flush video by going out of scope.
                    break;
                }
            }

            // Keep an image of what the program saw for what was being tapped.
            char filename[64];
            sprintf( filename, "level%02d.%03d.bmp", gameLevel, tapped );
            imwrite( filename, frame );

            // Give a bit more time before going back to take another frame.
            // Cannot completely remove because zero wait time could result
            // in the same picture without even any shift, theoretically.
            std::this_thread::sleep_for( std::chrono::milliseconds(timeCamera) );
       }

    } while (keepRunning);

    cap.release();
    destroyAllWindows();

    return 0;
}

