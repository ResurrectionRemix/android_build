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

# Force disable some modules that are not compatible with graphite flags.
# Add more modules if needed for devices in BoardConfig.mk
# LOCAL_DISABLE_GRAPHITE +=
LOCAL_DISABLE_GRAPHITE := \
  libmincrypt \
  mkbootimg \
  mkbootfs \
  libhost \
  ibext2_profile \
  make_ext4fs \
  hprof-conv \
  acp \
  libsqlite \
  libsqlite_jni \
  simg2img_host \
  e2fsck \
  append2simg \
  build_verity_tree \
  sqlite3 \
  e2fsck_host \
  libext2_profile_host \
  libext2_quota_host \
  libext2fs_host\
  libbz\
  make_f2fs\
  imgdiff\
  bsdiff \
  libedify \
  fs_config \
  unpackbootimg \
  mkyaffs2image \
  libext2_com_err_host \
  libext2_blkid_host \
  libext2_e2p_host\
  libcrypto-host \
  libexpat-host \
  libicuuc-host \
  libicui18n-host \
  dmtracedump \
  libsparse_host \
  libz-host \
  libfdlibm \
  libsqlite3_android \
  libssl-host \
  libf2fs_dlutils_host \
  libf2fs_utils_host \
  libf2fs_ioutils_host \
  libf2fs_fmt_host_dyn \
  libext2_uuid_host \
  minigzip \
  libdex \
  dexdump \
  dexlist \
  libext4_utils_host \
  third_party_protobuf_protoc_arm_host_gyp \
  libaapt \
  aapt \
  fastboot  \
  libpng \
  aprotoc \
  fio \
  fsck.f2fs \
  libandroidfw \
  libbacktrace_test \
  liblog \
  libgtest_host \
  libbacktrace_libc++ \
  v8_tools_gyp_v8_nosnapshot_arm_host_gyp \
  third_party_icu_icui18n_arm_host_gyp \
  third_party_icu_icuuc_arm_host_gyp \
  tird_party_protobuf_protobuf_full_do_not_use_arm_host_gyp \
  third_party_protobuf_protobuf_full_do_not_use_arm_host_gyp \
  v8_tools_gyp_mksnapshot_arm_host_gyp \
  third_party_libvpx_libvpx_obj_int_extract_arm_host_gyp \
  libutils \
  libcutils \
  libexpat \
  v8_tools_gyp_v8_base_arm_host_gyp \
  v8_tools_gyp_v8_libbase_arm_host_gyp \
  v8_tools_gyp_v8_libbase_arm_host_gyp_32 \
  aidl \
  libziparchive-host \
  libcrypto_static \
  libunwind-ptrace \
  libgtest_main_host \
  libbacktrace \
  backtrace_test \
  libzopfli \
  zipalign \
  rsg-generator \
  unrar \
  libunz \
  adb \
  libzipfile \
  rsg-generator_support \
  libunwindbacktrace \
  libc_common \
  libz \
  libselinux \
  checkfc \
  checkseapp \
  checkpolicy \
  libsepol \
  libpcre \
  libunwind \
  libFFTEm \
  libicui18n \
  libskia \
  libvpx \
  libmedia_jni \
  libstagefright_mp3dec \
  libart \
  mdnsd \
  libwebrtc_spl \
  third_party_WebKit_Source_core_webcore_svg_gyp \
  libjni_filtershow_filters \
  libavformat \
  libavcodec \
  skia_skia_library_gyp

ifneq (1,$(words $(filter $(LOCAL_DISABLE_GRAPHITE),$(LOCAL_MODULE))))
ifdef LOCAL_CONLYFLAGS
LOCAL_CONLYFLAGS += $(GRAPHITE_FLAGS)
else
LOCAL_CONLYFLAGS := $(GRAPHITE_FLAGS)
endif

ifdef LOCAL_CPPFLAGS
LOCAL_CPPFLAGS += $(GRAPHITE_FLAGS)
else
LOCAL_CPPFLAGS := $(GRAPHITE_FLAGS)
endif

ifndef LOCAL_LDFLAGS
LOCAL_LDFLAGS  := $(GRAPHITE_FLAGS)
else
LOCAL_LDFLAGS  += $(GRAPHITE_FLAGS)
endif
endif
#####
