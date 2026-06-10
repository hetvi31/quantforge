cmake_minimum_required(VERSION 3.22)
project(quantforge_matching_engine CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Ensure Threads is available when this dir is configured standalone.
find_package(Threads REQUIRED)

# Engine core library (shared by the server binary, tests, and benchmark).
add_library(matching_core STATIC
    src/OrderBook.cpp
    src/MatchingEngine.cpp
)
target_include_directories(matching_core PUBLIC include ../shared/cpp)
target_link_libraries(matching_core PUBLIC Threads::Threads)

# Production server binary.
add_executable(quantforge_matching_engine src/main.cpp)
target_link_libraries(quantforge_matching_engine PRIVATE matching_core)

# Unit tests.
add_executable(test_matching src/test_matching.cpp)
target_link_libraries(test_matching PRIVATE matching_core)

# Latency benchmark (in-process, no network).
add_executable(bench_matching src/benchmark.cpp)
target_link_libraries(bench_matching PRIVATE matching_core)
