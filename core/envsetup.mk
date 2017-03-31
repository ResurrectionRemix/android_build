# Variables we check:
#     HOST_BUILD_TYPE = { release debug }
#     TARGET_BUILD_TYPE = { release debug }
# and we output a bunch of variables, see the case statement at
# the bottom for the full list
#     OUT_DIR is also set to "out" if it's not already set.
#         this allows you to set it to somewhere else if you like
#     SCAN_EXCLUDE_DIRS is an optional, whitespace separated list of
#         directories that will also be excluded from full checkout tree
#         searches for source or make files, in addition to OUT_DIR.
#         This can be useful if you set OUT_DIR to be a different directory
#         than other outputs of your build system.

# Set up version information.
include $(BUILD_SYSTEM)/version_defaults.mk

# ---------------------------------------------------------------
# If you update the build system such that the environment setup
# or buildspec.mk need to be updated, increment this number, and
# people who haven't re-run those will have to do so before they
# can build.  Make sure to also update the corresponding value in
# buildspec.mk.default and envsetup.sh.
CORRECT_BUILD_ENV_SEQUENCE_NUMBER := 10

# ---------------------------------------------------------------
# The product defaults to generic on hardware
# NOTE: This will be overridden in product_config.mk if make
# was invoked with a PRODUCT-xxx-yyy goal.
ifeq ($(TARGET_PRODUCT),)
TARGET_PRODUCT := aosp_arm
endif


# the variant -- the set of files that are included for a build
ifeq ($(strip $(TARGET_BUILD_VARIANT)),)
TARGET_BUILD_VARIANT := eng
endif

# ---------------------------------------------------------------
# Set up configuration for host machine.  We don't do cross-
# compiles except for arm/mips, so the HOST is whatever we are
# running on

UNAME := $(shell uname -sm)

# HOST_OS
ifneq (,$(findstring Linux,$(UNAME)))
  HOST_OS := linux
endif
ifneq (,$(findstring Darwin,$(UNAME)))
  HOST_OS := darwin
endif
ifneq (,$(findstring Macintosh,$(UNAME)))
  HOST_OS := darwin
endif

HOST_OS_EXTRA:=$(shell python -c "import platform; print(platform.platform())")

# BUILD_OS is the real host doing the build.
BUILD_OS := $(HOST_OS)

HOST_CROSS_OS :=
# We can cross-build Windows binaries on Linux
ifeq ($(HOST_OS),linux)
HOST_CROSS_OS := windows
HOST_CROSS_ARCH := x86
HOST_CROSS_2ND_ARCH := x86_64
endif

ifeq ($(HOST_OS),)
$(error Unable to determine HOST_OS from uname -sm: $(UNAME)!)
endif

# HOST_ARCH
ifneq (,$(findstring x86_64,$(UNAME)))
  HOST_ARCH := x86_64
  HOST_2ND_ARCH := x86
  HOST_IS_64_BIT := true
else
ifneq (,$(findstring x86,$(UNAME)))
$(error Building on a 32-bit x86 host is not supported: $(UNAME)!)
endif
endif

BUILD_ARCH := $(HOST_ARCH)
BUILD_2ND_ARCH := $(HOST_2ND_ARCH)

ifeq ($(HOST_ARCH),)
$(error Unable to determine HOST_ARCH from uname -sm: $(UNAME)!)
endif

# the host build defaults to release, and it must be release or debug
ifeq ($(HOST_BUILD_TYPE),)
HOST_BUILD_TYPE := release
endif

ifneq ($(HOST_BUILD_TYPE),release)
ifneq ($(HOST_BUILD_TYPE),debug)
$(error HOST_BUILD_TYPE must be either release or debug, not '$(HOST_BUILD_TYPE)')
endif
endif

# We don't want to move all the prebuilt host tools to a $(HOST_OS)-x86_64 dir.
HOST_PREBUILT_ARCH := x86
# This is the standard way to name a directory containing prebuilt host
# objects. E.g., prebuilt/$(HOST_PREBUILT_TAG)/cc
HOST_PREBUILT_TAG := $(BUILD_OS)-$(HOST_PREBUILT_ARCH)

