### Define path to toolchain
LLVM_PREBUILTS_PATH_QCOM := prebuilts/clang/linux-x86/host/llvm-Snapdragon_LLVM_for_Android_3.6/prebuilt/linux-x86_64/bin
LLVM_PREBUILTS_HEADER_PATH_QCOM := $(LLVM_PREBUILTS_PATH_QCOM)/../lib/clang/3.6.0/include/

CLANG_QCOM := $(LLVM_PREBUILTS_PATH_QCOM)/clang$(BUILD_EXECUTABLE_SUFFIX) -mllvm -aggressive-jt
CLANG_QCOM_CXX := $(LLVM_PREBUILTS_PATH_QCOM)/clang++$(BUILD_EXECUTABLE_SUFFIX) -mllvm -aggressive-jt

LLVM_AS := $(LLVM_PREBUILTS_PATH_QCOM)/llvm-as$(BUILD_EXECUTABLE_SUFFIX)
LLVM_LINK := $(LLVM_PREBUILTS_PATH_QCOM)/llvm-link$(BUILD_EXECUTABLE_SUFFIX)

CLANG_QCOM_CONFIG_EXTRA_TARGET_C_INCLUDES := $(LLVM_PREBUILTS_HEADER_PATH_QCOM)



### Defines for linking
libpath := $(LLVM_PREBUILTS_PATH_QCOM)/../lib/clang/3.6.0/lib

CLANG_QCOM_EXTRA_OPT_LIBGCC := \
  -L $(libpath)/linux/ \
  -l clang_rt.builtins-arm-android

CLANG_QCOM_EXTRA_OPT_LIBGCC_LINK := \
  $(libpath)/linux/libclang_rt.builtins-arm-android.a

CLANG_QCOM_EXTRA_OPT_LIBRARIES_LINK := \
  $(libpath)/linux-propri_rt/libclang_rt.optlibc-krait.a \
  $(libpath)/linux-propri_rt/libclang_rt.translib32.a

$(LOCAL_2ND_ARCH_VAR_PREFIX)TARGET_LIBGCC += $(CLANG_QCOM_EXTRA_OPT_LIBRARIES_LINK)



### Define compile flags
CLANG_QCOM_CONFIG_arm_TARGET_TRIPLE := armv7a-linux-androideabi

CLANG_QCOM_CONFIG_arm_TARGET_TOOLCHAIN_PREFIX := \
  $(TARGET_TOOLCHAIN_ROOT)/arm-linux-androideabi/bin

CLANG_QCOM_CONFIG_LLVM_DEFAULT_FLAGS := \
  -ffunction-sections \
  -no-canonical-prefixes \
  -fstack-protector \
  -funwind-tables
  #-fpic

CLANG_QCOM_CONFIG_LLVM_EXTRA_FLAGS := \
  -Qunused-arguments -Wno-unknown-warning-option -D__compiler_offsetof=__builtin_offsetof \
  -Wno-tautological-constant-out-of-range-compare \
  -fcolor-diagnostics \
  -fstrict-aliasing \
  -Wstrict-aliasing=2 \
  -Werror=strict-aliasing \
  -fuse-ld=gold \
  -Wno-missing-field-initializers \
  -Wno-unused-local-typedef \
  -Wno-inconsistent-missing-override \
  -Wno-null-dereference \
  -Wno-enum-compare
  #-Wno-unused-parameter -Wno-unused-variable -Wno-unused-but-set-variable

ifeq ($(TARGET_CPU_VARIANT),krait)
  clang_qcom_mcpu := -mcpu=krait -muse-optlibc
  clang_qcom_muse-optlibc := -muse-optlibc
  clang_qcom_mcpu_as := -mcpu=cortex-a15 -mfpu=neon-vfpv4 -mfloat-abi=softfp
else ifeq ($(TARGET_CPU_VARIANT),scorpion)
  clang_qcom_mcpu := -mcpu=scorpion
  clang_qcom_mcpu_as := -mcpu=cortex-a8 -mfpu=neon-vfpv3 -mfloat-abi=softfp
  clang_qcom_muse-optlibc :=
