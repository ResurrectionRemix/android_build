ifneq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_DONT_USE_MODULES)))
  $(LOCAL_2ND_ARCH_VAR_PREFIX)TARGET_LIBGCC += $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES_LINK)

  my_target_c_includes += $(CLANG_QCOM_CONFIG_EXTRA_TARGET_C_INCLUDES)
  my_target_global_cflags := $(CLANG_QCOM_TARGET_GLOBAL_CFLAGS)
  my_target_global_cppflags := $(CLANG_QCOM_TARGET_GLOBAL_CPPFLAGS)
  my_target_global_ldflags := $(CLANG_QCOM_TARGET_GLOBAL_LDFLAGS)
  my_cflags_CLANG_QCOM := $(call convert-to-clang-qcom-flags,$(my_cflags)) $(CLANG_QCOM_CONFIG_KRAIT_FLAGS)
  my_cppflags_CLANG_QCOM := $(call convert-to-clang-qcom-flags,$(my_cppflags)) $(CLANG_QCOM_CONFIG_KRAIT_FLAGS)
  my_asflags_CLANG_QCOM := $(my_asflags) $(CLANG_QCOM_CONFIG_KRAIT_FLAGS) 
  my_ldflags_CLANG_QCOM := $(my_ldflags) $(CLANG_QCOM_CONFIG_KRAIT_FLAGS)
  LOCAL_CONLYFLAGS := $(call convert-to-clang-qcom-flags,$(LOCAL_CONLYFLAGS)) $(CLANG_QCOM_CONFIG_KRAIT_FLAGS)
  arm_objects_cflags_CLANG_QCOM := $(call convert-to-clang-qcom-flags,$($(LOCAL_2ND_ARCH_VAR_PREFIX)$(my_prefix)$(arm_objects_mode)_CFLAGS)) $(CLANG_QCOM_CONFIG_KRAIT_FLAGS) -marm
  normal_objects_cflags_CLANG_QCOM := $(call convert-to-clang-qcom-flags,$($(LOCAL_2ND_ARCH_VAR_PREFIX)$(my_prefix)$(normal_objects_mode)_CFLAGS)) $(CLANG_QCOM_CONFIG_KRAIT_FLAGS)

  #lto
  ifeq ($(USE_CLANG_QCOM_LTO),true)
    ifneq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_DONT_USE_LTO_MODULES)))
      my_shared_libraries += libLTO
      my_target_global_cflags += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_LTO_FLAGS)
      my_target_global_cppflags += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_LTO_FLAGS)
      my_target_global_ldflags += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_LTO_FLAGS)
      my_cflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_LTO_FLAGS)
      my_cppflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_LTO_FLAGS)
      my_asflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_LTO_FLAGS)
      my_ldflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_LTO_FLAGS)
      LOCAL_CONLYFLAGS  += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_LTO_FLAGS)
    endif
  endif

  #parallel
  ifeq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_USE_PARALLEL_MODULES)))
    my_target_global_cflags += -fparallel
    my_target_global_cppflags += -fparallel
    my_target_global_ldflags += -fparallel
    my_cflags_CLANG_QCOM += -fparallel
    my_cppflags_CLANG_QCOM += -fparallel
    my_asflags_CLANG_QCOM += -fparallel
    my_ldflags_CLANG_QCOM += -fparallel
    LOCAL_CONLYFLAGS  += -fparallel
    arm_objects_cflags_CLANG_QCOM += -fparallel
    normal_objects_cflags_CLANG_QCOM += -fparallel
  endif

  ifneq ($(LOCAL_MODULE),libc++)
    my_static_libraries += libclang_rt.optlibc-krait libclang_rt.translib32
    my_target_global_cflags += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
    my_target_global_cppflags += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS)  $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
    my_target_global_ldflags += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
    my_cflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
    my_cppflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
    my_asflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
    my_ldflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
    LOCAL_CONLYFLAGS  += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
    arm_objects_cflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
    normal_objects_cflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
  else
    #workaround for shared libc++
    ifneq (libc++,$(LOCAL_WHOLE_STATIC_LIBRARIES))
      my_static_libraries += libclang_rt.optlibc-krait libclang_rt.translib32
      my_target_global_cflags += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
      my_target_global_cppflags += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS)  $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
      my_target_global_ldflags += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
      my_cflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
      my_cppflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
      my_asflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
      my_ldflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
      LOCAL_CONLYFLAGS  += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
      arm_objects_cflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
      normal_objects_cflags_CLANG_QCOM += $(CLANG_QCOM_CONFIG_EXTRA_KRAIT_MEM_FLAGS) $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBRARIES)
    endif
  endif

  #ifneq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_NEED_LIBGCC_MODULES)))
  #  my_static_libraries += libclang_rt.builtins-arm-android #libclang_rt.profile-armv7 libclang_rt.profile-arm-android
  #  my_target_global_cflags += $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBGCC)
  #  my_target_global_cppflags += $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBGCC)
  #  my_target_global_ldflags += $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBGCC)
  #  my_cppflags_CLANG_QCOM += $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBGCC)
  #  ifdef LOCAL_CONLYFLAGS
  #    LOCAL_CONLYFLAGS  += $(COMPILER_RT_CONFIG_EXTRA_QCOM_OPT_LIBGCC)
  #  endif
  #endif
  #ifeq ($(strip $(LOCAL_ADDRESS_SANITIZER)),true)
  #  my_static_libraries += libclang_rt.asan-arm-android libclang_rt.san-arm-android
  #endif

  #qclang is using gcc assembler for .s so invoke mcpu=cortex-a15 for gcc-as. See documentation 3.4.12
  ifeq ($(LOCAL_MODULE),libcompiler_rt)
    my_asflags_CLANG_QCOM  += -mcpu=cortex-a15
  endif

  ifeq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_C11_MODULES)))
    my_cppflags_CLANG_QCOM += -std=c++11
  endif

  #https://android-review.googlesource.com/#/c/110170/
  ifeq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_DONT_USE_AS_MODULES)))
    my_asflags_CLANG_QCOM += -no-integrated-as
    my_cflags_CLANG_QCOM += -no-integrated-as
  endif

  ifeq ($(LOCAL_ARM_MODE),arm)
    my_target_global_cflags += -marm
    my_target_global_cppflags += -marm
    my_cflags_CLANG_QCOM += -marm
    my_cppflags_CLANG_QCOM += -marm
    my_asflags_CLANG_QCOM += -marm
    my_ldflags_CLANG_QCOM += -marm
    LOCAL_CONLYFLAGS  += -marm
  else ifeq ($(LOCAL_ARM_MODE),thumb)
    my_target_global_cflags += -mthumb
    my_target_global_cppflags += -mthumb
    my_cflags_CLANG_QCOM += -mthumb
    my_cppflags_CLANG_QCOM += -mthumb
    my_asflags_CLANG_QCOM += -mthumb
    my_ldflags_CLANG_QCOM += -mthumb
    LOCAL_CONLYFLAGS  += -mthumb
  endif

  ifdef my_target_global_ndk_stl_cppflags
    my_target_global_cppflags += $(my_target_global_ndk_stl_cppflags)
  endif

  my_cc := $(CLANG_QCOM) -mllvm -aggressive-jt
  my_cxx := $(CLANG_QCOM_CXX) -mllvm -aggressive-jt

  ifeq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_ALIGN-OS_MODULES)))
    normal_objects_cflags_CLANG_QCOM := $(filter-out -falign-os,$(normal_objects_cflags_CLANG_QCOM))
  endif

  ifeq ($(CLANG_QCOM_SHOW_FLAGS),true)
    $(info MODULE   : $(LOCAL_MODULE))
    $(info cflags    : $(my_target_global_cflags))
    $(info cppflags  : $(my_target_global_cppflags))
    $(info cflags   : $(my_cflags_CLANG_QCOM))
    $(info cppflags : $(my_cppflags_CLANG_QCOM))
    $(info asflags  : $(my_asflags_CLANG_QCOM))
    $(info ldflags  : $(my_ldflags_CLANG_QCOM))    
    $(info conly    : $(LOCAL_CONLYFLAGS))
    $(info arm_objects_cflags: $(arm_objects_cflags_CLANG_QCOM))
    $(info normal_objects_c  : $(normal_objects_cflags_CLANG_QCOM))
    $(info )
  endif
  
endif