# TARGET_COPY_OUT_* are all relative to the staging directory, ie PRODUCT_OUT.
# Define them here so they can be used in product config files.
TARGET_COPY_OUT_SYSTEM := system
TARGET_COPY_OUT_SYSTEM_OTHER := system_other
TARGET_COPY_OUT_DATA := data
TARGET_COPY_OUT_OEM := oem
TARGET_COPY_OUT_ODM := odm
TARGET_COPY_OUT_ROOT := root
TARGET_COPY_OUT_RECOVERY := recovery
###########################################
# Define TARGET_COPY_OUT_VENDOR to a placeholder, for at this point
# we don't know if the device wants to build a separate vendor.img
# or just build vendor stuff into system.img.
# A device can set up TARGET_COPY_OUT_VENDOR to "vendor" in its
# BoardConfig.mk.
# We'll substitute with the real value after loading BoardConfig.mk.
_vendor_path_placeholder := ||VENDOR-PATH-PH||
TARGET_COPY_OUT_VENDOR := $(_vendor_path_placeholder)
###########################################

# Read the product specs so we can get TARGET_DEVICE and other
# variables that we need in order to locate the output files.
include $(BUILD_SYSTEM)/product_config.mk

build_variant := $(filter-out eng user userdebug,$(TARGET_BUILD_VARIANT))
ifneq ($(build_variant)-$(words $(TARGET_BUILD_VARIANT)),-1)
$(warning bad TARGET_BUILD_VARIANT: $(TARGET_BUILD_VARIANT))
$(error must be empty or one of: eng user userdebug)
endif

SDK_HOST_ARCH := x86

# Boards may be defined under $(SRC_TARGET_DIR)/board/$(TARGET_DEVICE)
# or under vendor/*/$(TARGET_DEVICE).  Search in both places, but
# make sure only one exists.
# Real boards should always be associated with an OEM vendor.
board_config_mk := \
	$(strip $(sort $(wildcard \
		$(SRC_TARGET_DIR)/board/$(TARGET_DEVICE)/BoardConfig.mk \
		$(shell test -d device && find -L device -maxdepth 4 -path '*/$(TARGET_DEVICE)/BoardConfig.mk') \
		$(shell test -d vendor && find -L vendor -maxdepth 4 -path '*/$(TARGET_DEVICE)/BoardConfig.mk') \
	)))
ifeq ($(board_config_mk),)
  $(error No config file found for TARGET_DEVICE $(TARGET_DEVICE))
endif
ifneq ($(words $(board_config_mk)),1)
  $(error Multiple board config files for TARGET_DEVICE $(TARGET_DEVICE): $(board_config_mk))
endif
include $(board_config_mk)
ifeq ($(TARGET_ARCH),)
  $(error TARGET_ARCH not defined by board config: $(board_config_mk))
endif
ifneq ($(MALLOC_IMPL),)
  $(warning *** Unsupported option MALLOC_IMPL defined by board config: $(board_config_mk).)
  $(error Use `MALLOC_SVELTE := true` to configure jemalloc for low-memory)
endif
TARGET_DEVICE_DIR := $(patsubst %/,%,$(dir $(board_config_mk)))
board_config_mk :=

###########################################
# Now we can substitute with the real value of TARGET_COPY_OUT_VENDOR
ifeq ($(TARGET_COPY_OUT_VENDOR),$(_vendor_path_placeholder))
TARGET_COPY_OUT_VENDOR := system/vendor
else ifeq ($(filter vendor system/vendor system,$(TARGET_COPY_OUT_VENDOR)),)
$(error TARGET_COPY_OUT_VENDOR must be either 'vendor', 'system/vendor' or 'system', seeing '$(TARGET_COPY_OUT_VENDOR)'.)
endif
PRODUCT_COPY_FILES := $(subst $(_vendor_path_placeholder),$(TARGET_COPY_OUT_VENDOR),$(PRODUCT_COPY_FILES))

