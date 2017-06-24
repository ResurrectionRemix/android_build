#
# Copyright (C) 2006 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Configuration for builds hosted on linux-x86.
# Included by combo/select.mk

ifeq ($(strip $($(combo_2nd_arch_prefix)HOST_TOOLCHAIN_PREFIX)),)
$(combo_2nd_arch_prefix)HOST_TOOLCHAIN_PREFIX := prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.15-4.8/bin/x86_64-linux-
endif
$(combo_2nd_arch_prefix)HOST_CC  := $($(combo_2nd_arch_prefix)HOST_TOOLCHAIN_PREFIX)gcc
$(combo_2nd_arch_prefix)HOST_CXX := $($(combo_2nd_arch_prefix)HOST_TOOLCHAIN_PREFIX)g++
$(combo_2nd_arch_prefix)HOST_AR  := $($(combo_2nd_arch_prefix)HOST_TOOLCHAIN_PREFIX)ar
$(combo_2nd_arch_prefix)HOST_READELF  := $($(combo_2nd_arch_prefix)HOST_TOOLCHAIN_PREFIX)readelf
$(combo_2nd_arch_prefix)HOST_NM  := $($(combo_2nd_arch_prefix)HOST_TOOLCHAIN_PREFIX)nm

define $(combo_var_prefix)transform-shared-lib-to-toc
$(call _gen_toc_command_for_elf,$(1),$(2))
endef

# gcc location for clang; to be updated when clang is updated
$(combo_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG := prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.15-4.8

# We expect SSE3 floating point math.
$(combo_2nd_arch_prefix)HOST_GLOBAL_CFLAGS += -msse3 -mfpmath=sse -m32 -Wa,--noexecstack -march=native
$(combo_2nd_arch_prefix)HOST_GLOBAL_LDFLAGS += -m32 -Wl,-z,noexecstack -Wl,-z,relro -Wl,-z,now -Wl,--no-undefined-version

ifneq ($(strip $(BUILD_HOST_static)),)
# Statically-linked binaries are desirable for sandboxed environment
$(combo_2nd_arch_prefix)HOST_GLOBAL_LDFLAGS += -static
endif # BUILD_HOST_static

$(combo_2nd_arch_prefix)HOST_GLOBAL_CFLAGS += -fPIC \
  -no-canonical-prefixes \

$(combo_2nd_arch_prefix)HOST_GLOBAL_CFLAGS += -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=2 -fstack-protector

# Workaround differences in inttypes.h between host and target.
# See bug 12708004.
$(combo_2nd_arch_prefix)HOST_GLOBAL_CFLAGS += -D__STDC_FORMAT_MACROS -D__STDC_CONSTANT_MACROS

# We build a 32-bit host art, and right now that also means building *all* host libraries
# both 32- and 64-bit (whether art uses them or not --- 9d59f417767991246848c3e101cb27d2dfea5988).
$(combo_2nd_arch_prefix)HOST_GLOBAL_CFLAGS += -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE=1

$(combo_2nd_arch_prefix)HOST_NO_UNDEFINED_LDFLAGS := -Wl,--no-undefined

############################################################
## Macros after this line are shared by the 64-bit config.

# $(1): The file to check
define get-file-size
stat --format "%s" "$(1)" | tr -d '\n'
endef
