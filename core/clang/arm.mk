# Clang flags for arm arch, target or host.

CLANG_CONFIG_arm_EXTRA_ASFLAGS := \
  -no-integrated-as

CLANG_CONFIG_arm_EXTRA_CFLAGS := \
  -no-integrated-as

CLANG_CONFIG_arm_EXTRA_CPPFLAGS := \
  -no-integrated-as

CLANG_CONFIG_arm_EXTRA_LDFLAGS := \
  -no-integrated-as

# Include common unknown flags
CLANG_CONFIG_arm_UNKNOWN_CFLAGS := \
  $(CLANG_CONFIG_UNKNOWN_CFLAGS) \
  -mthumb-interwork \
  -fgcse-after-reload \
  -frerun-cse-after-loop \
  -frename-registers \
  -fno-builtin-sin \
  -fno-strict-volatile-bitfields \
  -fno-align-jumps \
  -Wa,--noexecstack

define subst-clang-incompatible-arm-flags
  $(subst -march=armv5te,-march=armv5t,\
  $(subst -march=armv5e,-march=armv5,\
  $(subst -mcpu=cortex-a15,-march=armv7-a,\
  $(1))))
endef
<<<<<<< HEAD
=======

# QUALCOMM CLANG
CLANG_QCOM_CONFIG_arm_UNKNOWN_CFLAGS := \
-fipa-pta \
-fsection-anchors \
-ftree-loop-im \
-ftree-loop-ivcanon \
-fno-canonical-system-headers \
-frerun-cse-after-loop \
-fgcse-las \
-fgcse-sm \
-fivopts \
-frename-registers \
-ftracer \
-funsafe-loop-optimizations \
-funswitch-loops \
-fweb \
-fgcse-after-reload \
-frename-registers \
-finline-functions \
-fno-strict-volatile-bitfields \
-fno-unswitch-loops \
-fno-if-conversion

define subst-clang-qcom-incompatible-arm-flags
  $(subst -march=armv5te,-mcpu=krait,\
  $(subst -march=armv5e,-mcpu=krait,\
  $(subst -march=armv7,-mcpu=krait,\
  $(subst -march=armv7-a,-mcpu=krait,\
  $(subst -mcpu=cortex-a15,-mcpu=krait,\
  $(subst -mtune=cortex-a15,-mcpu=krait,\
  $(subst -mfpu=cortex-a8,-mcpu=scorpion,\
  $(subst -O3,-Ofast -fno-fast-math,\
  $(subst -Os,-Os -falign-os,\
  $(subst -mfpu=neon,-mfpu=neon-vfpv4,\
  $(1)))))))))))
endef
>>>>>>> fc21499... qcom-clang: fixed build
