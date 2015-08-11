# Flags and linking
my_target_c_includes += $(CLANG_QCOM_CONFIG_EXTRA_TARGET_C_INCLUDES)
my_target_global_cflags := $(CLANG_QCOM_TARGET_GLOBAL_CFLAGS)
my_target_global_cppflags := $(CLANG_QCOM_TARGET_GLOBAL_CPPFLAGS)
my_target_global_ldflags := $(CLANG_QCOM_TARGET_GLOBAL_LDFLAGS)

ifneq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_DONT_USE_PARALLEL_MODULES)))
my_target_global_cflags += $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS)
my_target_global_cppflags += $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS)
my_target_global_ldflags += $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS)
endif

# build for arm
LOCAL_ARM_MODE := arm

ifeq ($(CLANG_QCOM_SHOW_FLAGS),true)
$(info global MODULE       : $(LOCAL_MODULE))
$(info global cflags       : $(my_target_global_cflags))
$(info global cppflags     : $(my_target_global_cppflags))
$(info global ldflags      : $(my_target_global_ldflags))
$(info )
endif

# Set path to CLANG binary
my_cc := $(CLANG_QCOM)
my_cxx := $(CLANG_QCOM_CXX)
