#
# Cozmonaut
# Copyright 2019 The Cozmonaut Contributors
#

cmake_minimum_required(VERSION 3.4)
project(linenoise)

set(linenoise_SRC_FILES
        src/linenoise.c
        )

add_library(linenoise STATIC ${linenoise_SRC_FILES})
set_target_properties(linenoise PROPERTIES C_STANDARD 99)
target_include_directories(linenoise PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/include/")