else
  $(info  )
  $(info QCOM_CLANG: warning no supported cpu detected.)
  $(exit)
endif

CLANG_QCOM_CONFIG_KRAIT_ALIGN_FLAGS := \
  -falign-functions -falign-labels -falign-loops

CLANG_QCOM_CONFIG_KRAIT_MEM_FLAGS := \
  -L $(libpath)/linux/ \
  -l clang_rt.optlibc-krait \
  -mllvm -arm-expand-memcpy-runtime=16 \
  -mllvm -arm-opt-memcpy=1 \
  $(clang_qcom_muse-optlibc)
  #-mllvm -arm-expand-memcpy-runtime=8
  #-mllvm -aggressive-jt

CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS :=\
  -L $(libpath)/linux-propri_rt/ \
  -l clang_rt.translib32 \
  -fparallel  

ifeq ($(USE_CLANG_QCOM_LTO),true)
  CLANG_QCOM_CONFIG_LTO_FLAGS := -flto 
  #-c-lto
endif

ifeq ($(USE_CLANG_QCOM_VERBOSE),true)
  CLANG_QCOM_VERBOSE := -v 
  #-ccc-print-phases \
  #-H
endif

# See documentation especialy 3.4.21 Math optimization.
CLANG_QCOM_CONFIG_KRAIT_FLAGS := \
  $(clang_qcom_mcpu) -mfpu=neon-vfpv4 -mfloat-abi=softfp -marm \
  -fvectorize-loops \
  -fomit-frame-pointer \
  -foptimize-sibling-calls \
  -funroll-loops \
  -ffinite-math-only \
  -funsafe-math-optimizations \
  -fdata-sections \
  $(CLANG_QCOM_CONFIG_LLVM_DEFAULT_FLAGS) \
  $(CLANG_QCOM_CONFIG_LLVM_EXTRA_FLAGS) \
  $(CLANG_QCOM_CONFIG_KRAIT_ALIGN_FLAGS) \
  $(CLANG_QCOM_CONFIG_KRAIT_MEM_FLAGS) \
  -ffp-contract=fast

#TODO:
#-ffp-contract=fast maybe too dangerous?

ifneq ($(USE_CLANG_QCOM_ONLY_ON_SELECTED_MODULES),true)
  CLANG_QCOM_CONFIG_KRAIT_FLAGS += $(CLANG_QCOM_CONFIG_KRAIT_MEM_FLAGS)
  USE_CLANG_QCOM_ONLY_ON_SELECTED_MODULES := false
endif


CLANG_QCOM_CONFIG_KRAIT_Ofast_FLAGS := \
  -Ofast -fno-fast-math \
  $(CLANG_QCOM_CONFIG_KRAIT_FLAGS)

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

### Define global flags
define subst-clang-qcom-incompatible-arm-flags
  $(subst -march=armv5te,-mcpu=krait,\
  $(subst -march=armv5e,-mcpu=krait,\
  $(subst -march=armv7,-mcpu=krait,\
  $(subst -march=armv7-a,-mcpu=krait,\
  $(subst -mcpu=cortex-a15,-mcpu=krait,\
  $(subst -mtune=cortex-a15,-mcpu=krait,\
  $(subst -mcpu=cortex-a8,-mcpu=scorpion,\
  $(subst -O3,-Ofast -fno-fast-math,\
  $(subst -O2,-Ofast -fno-fast-math,\
  $(subst -Os,-Ofast -fno-fast-math,\
  $(1)))))))))))
endef

define subst-clang-qcom-opt
  $(subst -O3,-Ofast -fno-fast-math,\
  $(subst -O2,-Ofast -fno-fast-math,\
  $(subst -O1,-Ofast -fno-fast-math,\
  $(subst -Os,-Ofast -fno-fast-math,\
  $(1)))))
endef

define convert-to-clang-qcom-flags
  $(strip \
  $(call subst-clang-qcom-incompatible-arm-flags,\
  $(filter-out $(CLANG_QCOM_CONFIG_arm_UNKNOWN_CFLAGS),\
  $(1))))