BOARD_USES_VENDORIMAGE :=
ifdef BOARD_PREBUILT_VENDORIMAGE
BOARD_USES_VENDORIMAGE := true
endif
ifdef BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE
BOARD_USES_VENDORIMAGE := true
endif
ifeq ($(TARGET_COPY_OUT_VENDOR),vendor)
BOARD_USES_VENDORIMAGE := true
else ifdef BOARD_USES_VENDORIMAGE
$(error TARGET_COPY_OUT_VENDOR must be set to 'vendor' to use a vendor image)
endif
###########################################


# ---------------------------------------------------------------
# Set up configuration for target machine.
# The following must be set:
# 		TARGET_OS = { linux }
# 		TARGET_ARCH = { arm | x86 | mips }

TARGET_OS := linux
# TARGET_ARCH should be set by BoardConfig.mk and will be checked later
ifneq ($(filter %64,$(TARGET_ARCH)),)
TARGET_IS_64_BIT := true
endif

# the target build type defaults to release
ifneq ($(TARGET_BUILD_TYPE),debug)
TARGET_BUILD_TYPE := release
endif

# ---------------------------------------------------------------
# figure out the output directories

ifeq (,$(strip $(OUT_DIR)))
ifeq (,$(strip $(OUT_DIR_COMMON_BASE)))
ifneq ($(TOPDIR),)
OUT_DIR := $(TOPDIR)out
else
OUT_DIR := $(CURDIR)/out
endif
else
OUT_DIR := $(OUT_DIR_COMMON_BASE:/=)/$(notdir $(PWD))
endif
endif

DEBUG_OUT_DIR := $(OUT_DIR)/debug

# Move the host or target under the debug/ directory
# if necessary.
TARGET_OUT_ROOT_release := $(OUT_DIR)/target
TARGET_OUT_ROOT_debug := $(DEBUG_OUT_DIR)/target
TARGET_OUT_ROOT := $(TARGET_OUT_ROOT_$(TARGET_BUILD_TYPE))

HOST_OUT_ROOT_release := $(OUT_DIR)/host
HOST_OUT_ROOT_debug := $(DEBUG_OUT_DIR)/host
HOST_OUT_ROOT := $(HOST_OUT_ROOT_$(HOST_BUILD_TYPE))

# We want to avoid two host bin directories in multilib build.
HOST_OUT_release := $(HOST_OUT_ROOT_release)/$(HOST_OS)-$(HOST_PREBUILT_ARCH)
HOST_OUT_debug := $(HOST_OUT_ROOT_debug)/$(HOST_OS)-$(HOST_PREBUILT_ARCH)
HOST_OUT := $(HOST_OUT_$(HOST_BUILD_TYPE))
# TODO: remove
BUILD_OUT := $(HOST_OUT)

HOST_CROSS_OUT_release := $(HOST_OUT_ROOT_release)/windows-$(HOST_PREBUILT_ARCH)
HOST_CROSS_OUT_debug := $(HOST_OUT_ROOT_debug)/windows-$(HOST_PREBUILT_ARCH)
HOST_CROSS_OUT := $(HOST_CROSS_OUT_$(HOST_BUILD_TYPE))

TARGET_PRODUCT_OUT_ROOT := $(TARGET_OUT_ROOT)/product

TARGET_COMMON_OUT_ROOT := $(TARGET_OUT_ROOT)/common
HOST_COMMON_OUT_ROOT := $(HOST_OUT_ROOT)/common

PRODUCT_OUT := $(TARGET_PRODUCT_OUT_ROOT)/$(TARGET_DEVICE)

OUT_DOCS := $(TARGET_COMMON_OUT_ROOT)/docs

BUILD_OUT_EXECUTABLES := $(BUILD_OUT)/bin

HOST_OUT_EXECUTABLES := $(HOST_OUT)/bin
HOST_OUT_SHARED_LIBRARIES := $(HOST_OUT)/lib64
HOST_OUT_RENDERSCRIPT_BITCODE := $(HOST_OUT_SHARED_LIBRARIES)
HOST_OUT_JAVA_LIBRARIES := $(HOST_OUT)/framework
HOST_OUT_SDK_ADDON := $(HOST_OUT)/sdk_addon

HOST_CROSS_OUT_EXECUTABLES := $(HOST_CROSS_OUT)/bin
HOST_CROSS_OUT_SHARED_LIBRARIES := $(HOST_CROSS_OUT)/lib

