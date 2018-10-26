# -*- coding: utf-8 -*-

from conans import ConanFile, AutoToolsBuildEnvironment, tools
from conans.errors import ConanExceptionInUserConanfileMethod
import os


class TclConan(ConanFile):
    name = "tcl"
    version = "8.6.8"
    description = "Tcl is a very powerful but easy to learn dynamic programming language."
    topics = ["conan", "tcl", "scripting", "programming"]
    url = "https://github.com/bincrafters/conan-tcl"
    homepage = "https://tcl.tk"
    author = "Bincrafters <bincrafters@gmail.com>"
    license = "TCL"
    exports = ["LICENSE.md"]
    settings = "os", "compiler", "build_type", "arch"
    options = {
        "fPIC": [True, False],
        "shared": [True, False]
    }
    default_options = {
        "fPIC": False,
        "shared": False,
    }
    _source_subfolder = "sources"
    requires = ("zlib/1.2.11@conan/stable")

    @property
    def _is_mingw_windows(self):
        return self.settings.os == "Windows" and self.settings.compiler == "gcc"

    def configure(self):
        if self.settings.compiler != "Visual Studio":
            del self.settings.compiler.libcxx

    def build_requirements(self):
        if self._is_mingw_windows:
            self.build_requires("msys2_installer/latest@bincrafters/stable")

    def source(self):
        url = "https://prdownloads.sourceforge.net/tcl/tcl{}-src.tar.gz".format(self.version)
        tools.get(url, sha256="c43cb0c1518ce42b00e7c8f6eaddd5195c53a98f94adc717234a65cbcfd3f96a")
        extracted_dir = "{}{}".format(self.name, self.version)
        os.rename(extracted_dir, self._source_subfolder)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
        else:
            if self.options.shared:
                self.options.fPIC = True
                # del self.options.fPIC  # Does not make sense.

    @property
    def _configure_dir(self):
        if self.settings.os == "Windows":
            return os.path.join(self.source_folder, self._source_subfolder, "win")
        elif self.settings.os == "Linux":
            return os.path.join(self.source_folder, self._source_subfolder, "unix")
        elif self.settings.os == "Macos":
            return os.path.join(self.source_folder, self._source_subfolder, "macosx")
        else:
            raise ConanExceptionInUserConanfileMethod("Invalid os: {}".format(self.settings.os))

    def _get_auto_tools(self):
        autoTools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
        if self._is_mingw_windows:
            # FIXME: bug in zlib/1.2.11@conan/stable ??
            autoTools.libs.append("z")
        return autoTools

    def _build_nmake(self, target="release"):
        opts = []
        # https://core.tcl.tk/tips/doc/trunk/tip/477.md
        if not self.options.shared:
            opts.append("static")
        if self.settings.build_type == "Debug":
            opts.append("symbols")
        if "MD" in self.settings.compiler.runtime:
            opts.append("msvcrt")
        else:
            opts.append("nomsvcrt")
        vcvars_command = tools.vcvars_command(self.settings)
        self.run(
            '{vcvars} && nmake -nologo -f "{cfgdir}/makefile.vc" shell INSTALLDIR="{pkgdir}" OPTS={opts} {target}'.format(
                vcvars=vcvars_command,
                cfgdir=self._configure_dir,
                pkgdir=self.package_folder,
                opts=",".join(opts),
                target=target,
            ), cwd=self._configure_dir,
        )

    def _build_autotools(self):
        conf_args = [
            "--enable-threads",
            "--enable-shared" if self.options.shared else "--disable-shared",
            "--enable-symbols" if self.settings.build_type == "Debug" else "--disable-symbols",
        ]
        if self.settings.arch == "x86_64":
            conf_args.append("--enable-64bit")
        autoTools = self._get_auto_tools()
        autoTools.configure(configure_dir=self._configure_dir, args=conf_args)

        # https://core.tcl.tk/tcl/tktview/840660e5a1
        for root, _, files in os.walk(self.build_folder):
            if "Makefile" in files:
                tools.replace_in_file(os.path.join(root, "Makefile"), "-Dstrtod=fixstrtod", "", strict=False)

        with tools.chdir(self.build_folder):
            autoTools.make()

    def build(self):
        if self.settings.compiler == "Visual Studio":
            self._build_nmake()
        else:
            self._build_autotools()

    def package(self):
        if self.settings.compiler == "Visual Studio":
            self._build_nmake("install")
        else:
            with tools.chdir(self.build_folder):
                autoTools = self._get_auto_tools()
                autoTools.install()
        self.copy(pattern="license.terms", dst="licenses", src=self._source_subfolder)

    def package_info(self):
        libs = []
        libdirs = []
        for root, _, _ in os.walk(os.path.join(self.package_folder, "lib"), topdown=False):
            newlibs = tools.collect_libs(self, root)
            if newlibs:
                libs.extend(newlibs)
                libdirs.append(root)
        if self._is_mingw_windows:
            # FIXME: bug in zlib/1.2.11@conan/stable ??
            libs.append("z")
        if self.settings.compiler == "Visual Studio":
            libs.extend(["netapi32"])
        else:
            libs.extend(["m", "pthread"])
            if self._is_mingw_windows:
                libs.extend(["ws2_32", "netapi32", "userenv"])
            else:
                libs.append("dl")
        defines = []
        if not self.options.shared:
            defines.append("STATIC_BUILD")
        self.cpp_info.defines = defines
        self.cpp_info.bindirs = ["bin"]
        self.cpp_info.libdirs = libdirs
        self.cpp_info.libs = libs
        self.cpp_info.includedirs = ["include"]
        self.env_info.TCL_LIBRARY = os.path.join(self.package_folder, "lib", "tcl{}".format(".".join(self.version.split(".")[:2])))
        if self.settings.os == "Macos":
            self.cpp_info.exelinkflags.append("-framework Cocoa")
            self.cpp_info.sharedlinkflags = self.cpp_info.exelinkflags