endef

define convert-to-clang-qcom-ldflags
  $(strip \
  $(filter-out $(CLANG_QCOM_CONFIG_arm_UNKNOWN_CFLAGS),\
  $(1)))
endef

CLANG_QCOM_CONFIG_arm_TARGET_EXTRA_CFLAGS := \
  -nostdlibinc \
  $(CLANG_QCOM_CONFIG_KRAIT_Ofast_FLAGS) \
  -B$(CLANG_QCOM_CONFIG_arm_TARGET_TOOLCHAIN_PREFIX) \
  -target $(CLANG_QCOM_CONFIG_arm_TARGET_TRIPLE) \
  $(CLANG_QCOM_VERBOSE)

CLANG_QCOM_CONFIG_arm_TARGET_EXTRA_CPPFLAGS := \
  -nostdlibinc \
  $(CLANG_QCOM_CONFIG_KRAIT_Ofast_FLAGS) \
  -target $(CLANG_QCOM_CONFIG_arm_TARGET_TRIPLE) \
  $(CLANG_QCOM_VERBOSE)

CLANG_QCOM_CONFIG_arm_TARGET_EXTRA_LDFLAGS := \
  $(CLANG_QCOM_CONFIG_LLVM_DEFAULT_FLAGS) \
  $(CLANG_QCOM_CONFIG_KRAIT_MEM_FLAGS) \
  $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS) \
  -B$(CLANG_QCOM_CONFIG_arm_TARGET_TOOLCHAIN_PREFIX) \
  -target $(CLANG_QCOM_CONFIG_arm_TARGET_TRIPLE) \
  $(CLANG_QCOM_VERBOSE)
  
CLANG_QCOM_TARGET_GLOBAL_CFLAGS := \
  $(call convert-to-clang-qcom-flags,$(TARGET_GLOBAL_CFLAGS)) \
  $(CLANG_QCOM_CONFIG_arm_TARGET_EXTRA_CFLAGS)

CLANG_QCOM_TARGET_GLOBAL_CPPFLAGS := \
  $(call convert-to-clang-qcom-flags,$(TARGET_GLOBAL_CPPFLAGS)) \
  $(CLANG_QCOM_CONFIG_arm_TARGET_EXTRA_CPPFLAGS)

CLANG_QCOM_TARGET_GLOBAL_LDFLAGS := \
  $(call convert-to-clang-qcom-flags,$(TARGET_GLOBAL_LDFLAGS)) \
  $(CLANG_QCOM_CONFIG_arm_TARGET_EXTRA_LDFLAGS) \
  -Wl,--gc-sections



### Define modules
ifeq ($(CLANG_QCOM_COMPILE_ART),true)
  CLANG_QCOM_ART_MODULES := \
          art \
          libsigchain \
          libart \
          libart-compiler \
          libartd \
          libartd-compiler \
          libart-disassembler \
          libartd-disassembler \
          core.art-host \
          core.art \
          cpplint-art-phony \
          libnativebridgetest \
          libarttest \
          art-run-tests \
          libart-gtest
else
  CLANG_QCOM_ART_MODULES :=
endif

ifeq ($(CLANG_QCOM_COMPILE_BIONIC),true)
  CLANG_QCOM_BIONIC_MODULES := \
    libc_cxa \
    libc_syscalls \
    libc_aeabi \
    libstdc++ \
    libc_nomalloc \
    libc_malloc \
    libc_bionic \
    libc \
    libc_common \
    libm \
    libc_stack_protector \
    libc_tzcode \
    libc_dns \
    libc_freebsd \
    libc_netbsd \
    libc_openbsd \
    libdl \
    libc_gdtoa

  CLANG_QCOM_BIONIC_MODULES_working := \
    libc_cxa \
    libc_syscalls \
    libc_aeabi \
    libstdc++ \
    libc_nomalloc \
    libc_malloc \
    libc_bionic \
    libc \
    libc_common \
    libm   
else
  CLANG_QCOM_BIONIC_MODULES :=
endif

