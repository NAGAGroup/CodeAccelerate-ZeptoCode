cmake_minimum_required(VERSION 3.25)
project(cpp-demo-project VERSION 0.1.0 LANGUAGES CXX)

# ============================================================
# Global Settings
# ============================================================
# CPM.cmake dependencies
include(cmake/CPM.cmake)
# CPMAddPackage(
#    "gh:owner/repo#tag"
# )

# C++ standard
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Export compile commands for clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ============================================================
# Application
# (Remove this section if you don't need an executable)
# ============================================================
add_subdirectory(app)
