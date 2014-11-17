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

GRAPHITE_FLAGS := -fgraphite,-floop-flatten,-floop-parallelize-all,-ftree-loop-linear,-floop-interchange,-floop-strip-mine,-floop-block

ifdef LOCAL_CFLAGS
LOCAL_CFLAGS += $(call cc-option,$(GRAPHITE_FLAGS))
else
LOCAL_CFLAGS := $(call cc-option,$(GRAPHITE_FLAGS))
endif

ifdef LOCAL_CPPFLAGS
LOCAL_CFLAGS += $(call cpp-option,$(GRAPHITE_FLAGS))
else
LOCAL_CPPFLAGS := $(call cpp-option,$(GRAPHITE_FLAGS))
endif
####
