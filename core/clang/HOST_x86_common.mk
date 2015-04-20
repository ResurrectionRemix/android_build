ifeq ($(HOST_OS),darwin)
# nothing required here yet
endif

ifeq ($(HOST_OS),linux)
CLANG_CONFIG_x86_LINUX_HOST_EXTRA_ASFLAGS := \
  --gcc-toolchain=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG) \
  --sysroot=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/sysroot \
  -no-integrated-as

CLANG_CONFIG_x86_LINUX_HOST_EXTRA_CFLAGS := \
	--gcc-toolchain=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG) \
	-no-integrated-as

ifeq ($(strip $(RROPTI)),true)
HOST_TOOLCHAIN_CLANG_VERSION :=4.8
else
HOST_TOOLCHAIN_CLANG_VERSION :=4.6
endif

ifneq ($(strip $($(clang_2nd_arch_prefix)HOST_IS_64_BIT)),)

CLANG_CONFIG_x86_LINUX_HOST_EXTRA_CPPFLAGS := \
	--gcc-toolchain=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG) \
	--sysroot=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/sysroot \
	-isystem $($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/x86_64-linux/include/c++/$(HOST_TOOLCHAIN_CLANG_VERSION) \
	-isystem $($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/x86_64-linux/include/c++/$(HOST_TOOLCHAIN_CLANG_VERSION)/x86_64-linux \
	-isystem $($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/x86_64-linux/include/c++/$(HOST_TOOLCHAIN_CLANG_VERSION)/backward \
	-no-integrated-as

CLANG_CONFIG_x86_LINUX_HOST_EXTRA_LDFLAGS := \
	--gcc-toolchain=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG) \
	--sysroot=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/sysroot \
	-B$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/x86_64-linux/bin \
	-L$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/x86_64-linux/lib64/ \
	-B$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/lib/gcc/x86_64-linux/$(HOST_TOOLCHAIN_CLANG_VERSION) \
	-L$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/lib/gcc/x86_64-linux/$(HOST_TOOLCHAIN_CLANG_VERSION) \
	-no-integrated-as

else #ifneq HOST_IS_64_BIT

CLANG_CONFIG_x86_LINUX_HOST_EXTRA_CPPFLAGS := \
	--gcc-toolchain=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG) \
	--sysroot=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/sysroot \
	-isystem $($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/x86_64-linux/include/c++/$(HOST_TOOLCHAIN_CLANG_VERSION) \
	-isystem $($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/x86_64-linux/include/c++/$(HOST_TOOLCHAIN_CLANG_VERSION)/x86_64-linux/32 \
	-isystem $($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/x86_64-linux/include/c++/$(HOST_TOOLCHAIN_CLANG_VERSION)/backward \
	-no-integrated-as

CLANG_CONFIG_x86_LINUX_HOST_EXTRA_LDFLAGS := \
	--gcc-toolchain=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG) \
	--sysroot=$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/sysroot \
	-B$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/x86_64-linux/bin \
	-B$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/lib/gcc/x86_64-linux/$(HOST_TOOLCHAIN_CLANG_VERSION)/32 \
	-L$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/lib/gcc/x86_64-linux/$(HOST_TOOLCHAIN_CLANG_VERSION)/32 \
	-L$($(clang_2nd_arch_prefix)HOST_TOOLCHAIN_FOR_CLANG)/x86_64-linux/lib32/ \
	-no-integrated-as
endif
endif  # Linux

ifeq ($(HOST_OS),windows)
# nothing required here yet
endif
