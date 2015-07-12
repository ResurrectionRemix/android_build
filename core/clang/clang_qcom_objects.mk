# Convert for QCOM CLANG
arm_objects_cflags := $(call convert-to-clang-qcom-flags,$($(LOCAL_2ND_ARCH_VAR_PREFIX)$(my_prefix)$(arm_objects_mode)_CFLAGS))
normal_objects_cflags := $(call convert-to-clang-qcom-flags,$($(LOCAL_2ND_ARCH_VAR_PREFIX)$(my_prefix)$(normal_objects_mode)_CFLAGS))

# -fparallel documentation 3.6.4
ifeq ($(USE_CLANG_QCOM_ONLY_ON_SELECTED_MODULES)$(LOCAL_MODULE),true$(filter $(LOCAL_MODULE),$(CLANG_QCOM_USE_PARALLEL_MODULES)))
arm_objects_cflags += $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS)
normal_objects_cflags += $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS)
endif

# Add KRAIT FLAGS
arm_objects_cflags += $(CLANG_QCOM_CONFIG_KRAIT_Ofast_FLAGS) 
normal_objects_cflags += $(CLANG_QCOM_CONFIG_KRAIT_Ofast_FLAGS)

# Workaround where global definition of -Os ist overwritten with a higher optimization in local definition
ifeq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_NO-ALIGN-OS_MODULES)))
normal_objects_cflags := $(filter-out -falign-os,$(normal_objects_cflags))
endif

ifeq ($(CLANG_QCOM_SHOW_FLAGS_OBJECT),true)
$(info object MODULE       : $(LOCAL_MODULE))
$(info arm_objects_cflags  : $(arm_objects_cflags))
$(info normal_objects_c    : $(normal_objects_cflags))
$(info )
endif
