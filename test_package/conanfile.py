# -*- coding: utf-8 -*-

import os

from conans import ConanFile, CMake, tools, RunEnvironment


class TclTestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def imports(self):
        self.copy("*.dll", dst="bin", src="bin")
        self.copy("*.dylib*", dst="bin", src="lib")
        self.copy("*.so*", dst="bin", src="lib")

    def test(self):
        with tools.environment_append(RunEnvironment(self).vars):
            bin_path = os.path.join("bin", "test_package")
            if self.settings.os == "Macos":
                self.run("DYLD_LIBRARY_PATH={} {}".format(os.environ.get("DYLD_LIBRARY_PATH", ""), bin_path))
            else:
                self.run(bin_path)
        assert(os.path.exists(os.environ["TCLSH"]))
