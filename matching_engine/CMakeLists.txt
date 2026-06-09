cmake_minimum_required(VERSION 3.22)
project(quantforge_matching_engine CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Source files
set(SOURCES
    src/OrderBook.cpp
    src/MatchingEngine.cpp
    src/main.cpp
)

# Header files path
include_directories(include)
include_directories(../shared/cpp)

# Output binary target
add_executable(quantforge_matching_engine ${SOURCES})

# Test binary target
add_executable(test_matching src/OrderBook.cpp src/test_matching.cpp)

# Links
target_link_libraries(quantforge_matching_engine PRIVATE Threads::Threads)
target_link_libraries(test_matching PRIVATE Threads::Threads)

