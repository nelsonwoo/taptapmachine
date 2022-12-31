-- premake5.lua
workspace "TapTapMachine"
    configurations { "Release" }

    filter "configurations:Release"
        defines { "NDEBUG" }
        optimize "On"

project "taptapcamera"
    kind "ConsoleApp"
    language "C++"
    cppdialect "C++17"
    targetdir "bin"

    files { "src/taptapcamera.cc", "src/taptapservo.cc" }
    buildoptions { "`pkg-config --cflags-only-I opencv4`" }
    linkoptions { "`pkg-config --libs-only-l opencv4`" }
    links { "pigpio" }