HOST_OUT_INTERMEDIATES := $(HOST_OUT)/obj
HOST_OUT_HEADERS := $(HOST_OUT_INTERMEDIATES)/include
HOST_OUT_INTERMEDIATE_LIBRARIES := $(HOST_OUT_INTERMEDIATES)/lib
HOST_OUT_NOTICE_FILES := $(HOST_OUT_INTERMEDIATES)/NOTICE_FILES
HOST_OUT_COMMON_INTERMEDIATES := $(HOST_COMMON_OUT_ROOT)/obj
HOST_OUT_FAKE := $(HOST_OUT)/fake_packages

HOST_CROSS_OUT_INTERMEDIATES := $(HOST_CROSS_OUT)/obj
HOST_CROSS_OUT_HEADERS := $(HOST_CROSS_OUT_INTERMEDIATES)/include
HOST_CROSS_OUT_INTERMEDIATE_LIBRARIES := $(HOST_CROSS_OUT_INTERMEDIATES)/lib
HOST_CROSS_OUT_NOTICE_FILES := $(HOST_CROSS_OUT_INTERMEDIATES)/NOTICE_FILES

HOST_OUT_GEN := $(HOST_OUT)/gen
HOST_OUT_COMMON_GEN := $(HOST_COMMON_OUT_ROOT)/gen

HOST_CROSS_OUT_GEN := $(HOST_CROSS_OUT)/gen

# Out for HOST_2ND_ARCH
HOST_2ND_ARCH_VAR_PREFIX := 2ND_
HOST_2ND_ARCH_MODULE_SUFFIX := _32
$(HOST_2ND_ARCH_VAR_PREFIX)HOST_OUT_INTERMEDIATES := $(HOST_OUT)/obj32
$(HOST_2ND_ARCH_VAR_PREFIX)HOST_OUT_INTERMEDIATE_LIBRARIES := $($(HOST_2ND_ARCH_VAR_PREFIX)HOST_OUT_INTERMEDIATES)/lib
$(HOST_2ND_ARCH_VAR_PREFIX)HOST_OUT_SHARED_LIBRARIES := $(HOST_OUT)/lib
$(HOST_2ND_ARCH_VAR_PREFIX)HOST_OUT_EXECUTABLES := $(HOST_OUT_EXECUTABLES)
$(HOST_2ND_ARCH_VAR_PREFIX)HOST_OUT_JAVA_LIBRARIES := $(HOST_OUT_JAVA_LIBRARIES)

# The default host library path.
# It always points to the path where we build libraries in the default bitness.
ifeq ($(HOST_PREFER_32_BIT),true)
HOST_LIBRARY_PATH := $($(HOST_2ND_ARCH_VAR_PREFIX)HOST_OUT_SHARED_LIBRARIES)
else
HOST_LIBRARY_PATH := $(HOST_OUT_SHARED_LIBRARIES)
endif

# Out for HOST_CROSS_2ND_ARCH
HOST_CROSS_2ND_ARCH_VAR_PREFIX := 2ND_
HOST_CROSS_2ND_ARCH_MODULE_SUFFIX := _64
$(HOST_CROSS_2ND_ARCH_VAR_PREFIX)HOST_CROSS_OUT_INTERMEDIATES := $(HOST_CROSS_OUT)/obj64
$(HOST_CROSS_2ND_ARCH_VAR_PREFIX)HOST_CROSS_OUT_INTERMEDIATE_LIBRARIES := $($(HOST_CROSS_2ND_ARCH_VAR_PREFIX)HOST_CROSS_OUT_INTERMEDIATES)/lib
$(HOST_CROSS_2ND_ARCH_VAR_PREFIX)HOST_CROSS_OUT_SHARED_LIBRARIES := $(HOST_CROSS_OUT)/lib64
$(HOST_CROSS_2ND_ARCH_VAR_PREFIX)HOST_CROSS_OUT_EXECUTABLES := $(HOST_CROSS_OUT_EXECUTABLES)

