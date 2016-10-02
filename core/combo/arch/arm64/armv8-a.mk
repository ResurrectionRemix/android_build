ifneq (,$(filter cortex-a53,$(TARGET_$(combo_2nd_arch_prefix)CPU_VARIANT)))
	arch_variant_cflags := -mcpu=cortex-a53
else
	arch_variant_cflags :=
endif

ifneq (,$(filter cortex-a53 default,$(TARGET_$(combo_2nd_arch_prefix)CPU_VARIANT)))
	arch_variant_ldflags := -Wl,--fix-cortex-a53-843419
else
	arch_variant_ldflags := -Wl,--no-fix-cortex-a53-843419
endif

