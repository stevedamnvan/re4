@echo off
rem Build the hwtrace Flycast (MSVC + Ninja). usage: build_fc.bat <flycast source dir at 12bb43652 + hwtrace.patch>
rem Output: <src>\build-hwtrace\flycast.exe. Adjust VCVARS / CMAKE / NINJA for your machine.
setlocal
set SRC=%~1
if "%SRC%"=="" set SRC=%CD%
if "%VCVARS%"=="" set VCVARS=C:\BuildTools\VS2022\VC\Auxiliary\Build\vcvars64.bat
if "%CMAKE%"=="" set CMAKE=C:\Program Files\CMake\bin\cmake.exe
if "%NINJA%"=="" set NINJA=C:/Users/lambd/AppData/Local/Microsoft/WinGet/Packages/Ninja-build.Ninja_Microsoft.Winget.Source_8wekyb3d8bbwe/ninja.exe
call "%VCVARS%" >nul
cd /d "%SRC%"
if not exist build-hwtrace\build.ninja (
"%CMAKE%" -S . -B build-hwtrace -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM=%NINJA% -DUSE_VULKAN=OFF -DUSE_BREAKPAD=OFF -DUSE_DISCORD=OFF -DUSE_LUA=OFF -DUSE_DX9=OFF || exit /b 1
)
"%CMAKE%" --build build-hwtrace --config Release -j %NUMBER_OF_PROCESSORS%
