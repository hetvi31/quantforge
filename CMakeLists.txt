cmake_minimum_required(VERSION 3.22)
project(QuantForge CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Configure output directories
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# Setup Threads
find_package(Threads REQUIRED)

# Common include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/shared/cpp)

# Subdirectories
add_subdirectory(matching_engine)
add_subdirectory(feed_handler)
