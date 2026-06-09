cmake_minimum_required(VERSION 3.22)
project(quantforge_feed_handler CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Source files
set(SOURCES
    src/main.cpp
)

# Header paths
include_directories(include)
include_directories(../shared/cpp)

# Binary target
add_executable(quantforge_feed_handler ${SOURCES})

# Links
target_link_libraries(quantforge_feed_handler PRIVATE Threads::Threads)