ifeq ($(CLANG_QCOM_COMPILE_MIXED),true)
  CLANG_QCOM_EXTRA_MODULES := \
    libskia \
    libjpeg_static \
    libjpeg \
    cjpeg \
    djpeg \
    libft2 \
    libsqlite3_android \
    libsqlite \
    sqlite3 \
    libwebp-encode \
    libwebp-decode \
    libwebm \
    libz \
    libunz \
    gzip \
    libtruezip \
    liblz4-static \
    lz4 \
    liblzo-static \
    liblzo \
    zip \
    libbz \
    libwebp-encode \
    libwebp-decode \
    libstlport \
    libstlport_static
else
  CLANG_QCOM_EXTRA_MODULES :=
endif

ifeq ($(CLANG_QCOM_COMPILE_MORE_MIXED),true)
CLANG_QCOM_EXTRA_MODULES += \
  libion \
  lib_core_neon_offsets \
  libcompiler_rt \
  libgui \
  libui \
  hwcStress \
  hwcRects \
  hwcColorEquiv \
  hwcCommit \
  gralloc.default \
  hwcomposer.default \
  audio.primary.default \
  audio_policy.stub \
  liboverlay \
  math \
  libcv \
  libcvaux \
  libcvml \
  libcvhighgui \
  libopencv \
  libpixman \
  stagefright \
  record \
  recordvideo \
  screenrecord \
  codec \
  muxer \
  libdownmix \
  libeffects \
  libvisualizer \
  libmedia_helper \
  libaudioparameter \
  libmedia\
  decoder \
  libserviceutility \
  libaudioresampler \
  libaudio-resampler \
  libaudiopolicymanagerdefault \
  libaudiopolicymanager \
  libandroid_servers \
  servicemanager \
  surfaceflinger \
  halutil \
  libhardware \
  libqdMetaData \
  libhdmi \
  libqservice \
  memtrack.msm8974 \
  keystore.msm8974 \
  libOmxCore \
  libmm-omxcore \
  libstagefrighthw \
  libdashplayer \
  libutils \
  libgabi++ \
  libandroid
endif

# Here you can overwrite which modules should be compiled with QCOM CLANG instead of GCC
CLANG_QCOM_FORCE_COMPILE_MODULES += \
  $(CLANG_QCOM_ART_MODULES) \
  $(CLANG_QCOM_BIONIC_MODULES) \
  $(CLANG_QCOM_EXTRA_MODULES)

# Here you can overwrite which modules should be compiled with the default CLANG instead of QCOM CLANG
CLANG_QCOM_FORCE_COMPILE_ACLANG_MODULES +=

# -fparallel where to use? see 3.6.4
# Only use on selected modules. NOT USED AT THE MOMENT!
CLANG_QCOM_USE_PARALLEL_MODULES += \
  libpng \
  libsigchain \
  libcompiler_rt-extras \
  libcompiler_rt \
  $(ART_MODULES) \
  $(BIONIC_MODULES) \
  $(EXTRA_MODULES)

# Modules for language mode C++11
CLANG_QCOM_C++11_MODULES += \
  libjni_latinime_common_static \
  libjni_latinime

CLANG_QCOM_GNU++11_MODULES +=

# Dont use CLANG Assembler. Use GCC Assembler instead
# https://android-review.googlesource.com/#/c/110170/
# Skia doesnt like the CLANG assembler
CLANG_QCOM_DONT_USE_INTEGRATED_AS_MODULES += \
  libskia \
  libc++abi

CLANG_QCOM_DONT_REPLACE_WITH_Ofast_MODULES +=

# Workaround for modules where global definition of -Os ist overwritten with a higher optimization in local definition
CLANG_QCOM_NO-ALIGN-OS_MODULES += \
  libbccRenderscript \
  libLLVMSupport \
  libLLVMMC \
  libLLVMOption \
  libLLVMSupport \
  libLLVMMC \
  libLLVMTarget \
  libLLVMBitWriter_3_2 \
  libbcinfo \
  libbccCore \
  ndc \
  libnativebridge

CLANG_QCOM_NO-ALIGN-OS_MODULES :=
