# Convert for CLANG QCOM
my_cflags := $(call convert-to-clang-qcom-flags,$(my_cflags))
my_cppflags := $(call convert-to-clang-qcom-flags,$(my_cppflags))
my_ldflags := $(call convert-to-clang-qcom-ldflags,$(my_ldflags))
LOCAL_CONLYFLAGS := $(call convert-to-clang-qcom-flags,$(LOCAL_CONLYFLAGS))

# Substitute -O2 and -O3 with -Ofast -fno-fast-math
ifneq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_DONT_REPLACE_WITH_Ofast_MODULES)))
my_cflags := $(call subst-clang-qcom-opt,$(my_cflags))
my_cppflags := $(call subst-clang-qcom-opt,$(my_cppflags))
LOCAL_CONLYFLAGS := $(call subst-clang-qcom-opt,$(LOCAL_CONLYFLAGS))
endif

# Flags and linking
my_cflags += $(CLANG_QCOM_CONFIG_KRAIT_Ofast_FLAGS)
my_cppflags += $(CLANG_QCOM_CONFIG_KRAIT_Ofast_FLAGS)
my_ldflags += $(CLANG_QCOM_CONFIG_KRAIT_FLAGS) -Wl,--gc-sections
LOCAL_CONLYFLAGS += $(CLANG_QCOM_CONFIG_KRAIT_Ofast_FLAGS)  
# Set different mcpu for GCC Assembler because it doesnt know -mcpu=krait and defaults to -march=armv7-a
my_asflags += $(clang_qcom_mcpu_as)

# -fparallel documentation 3.6.4
ifeq ($(USE_CLANG_QCOM_ONLY_ON_SELECTED_MODULES)$(LOCAL_MODULE),true$(filter $(LOCAL_MODULE),$(CLANG_QCOM_USE_PARALLEL_MODULES)))
my_cflags += $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS)
my_cppflags += $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS)
my_asflags += $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS)
my_ldflags += $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS)
LOCAL_CONLYFLAGS += $(CLANG_QCOM_CONFIG_KRAIT_PARALLEL_FLAGS)
endif

# Set language dialect to C++11
ifeq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_C++11_MODULES)))
my_cppflags += -std=c++11
endif

# Set language dialect to C++11
ifeq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_GNU++11_MODULES)))
my_cppflags += -std=gnu++11
endif

# libc++abi bug: https://android-review.googlesource.com/#/c/110170/
# Skia doesnt like the clang assembler
ifeq ($(LOCAL_MODULE),$(filter $(LOCAL_MODULE),$(CLANG_QCOM_DONT_USE_INTEGRATED_AS_MODULES)))
my_cflags += -no-integrated-as -Xassembler -mcpu=cortex-a15
endif

ifeq ($(CLANG_QCOM_SHOW_FLAGS_LOCAL),true)
$(info local MODULE       : $(LOCAL_MODULE))
$(info cflags             : $(my_cflags))
$(info cppflags           : $(my_cppflags))
$(info asflags            : $(my_asflags))
$(info ldflags            : $(my_ldflags))    
$(info conly              : $(LOCAL_CONLYFLAGS))
$(info )
endif
