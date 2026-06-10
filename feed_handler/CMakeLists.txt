cmake_minimum_required(VERSION 3.22)
project(quantforge_feed_handler CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Threads REQUIRED)

add_executable(quantforge_feed_handler src/main.cpp)
target_include_directories(quantforge_feed_handler PRIVATE ../shared/cpp)
target_link_libraries(quantforge_feed_handler PRIVATE Threads::Threads)
