#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

cmake_minimum_required(VERSION 3.4)
project(cozmonaut C CXX)

add_subdirectory(third_party/linenoise-cmake)

find_package(PythonInterp 3.6 REQUIRED)
find_package(PythonLibs 3.6 REQUIRED)

set(cozmo_SRC_FILES
        src/global.c
        src/main.c
        )

add_executable(cozmo ${cozmo_SRC_FILES})
set_target_properties(cozmo PROPERTIES C_STANDARD 99 CXX_STANDARD 11)
target_include_directories(cozmo PRIVATE ${PYTHON_INCLUDE_DIRS})
target_link_libraries(cozmo PRIVATE linenoise ${PYTHON_LIBRARIES})
