# -*- coding: utf-8 -*-

from conans import ConanFile, AutoToolsBuildEnvironment, tools
from conans.errors import ConanExceptionInUserConanfileMethod
from conans.util.env_reader import get_env
import os
import shutil
import tempfile


class TclConan(ConanFile):
    name = "tcl"
    version = "8.6.9"
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
        "fPIC": True,
        "shared": False,
    }
    _source_subfolder = "sources"
    requires = ("zlib/1.2.11@conan/stable", )

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
        filename = "tcl{}-src.tar.gz".format(self.version)
        url = "https://downloads.sourceforge.net/project/tcl/Tcl/{}/{}".format(self.version, filename)
        sha256 = "ad0cd2de2c87b9ba8086b43957a0de3eb2eb565c7159d5f53ccbba3feb915f4e"

        dlfilepath = os.path.join(tempfile.gettempdir(), filename)
        if os.path.exists(dlfilepath) and not get_env("TCL_FORCE_DOWNLOAD", False):
            self.output.info("Skipping download. Using cached {}".format(dlfilepath))
        else:
            self.output.info("Downloading {} from {}".format(self.name, url))
            tools.download(url, dlfilepath)
        tools.check_sha256(dlfilepath, sha256)
        tools.untargz(dlfilepath)

        extracted_dir = "{}{}".format(self.name, self.version)
        os.rename(extracted_dir, self._source_subfolder)

        unix_config_dir = self._get_configure_dir("unix")
        # When disabling 64-bit support (in 32-bit), this test must be 0 in order to use "long long" for 64-bit ints
        # (${tcl_type_64bit} can be either "__int64" or "long long")
        tools.replace_in_file(os.path.join(unix_config_dir, "configure"),
                              "(sizeof(${tcl_type_64bit})==sizeof(long))",
                              "(sizeof(${tcl_type_64bit})!=sizeof(long))")

        unix_makefile_in = os.path.join(unix_config_dir, "Makefile.in")
        # Avoid building internal libraries as shared libraries
        tools.replace_in_file(unix_makefile_in, "--enable-shared --enable-threads", "--enable-threads")
        # Avoid clearing CFLAGS and LDFLAGS in the makefile
        tools.replace_in_file(unix_makefile_in, "\nCFLAGS\t", "\n#CFLAGS\t")
        tools.replace_in_file(unix_makefile_in, "\nLDFLAGS\t", "\n#LDFLAGS\t")
        # Use CFLAGS and CPPFLAGS as argument to CC
        tools.replace_in_file(unix_makefile_in, "${CFLAGS}", "${CFLAGS} ${CPPFLAGS}")

    def config_options(self):
        if self.settings.compiler == "Visual Studio" or self.options.shared:
            del self.options.fPIC

    def _get_default_build_system(self):
        if self.settings.os == "Macos":
            return "macosx"
        elif self.settings.os == "Linux":
            return "unix"
        elif self.settings.os == "Windows":
            return "win"
        else:
            raise ConanExceptionInUserConanfileMethod("Unknown settings.os={}".format(self.settings.os))

    def _get_configure_dir(self, build_system=None):
        if build_system is None:
            build_system = self._get_default_build_system()
        if build_system not in ["win", "unix", "macosx"]:
            raise ConanExceptionInUserConanfileMethod("Invalid build system: {}".format(build_system))
        return os.path.join(self.source_folder, self._source_subfolder, build_system)

    def _get_auto_tools(self):
        autoTools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
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
        if "d" not in self.settings.compiler.runtime:
            opts.append("unchecked")
        vcvars_command = tools.vcvars_command(self.settings)
        self.run(
            '{vcvars} && nmake -nologo -f "{cfgdir}/makefile.vc" shell INSTALLDIR="{pkgdir}" OPTS={opts} {target}'.format(
                vcvars=vcvars_command,
                cfgdir=self._get_configure_dir("win"),
                pkgdir=self.package_folder,
                opts=",".join(opts),
                target=target,
            ), cwd=self._get_configure_dir("win"),
        )

    def _build_autotools(self):
        conf_args = [
            "--enable-threads",
            "--enable-shared" if self.options.shared else "--disable-shared",
            "--enable-symbols" if self.settings.build_type == "Debug" else "--disable-symbols",
            "--enable-64bit" if self.settings.arch == "x86_64" else "--disable-64bit",
        ]
        autoTools = self._get_auto_tools()
        autoTools.configure(configure_dir=self._get_configure_dir(), args=conf_args, vars={"PKG_CFG_ARGS": " ".join(conf_args)})

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
                autoTools.make(target="install-private-headers")
            pkgconfig_dir = os.path.join(self.package_folder, "lib", "pkgconfig")
            if os.path.isdir(pkgconfig_dir):
                shutil.rmtree(pkgconfig_dir)
        self.copy(pattern="license.terms", dst="licenses", src=self._source_subfolder)

        tclConfigShPath = os.path.join(self.package_folder, "lib", "tclConfig.sh")
        package_path = os.path.join(self.package_folder)
        if self._is_mingw_windows:
            package_path = package_path.replace("\\", "/")
        tools.replace_in_file(tclConfigShPath,
                              package_path,
                              "${TCL_ROOT}")
        tools.replace_in_file(tclConfigShPath,
                              "\nTCL_BUILD_",
                              "\n#TCL_BUILD_")

        tools.replace_in_file(tclConfigShPath,
                              "\nTCL_SRC_DIR",
                              "\n#TCL_SRC_DIR")

    def package_info(self):
        libs = []
        libdirs = []
        for root, _, _ in os.walk(os.path.join(self.package_folder, "lib"), topdown=False):
            newlibs = tools.collect_libs(self, root)
            if newlibs:
                libs.extend(newlibs)
                libdirs.append(root)
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

        if self.settings.os == "Macos":
            self.cpp_info.exelinkflags.append("-framework Cocoa")
            self.cpp_info.sharedlinkflags = self.cpp_info.exelinkflags

        tcl_library = os.path.join(self.package_folder, "lib", "{}{}".format(self.name, ".".join(self.version.split(".")[:2])))
        self.output.info("Setting TCL_LIBRARY environment variable to {}".format(tcl_library))
        self.env_info.TCL_LIBRARY = tcl_library

        tcl_root = self.package_folder
        self.output.info("Setting TCL_ROOT environment variable to {}".format(tcl_root))
        self.env_info.TCL_ROOT = tcl_root

        tclsh_list = list(filter(lambda fn: fn.startswith("tclsh"), os.listdir(os.path.join(self.package_folder, "bin"))))
        assert(len(tclsh_list))
        tclsh = os.path.join(self.package_folder, "bin", tclsh_list[0])
        self.output.info("Setting TCLSH environment variable to {}".format(tclsh))
        self.env_info.TCLSH = tclsh

        bindir = os.path.join(self.package_folder, "bin")
        self.output.info("Adding PATH environment variable: {}".format(bindir))
        self.env_info.PATH.append(bindir)