TARGET_OUT_INTERMEDIATES := $(PRODUCT_OUT)/obj
TARGET_OUT_HEADERS := $(TARGET_OUT_INTERMEDIATES)/include
TARGET_OUT_INTERMEDIATE_LIBRARIES := $(TARGET_OUT_INTERMEDIATES)/lib
TARGET_OUT_COMMON_INTERMEDIATES := $(TARGET_COMMON_OUT_ROOT)/obj

TARGET_OUT_GEN := $(PRODUCT_OUT)/gen
TARGET_OUT_COMMON_GEN := $(TARGET_COMMON_OUT_ROOT)/gen

TARGET_OUT := $(PRODUCT_OUT)/$(TARGET_COPY_OUT_SYSTEM)
ifneq ($(filter address,$(SANITIZE_TARGET)),)
target_out_shared_libraries_base := $(PRODUCT_OUT)/$(TARGET_COPY_OUT_DATA)
else
target_out_shared_libraries_base := $(TARGET_OUT)
endif

TARGET_OUT_EXECUTABLES := $(TARGET_OUT)/bin
TARGET_OUT_OPTIONAL_EXECUTABLES := $(TARGET_OUT)/xbin
ifeq ($(TARGET_IS_64_BIT),true)
# /system/lib always contains 32-bit libraries,
# and /system/lib64 (if present) always contains 64-bit libraries.
TARGET_OUT_SHARED_LIBRARIES := $(target_out_shared_libraries_base)/lib64
else
TARGET_OUT_SHARED_LIBRARIES := $(target_out_shared_libraries_base)/lib
endif
TARGET_OUT_RENDERSCRIPT_BITCODE := $(TARGET_OUT_SHARED_LIBRARIES)
TARGET_OUT_JAVA_LIBRARIES := $(TARGET_OUT)/framework
TARGET_OUT_APPS := $(TARGET_OUT)/app
TARGET_OUT_APPS_PRIVILEGED := $(TARGET_OUT)/priv-app
TARGET_OUT_KEYLAYOUT := $(TARGET_OUT)/usr/keylayout
TARGET_OUT_KEYCHARS := $(TARGET_OUT)/usr/keychars
TARGET_OUT_ETC := $(TARGET_OUT)/etc
TARGET_OUT_NOTICE_FILES := $(TARGET_OUT_INTERMEDIATES)/NOTICE_FILES
TARGET_OUT_FAKE := $(PRODUCT_OUT)/fake_packages

TARGET_OUT_SYSTEM_OTHER := $(PRODUCT_OUT)/$(TARGET_COPY_OUT_SYSTEM_OTHER)

