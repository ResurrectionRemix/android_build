# Copyright (C) 2014 The SaberMod Project
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

LOCAL_DISABLE_STRICT := \
	camera.omap4 \
	audio.primary.piranha \
	camera.msm8084 \
	hwcomposer.msm8084 \
	bionic \
	libavutil \
	libavcodec \
	libxml2 \
	stlport \
	libc_bionic \
	libc_dns \
	libc_tzcode \
	libziparchive \
	busybox \
	libuclibcrpc \
	libziparchive-host \
	libpdfiumcore \
	libandroid_runtime \
	libmedia \
	libpdfiumcore \
	libpdfium \
	bluetooth.default \
	logd \
	mdnsd \
	dnsmasq \
	net_net_gyp \
	libaudioflinger \
	libdiskconfig \
	libjavacore \
	libfdlibm \
	librtp_jni \
	libwilhelm \
	libdownmix \
	libldnhncr \
	libqcomvisualizer \
	libvisualizer \
	libstlport \
	libutils \
	libandroidfw \
	libmediaplayerservice \
	libstagefright \
	libstagefright_webm \
	libvariablespeed \
	ping \
	ping6 \
	static_busybox \
	mm-vdec-omx-test \
	content_content_renderer_gyp \
	third_party_WebKit_Source_modules_modules_gyp \
	third_party_WebKit_Source_platform_blink_platform_gyp \
	third_party_WebKit_Source_core_webcore_remaining_gyp \
	third_party_angle_src_translator_lib_gyp \
	third_party_WebKit_Source_core_webcore_generated_gyp \
	libc_gdtoa \
	libc_openbsd \
	libc \
	libc_nomalloc \
	libstlport_static \
	libcrypto_static \
	libfuse \
	libbusybox \
	libwnndict \
        libcurl \
	gatt_testtool \
	libqsap_sdk \
	libOmxVenc \
	lsof \
	libc_malloc \
	canohost.c \
	sshconnect.c \
	ssh \
	libssh \
	audio.primary.msm8960

ifneq (1,$(words $(filter $(LOCAL_DISABLE_STRICT), $(LOCAL_MODULE))))
ifndef LOCAL_CONLYFLAGS
LOCAL_CONLYFLAGS += \
	-fstrict-aliasing \
	-Werror=strict-aliasing
else
LOCAL_CONLYFLAGS := \
	-fstrict-aliasing \
	-Werror=strict-aliasing
endif

ifdef LOCAL_CPPFLAGS
LOCAL_CPPFLAGS += \
	-fstrict-aliasing \
	-Werror=strict-aliasing
else
LOCAL_CPPFLAGS := \
	-fstrict-aliasing \
	-Werror=strict-aliasing
endif
ifndef LOCAL_CLANG
LOCAL_CONLYFLAGS += \
	-Wstrict-aliasing=3
LOCAL_CPPFLAGS += \
	-Wstrict-aliasing=3
else
LOCAL_CONLYFLAGS += \
	-Wstrict-aliasing=2
LOCAL_CPPFLAGS += \
	-Wstrict-aliasing=2
endif
endif
#####
