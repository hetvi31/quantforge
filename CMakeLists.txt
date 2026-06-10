cmake_minimum_required(VERSION 3.22)
project(QuantForge CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Default to an optimized build. A "low-latency" engine compiled at -O0 is a
# contradiction, so Release is the default unless the caller overrides it.
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# Aggressive optimization flags for GCC/Clang release builds.
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG -funroll-loops")
    # -march=native gives the best numbers locally; disable for portable CI images
    # by configuring with -DQF_PORTABLE_BUILD=ON.
    option(QF_PORTABLE_BUILD "Build without -march=native for portable binaries" OFF)
    if(NOT QF_PORTABLE_BUILD)
        include(CheckCXXCompilerFlag)
        check_cxx_compiler_flag("-march=native" QF_HAS_MARCH_NATIVE)
        if(QF_HAS_MARCH_NATIVE)
            string(APPEND CMAKE_CXX_FLAGS_RELEASE " -march=native")
        endif()
    endif()
    # Link-time optimization when supported.
    # Disable with -DQF_NO_LTO=ON for Alpine/musl builds: GCC 13 + musl fortify
    # headers declare vsnprintf as always_inline which conflicts with LTO's
    # ability to rewrite function bodies at link time, causing a linker error.
    option(QF_NO_LTO "Disable LTO (required on Alpine/musl with GCC 13+)" OFF)
    if(NOT QF_NO_LTO)
        include(CheckIPOSupported)
        check_ipo_supported(RESULT QF_IPO_SUPPORTED OUTPUT _ipo_msg)
        if(QF_IPO_SUPPORTED)
            set(CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE ON)
        endif()
    else()
        message(STATUS "LTO disabled (QF_NO_LTO=ON)")
    endif()
endif()

message(STATUS "QuantForge build type: ${CMAKE_BUILD_TYPE}")

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

# Aggregate test target: `ctest` or `cmake --build . --target run_tests`
enable_testing()
add_test(NAME matching_engine_unit_tests COMMAND test_matching)