# Out for TARGET_2ND_ARCH
TARGET_2ND_ARCH_VAR_PREFIX := $(HOST_2ND_ARCH_VAR_PREFIX)
TARGET_2ND_ARCH_MODULE_SUFFIX := $(HOST_2ND_ARCH_MODULE_SUFFIX)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_INTERMEDIATES := $(PRODUCT_OUT)/obj_$(TARGET_2ND_ARCH)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_INTERMEDIATE_LIBRARIES := $($(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_INTERMEDIATES)/lib
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_SHARED_LIBRARIES := $(target_out_shared_libraries_base)/lib
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_RENDERSCRIPT_BITCODE := $($(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_SHARED_LIBRARIES)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_EXECUTABLES := $(TARGET_OUT_EXECUTABLES)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_APPS := $(TARGET_OUT_APPS)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_APPS_PRIVILEGED := $(TARGET_OUT_APPS_PRIVILEGED)

TARGET_OUT_DATA := $(PRODUCT_OUT)/$(TARGET_COPY_OUT_DATA)
TARGET_OUT_DATA_EXECUTABLES := $(TARGET_OUT_EXECUTABLES)
TARGET_OUT_DATA_SHARED_LIBRARIES := $(TARGET_OUT_SHARED_LIBRARIES)
TARGET_OUT_DATA_JAVA_LIBRARIES := $(TARGET_OUT_DATA)/framework
TARGET_OUT_DATA_APPS := $(TARGET_OUT_DATA)/app
TARGET_OUT_DATA_KEYLAYOUT := $(TARGET_OUT_KEYLAYOUT)
TARGET_OUT_DATA_KEYCHARS := $(TARGET_OUT_KEYCHARS)
TARGET_OUT_DATA_ETC := $(TARGET_OUT_ETC)
ifeq ($(TARGET_IS_64_BIT),true)
TARGET_OUT_DATA_NATIVE_TESTS := $(TARGET_OUT_DATA)/nativetest64
TARGET_OUT_DATA_METRIC_TESTS := $(TARGET_OUT_DATA)/benchmarktest64
else
TARGET_OUT_DATA_NATIVE_TESTS := $(TARGET_OUT_DATA)/nativetest
TARGET_OUT_DATA_METRIC_TESTS := $(TARGET_OUT_DATA)/benchmarktest
endif
TARGET_OUT_DATA_FAKE := $(TARGET_OUT_DATA)/fake_packages

$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_DATA_EXECUTABLES := $(TARGET_OUT_DATA_EXECUTABLES)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_DATA_SHARED_LIBRARIES := $($(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_SHARED_LIBRARIES)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_DATA_APPS := $(TARGET_OUT_DATA_APPS)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_DATA_NATIVE_TESTS := $(TARGET_OUT_DATA)/nativetest
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_DATA_METRIC_TESTS := $(TARGET_OUT_DATA)/benchmarktest

TARGET_OUT_CACHE := $(PRODUCT_OUT)/cache

TARGET_OUT_VENDOR := $(PRODUCT_OUT)/$(TARGET_COPY_OUT_VENDOR)
ifneq ($(filter address,$(SANITIZE_TARGET)),)
target_out_vendor_shared_libraries_base := $(PRODUCT_OUT)/$(TARGET_COPY_OUT_DATA)/vendor
else
target_out_vendor_shared_libraries_base := $(TARGET_OUT_VENDOR)
endif

TARGET_OUT_VENDOR_EXECUTABLES := $(TARGET_OUT_VENDOR)/bin
TARGET_OUT_VENDOR_OPTIONAL_EXECUTABLES := $(TARGET_OUT_VENDOR)/xbin
ifeq ($(TARGET_IS_64_BIT),true)
TARGET_OUT_VENDOR_SHARED_LIBRARIES := $(target_out_vendor_shared_libraries_base)/lib64
else
TARGET_OUT_VENDOR_SHARED_LIBRARIES := $(target_out_vendor_shared_libraries_base)/lib
endif
TARGET_OUT_VENDOR_JAVA_LIBRARIES := $(TARGET_OUT_VENDOR)/framework
TARGET_OUT_VENDOR_APPS := $(TARGET_OUT_VENDOR)/app
TARGET_OUT_VENDOR_ETC := $(TARGET_OUT_VENDOR)/etc

$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_VENDOR_EXECUTABLES := $(TARGET_OUT_VENDOR_EXECUTABLES)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_VENDOR_SHARED_LIBRARIES := $(target_out_vendor_shared_libraries_base)/lib
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_VENDOR_APPS := $(TARGET_OUT_VENDOR_APPS)

TARGET_OUT_OEM := $(PRODUCT_OUT)/$(TARGET_COPY_OUT_OEM)
TARGET_OUT_OEM_EXECUTABLES := $(TARGET_OUT_OEM)/bin
ifeq ($(TARGET_IS_64_BIT),true)
TARGET_OUT_OEM_SHARED_LIBRARIES := $(TARGET_OUT_OEM)/lib64
else
TARGET_OUT_OEM_SHARED_LIBRARIES := $(TARGET_OUT_OEM)/lib
endif
# We don't expect Java libraries in the oem.img.
# TARGET_OUT_OEM_JAVA_LIBRARIES:= $(TARGET_OUT_OEM)/framework
TARGET_OUT_OEM_APPS := $(TARGET_OUT_OEM)/app
TARGET_OUT_OEM_ETC := $(TARGET_OUT_OEM)/etc

$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_OEM_EXECUTABLES := $(TARGET_OUT_OEM_EXECUTABLES)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_OEM_SHARED_LIBRARIES := $(TARGET_OUT_OEM)/lib
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_OEM_APPS := $(TARGET_OUT_OEM_APPS)

TARGET_OUT_ODM := $(PRODUCT_OUT)/$(TARGET_COPY_OUT_ODM)
TARGET_OUT_ODM_EXECUTABLES := $(TARGET_OUT_ODM)/bin
ifeq ($(TARGET_IS_64_BIT),true)
TARGET_OUT_ODM_SHARED_LIBRARIES := $(TARGET_OUT_ODM)/lib64
else
TARGET_OUT_ODM_SHARED_LIBRARIES := $(TARGET_OUT_ODM)/lib
endif
TARGET_OUT_ODM_APPS := $(TARGET_OUT_ODM)/app
TARGET_OUT_ODM_ETC := $(TARGET_OUT_ODM)/etc

$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_ODM_EXECUTABLES := $(TARGET_OUT_ODM_EXECUTABLES)
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_ODM_SHARED_LIBRARIES := $(TARGET_OUT_ODM)/lib
$(TARGET_2ND_ARCH_VAR_PREFIX)TARGET_OUT_ODM_APPS := $(TARGET_OUT_ODM_APPS)

TARGET_OUT_BREAKPAD := $(PRODUCT_OUT)/breakpad

TARGET_OUT_UNSTRIPPED := $(PRODUCT_OUT)/symbols
TARGET_OUT_EXECUTABLES_UNSTRIPPED := $(TARGET_OUT_UNSTRIPPED)/system/bin
TARGET_OUT_SHARED_LIBRARIES_UNSTRIPPED := $(TARGET_OUT_UNSTRIPPED)/system/lib
TARGET_OUT_VENDOR_SHARED_LIBRARIES_UNSTRIPPED := $(TARGET_OUT_UNSTRIPPED)/$(TARGET_COPY_OUT_VENDOR)/lib
TARGET_ROOT_OUT_UNSTRIPPED := $(TARGET_OUT_UNSTRIPPED)
TARGET_ROOT_OUT_SBIN_UNSTRIPPED := $(TARGET_OUT_UNSTRIPPED)/sbin
TARGET_ROOT_OUT_BIN_UNSTRIPPED := $(TARGET_OUT_UNSTRIPPED)/bin

TARGET_ROOT_OUT := $(PRODUCT_OUT)/$(TARGET_COPY_OUT_ROOT)
TARGET_ROOT_OUT_BIN := $(TARGET_ROOT_OUT)/bin
TARGET_ROOT_OUT_SBIN := $(TARGET_ROOT_OUT)/sbin
TARGET_ROOT_OUT_ETC := $(TARGET_ROOT_OUT)/etc
TARGET_ROOT_OUT_USR := $(TARGET_ROOT_OUT)/usr

TARGET_RECOVERY_OUT := $(PRODUCT_OUT)/$(TARGET_COPY_OUT_RECOVERY)
TARGET_RECOVERY_ROOT_OUT := $(TARGET_RECOVERY_OUT)/root

TARGET_SYSLOADER_OUT := $(PRODUCT_OUT)/sysloader
TARGET_SYSLOADER_ROOT_OUT := $(TARGET_SYSLOADER_OUT)/root
TARGET_SYSLOADER_SYSTEM_OUT := $(TARGET_SYSLOADER_OUT)/root/system

TARGET_INSTALLER_OUT := $(PRODUCT_OUT)/installer
TARGET_INSTALLER_DATA_OUT := $(TARGET_INSTALLER_OUT)/data
TARGET_INSTALLER_ROOT_OUT := $(TARGET_INSTALLER_OUT)/root
TARGET_INSTALLER_SYSTEM_OUT := $(TARGET_INSTALLER_OUT)/root/system

COMMON_MODULE_CLASSES := TARGET-NOTICE_FILES HOST-NOTICE_FILES HOST-JAVA_LIBRARIES
PER_ARCH_MODULE_CLASSES := SHARED_LIBRARIES STATIC_LIBRARIES EXECUTABLES GYP RENDERSCRIPT_BITCODE

ifeq (,$(strip $(DIST_DIR)))
  DIST_DIR := $(OUT_DIR)/dist
endif

ifeq ($(PRINT_BUILD_CONFIG),)
PRINT_BUILD_CONFIG := true
endif

ifeq ($(USE_CLANG_PLATFORM_BUILD),)
USE_CLANG_PLATFORM_BUILD := true
endif
