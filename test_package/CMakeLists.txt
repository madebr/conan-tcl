cmake_minimum_required(VERSION 2.8.12)
project(PackageTest C)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

add_executable(embed_tcl embed_tcl.c)
target_link_libraries(embed_tcl ${CONAN_LIBS})

enable_testing()
add_test(NAME embed_tcl
         WORKING_DIRECTORY ${CMAKE_BINARY_DIR}/bin
         COMMAND embed_tcl)
