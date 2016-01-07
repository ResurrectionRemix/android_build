#!/usr/bin/env python
#
# Copyright (C) 2008 The Android Open Source Project
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

"""
Given a target-files zipfile, produces an OTA package that installs
that build.  An incremental OTA is produced if -i is given, otherwise
a full OTA is produced.

Usage:  ota_from_target_files [flags] input_target_files output_ota_package

  --board_config  <file>
      Deprecated.

  -k (--package_key) <key> Key to use to sign the package (default is
      the value of default_system_dev_certificate from the input
      target-files's META/misc_info.txt, or
      "build/target/product/security/testkey" if that value is not
      specified).

      For incremental OTAs, the default value is based on the source
      target-file, not the target build.

  -i  (--incremental_from)  <file>
      Generate an incremental OTA using the given target-files zip as
      the starting build.

  --full_radio
      When generating an incremental OTA, always include a full copy of
      radio image. This option is only meaningful when -i is specified,
      because a full radio is always included in a full OTA if applicable.

 --full_bootloader
      When generating an incremental OTA, always include a full copy of
      bootloader image. This option is only meaningful when -i is specified,
      because a full bootloader is always included in a full OTA if applicable.

  -v  (--verify)
      Remount and verify the checksums of the files written to the
      system and vendor (if used) partitions.  Incremental builds only.

  -o  (--oem_settings)  <file>
      Use the file to specify the expected OEM-specific properties
      on the OEM partition of the intended device.

  -w  (--wipe_user_data)
      Generate an OTA package that will wipe the user data partition
      when installed.

  -n  (--no_prereq)
      Omit the timestamp prereq check normally included at the top of
      the build scripts (used for developer OTA packages which
      legitimately need to go back and forth).

  -e  (--extra_script)  <file>
      Insert the contents of file at the end of the update script.

  -a  (--aslr_mode)  <on|off>
      Specify whether to turn on ASLR for the package (on by default).

  -2  (--two_step)
      Generate a 'two-step' OTA package, where recovery is updated
      first, so that any changes made to the system partition are done
      using the new recovery (new kernel, etc.).

  --block
      Generate a block-based OTA if possible.  Will fall back to a
      file-based OTA if the target_files is older and doesn't support
      block-based OTAs.

  -b  (--binary)  <file>
      Use the given binary as the update-binary in the output package,
      instead of the binary in the build's target_files.  Use for
      development only.

  -t  (--worker_threads) <int>
      Specifies the number of worker-threads that will be used when
      generating patches for incremental updates (defaults to 3).

  --stash_threshold <float>
      Specifies the threshold that will be used to compute the maximum
      allowed stash size (defaults to 0.8).

  --backup <boolean>
      Enable or disable the execution of backuptool.sh.
      Disabled by default.

  --override_device <device>
      Override device-specific asserts. Can be a comma-separated list.

  --override_prop <boolean>
      Override build.prop items with custom vendor init.
      Enabled when TARGET_UNIFIED_DEVICE is defined in BoardConfig

"""

from __future__ import print_function

import sys

if sys.hexversion < 0x02070000:
  print("Python 2.7 or newer is required.", file=sys.stderr)
  sys.exit(1)

import multiprocessing
import os
import tempfile
import zipfile

import common
import edify_generator
import sparse_img

OPTIONS = common.OPTIONS
OPTIONS.package_key = None
OPTIONS.incremental_source = None
OPTIONS.verify = False
OPTIONS.require_verbatim = set()
OPTIONS.prohibit_verbatim = set(("system/build.prop",))
OPTIONS.patch_threshold = 0.95
OPTIONS.wipe_user_data = False
OPTIONS.omit_prereq = False
OPTIONS.extra_script = None
OPTIONS.aslr_mode = True
OPTIONS.worker_threads = multiprocessing.cpu_count() // 2
if OPTIONS.worker_threads == 0:
  OPTIONS.worker_threads = 1
OPTIONS.two_step = False
OPTIONS.no_signing = False
OPTIONS.block_based = False
OPTIONS.updater_binary = None
OPTIONS.oem_source = None
OPTIONS.fallback_to_full = True
OPTIONS.full_radio = False
OPTIONS.full_bootloader = False
OPTIONS.backuptool = False
OPTIONS.override_device = 'auto'
OPTIONS.override_prop = False

def MostPopularKey(d, default):
  """Given a dict, return the key corresponding to the largest
  value.  Returns 'default' if the dict is empty."""
  x = [(v, k) for (k, v) in d.items()]
  if not x:
    return default
  x.sort()
  return x[-1][1]


def IsSymlink(info):
  """Return true if the zipfile.ZipInfo object passed in represents a
  symlink."""
  return (info.external_attr >> 16) & 0o770000 == 0o120000

def IsRegular(info):
  """Return true if the zipfile.ZipInfo object passed in represents a
  symlink."""
  return (info.external_attr >> 28) == 0o10

def ClosestFileMatch(src, tgtfiles, existing):
  """Returns the closest file match between a source file and list
     of potential matches.  The exact filename match is preferred,
     then the sha1 is searched for, and finally a file with the same
     basename is evaluated.  Rename support in the updater-binary is
     required for the latter checks to be used."""

  result = tgtfiles.get("path:" + src.name)
  if result is not None:
    return result

  if not OPTIONS.target_info_dict.get("update_rename_support", False):
    return None

  if src.size < 1000:
    return None

  result = tgtfiles.get("sha1:" + src.sha1)
  if result is not None and existing.get(result.name) is None:
    return result
  result = tgtfiles.get("file:" + src.name.split("/")[-1])
  if result is not None and existing.get(result.name) is None:
    return result
  return None

class ItemSet(object):
  def __init__(self, partition, fs_config):
    self.partition = partition
    self.fs_config = fs_config
    self.ITEMS = {}

  def Get(self, name, is_dir=False):
    if name not in self.ITEMS:
      self.ITEMS[name] = Item(self, name, is_dir=is_dir)
    return self.ITEMS[name]

  def GetMetadata(self, input_zip):
    # The target_files contains a record of what the uid,
    # gid, and mode are supposed to be.
    output = input_zip.read(self.fs_config)

    for line in output.split("\n"):
      if not line:
        continue
      columns = line.split()
      name, uid, gid, mode = columns[:4]
      selabel = None
      capabilities = None

      # After the first 4 columns, there are a series of key=value
      # pairs. Extract out the fields we care about.
      for element in columns[4:]:
        key, value = element.split("=")
        if key == "selabel":
          selabel = value
        if key == "capabilities":
          capabilities = value

      i = self.ITEMS.get(name, None)
      if i is not None:
        i.uid = int(uid)
        i.gid = int(gid)
        i.mode = int(mode, 8)
        i.selabel = selabel
        i.capabilities = capabilities
        if i.is_dir:
          i.children.sort(key=lambda i: i.name)

    # set metadata for the files generated by this script.
    i = self.ITEMS.get("system/recovery-from-boot.p", None)
    if i:
      i.uid, i.gid, i.mode, i.selabel, i.capabilities = 0, 0, 0o644, None, None
    i = self.ITEMS.get("system/etc/install-recovery.sh", None)
    if i:
      i.uid, i.gid, i.mode, i.selabel, i.capabilities = 0, 0, 0o544, None, None


class Item(object):
  """Items represent the metadata (user, group, mode) of files and
  directories in the system image."""
  def __init__(self, itemset, name, is_dir=False):
    self.itemset = itemset
    self.name = name
    self.uid = None
    self.gid = None
    self.mode = None
    self.selabel = None
    self.capabilities = None
    self.is_dir = is_dir
    self.descendants = None
    self.best_subtree = None

    if name:
      self.parent = itemset.Get(os.path.dirname(name), is_dir=True)
      self.parent.children.append(self)
    else:
      self.parent = None
    if self.is_dir:
      self.children = []

  def Dump(self, indent=0):
    if self.uid is not None:
      print("%s%s %d %d %o" % (
          "  " * indent, self.name, self.uid, self.gid, self.mode))
    else:
      print("%s%s %s %s %s" % (
          "  " * indent, self.name, self.uid, self.gid, self.mode))
    if self.is_dir:
      print("%s%s" % ("  "*indent, self.descendants))
      print("%s%s" % ("  "*indent, self.best_subtree))
      for i in self.children:
        i.Dump(indent=indent+1)

  def CountChildMetadata(self):
    """Count up the (uid, gid, mode, selabel, capabilities) tuples for
    all children and determine the best strategy for using set_perm_recursive
    and set_perm to correctly chown/chmod all the files to their desired
    values.  Recursively calls itself for all descendants.

    Returns a dict of {(uid, gid, dmode, fmode, selabel, capabilities): count}
    counting up all descendants of this node.  (dmode or fmode may be None.)
    Also sets the best_subtree of each directory Item to the (uid, gid, dmode,
    fmode, selabel, capabilities) tuple that will match the most descendants of
    that Item.
    """

    assert self.is_dir
    key = (self.uid, self.gid, self.mode, None, self.selabel,
           self.capabilities)
    self.descendants = {key: 1}
    d = self.descendants
    for i in self.children:
      if i.is_dir:
        for k, v in i.CountChildMetadata().items():
          d[k] = d.get(k, 0) + v
      else:
        k = (i.uid, i.gid, None, i.mode, i.selabel, i.capabilities)
        d[k] = d.get(k, 0) + 1

    # Find the (uid, gid, dmode, fmode, selabel, capabilities)
    # tuple that matches the most descendants.

    # First, find the (uid, gid) pair that matches the most
    # descendants.
    ug = {}
    for (uid, gid, _, _, _, _), count in d.items():
      ug[(uid, gid)] = ug.get((uid, gid), 0) + count
    ug = MostPopularKey(ug, (0, 0))

    # Now find the dmode, fmode, selabel, and capabilities that match
    # the most descendants with that (uid, gid), and choose those.
    best_dmode = (0, 0o755)
    best_fmode = (0, 0o644)
    best_selabel = (0, None)
    best_capabilities = (0, None)
    for k, count in d.items():
      if k[:2] != ug:
        continue
      if k[2] is not None and count >= best_dmode[0]:
        best_dmode = (count, k[2])
      if k[3] is not None and count >= best_fmode[0]:
        best_fmode = (count, k[3])
      if k[4] is not None and count >= best_selabel[0]:
        best_selabel = (count, k[4])
      if k[5] is not None and count >= best_capabilities[0]:
        best_capabilities = (count, k[5])
    self.best_subtree = ug + (
        best_dmode[1], best_fmode[1], best_selabel[1], best_capabilities[1])

    return d

  def SetPermissions(self, script):
    """Append set_perm/set_perm_recursive commands to 'script' to
    set all permissions, users, and groups for the tree of files
    rooted at 'self'."""

    self.CountChildMetadata()

    def recurse(item, current):
      # current is the (uid, gid, dmode, fmode, selabel, capabilities) tuple
      # that the current item (and all its children) have already been set to.
      # We only need to issue set_perm/set_perm_recursive commands if we're
      # supposed to be something different.
      if item.is_dir:
        if current != item.best_subtree:
          script.SetPermissionsRecursive("/"+item.name, *item.best_subtree)
          current = item.best_subtree

        if item.uid != current[0] or item.gid != current[1] or \
           item.mode != current[2] or item.selabel != current[4] or \
           item.capabilities != current[5]:
          script.SetPermissions("/"+item.name, item.uid, item.gid,
                                item.mode, item.selabel, item.capabilities)

        for i in item.children:
          recurse(i, current)
      else:
        if item.uid != current[0] or item.gid != current[1] or \
               item.mode != current[3] or item.selabel != current[4] or \
               item.capabilities != current[5]:
          script.SetPermissions("/"+item.name, item.uid, item.gid,
                                item.mode, item.selabel, item.capabilities)

    recurse(self, (-1, -1, -1, -1, None, None))


def CopyPartitionFiles(itemset, input_zip, output_zip=None, substitute=None):
  """Copies files for the partition in the input zip to the output
  zip.  Populates the Item class with their metadata, and returns a
  list of symlinks.  output_zip may be None, in which case the copy is
  skipped (but the other side effects still happen).  substitute is an
  optional dict of {output filename: contents} to be output instead of
  certain input files.
  """

  symlinks = []

  partition = itemset.partition

  for info in input_zip.infolist():
    prefix = partition.upper() + "/"
    if info.filename.startswith(prefix):
      basefilename = info.filename[len(prefix):]
      if IsSymlink(info):
        symlinks.append((input_zip.read(info.filename),
                         "/" + partition + "/" + basefilename))
      else:
        import copy
        info2 = copy.copy(info)
        fn = info2.filename = partition + "/" + basefilename
        if substitute and fn in substitute and substitute[fn] is None:
          continue
        if output_zip is not None:
          if substitute and fn in substitute:
            data = substitute[fn]
          else:
            data = input_zip.read(info.filename)
          common.ZipWriteStr(output_zip, info2, data)
        if fn.endswith("/"):
          itemset.Get(fn[:-1], is_dir=True)
        else:
          itemset.Get(fn)

  symlinks.sort()
  return symlinks


def SignOutput(temp_zip_name, output_zip_name):
  key_passwords = common.GetKeyPasswords([OPTIONS.package_key])
  pw = key_passwords[OPTIONS.package_key]

  common.SignFile(temp_zip_name, output_zip_name, OPTIONS.package_key, pw,
                  whole_file=True)


def AppendAssertions(script, info_dict, oem_dict=None):
  oem_props = info_dict.get("oem_fingerprint_properties")
  if oem_props is None or len(oem_props) == 0:
    if OPTIONS.override_device == "auto":
      device = GetBuildProp("ro.product.device", info_dict)
    else:
      device = OPTIONS.override_device
    script.AssertDevice(device)
  else:
    if oem_dict is None:
      raise common.ExternalError(
          "No OEM file provided to answer expected assertions")
    for prop in oem_props.split():
      if oem_dict.get(prop) is None:
        raise common.ExternalError(
            "The OEM file is missing the property %s" % prop)
      script.AssertOemProperty(prop, oem_dict.get(prop))


def HasRecoveryPatch(target_files_zip):
  try:
    target_files_zip.getinfo("SYSTEM/recovery-from-boot.p")
    return True
  except KeyError:
    return False

def HasVendorPartition(target_files_zip):
  try:
    target_files_zip.getinfo("VENDOR/")
    return True
  except KeyError:
    return False

def GetOemProperty(name, oem_props, oem_dict, info_dict):
  if oem_props is not None and name in oem_props:
    return oem_dict[name]
  return GetBuildProp(name, info_dict)

def CalculateFingerprint(oem_props, oem_dict, info_dict):
  if OPTIONS.override_prop:
    return GetBuildProp("ro.build.date.utc", info_dict)
  if oem_props is None:
    return GetBuildProp("ro.build.fingerprint", info_dict)
  return "%s/%s/%s:%s" % (
      GetOemProperty("ro.product.brand", oem_props, oem_dict, info_dict),
      GetOemProperty("ro.product.name", oem_props, oem_dict, info_dict),
      GetOemProperty("ro.product.device", oem_props, oem_dict, info_dict),
      GetBuildProp("ro.build.thumbprint", info_dict))


def GetImage(which, tmpdir, info_dict):
  # Return an image object (suitable for passing to BlockImageDiff)
  # for the 'which' partition (most be "system" or "vendor").  If a
  # prebuilt image and file map are found in tmpdir they are used,
  # otherwise they are reconstructed from the individual files.

  assert which in ("system", "vendor")

  path = os.path.join(tmpdir, "IMAGES", which + ".img")
  mappath = os.path.join(tmpdir, "IMAGES", which + ".map")
  if os.path.exists(path) and os.path.exists(mappath):
    print("using %s.img from target-files" % which)
    # This is a 'new' target-files, which already has the image in it.

  else:
    print("building %s.img from target-files" % which)

    # This is an 'old' target-files, which does not contain images
    # already built.  Build them.

    mappath = tempfile.mkstemp()[1]
    OPTIONS.tempfiles.append(mappath)

    import add_img_to_target_files
    if which == "system":
      path = add_img_to_target_files.BuildSystem(
          tmpdir, info_dict, block_list=mappath)
    elif which == "vendor":
      path = add_img_to_target_files.BuildVendor(
          tmpdir, info_dict, block_list=mappath)

  # Bug: http://b/20939131
  # In ext4 filesystems, block 0 might be changed even being mounted
  # R/O. We add it to clobbered_blocks so that it will be written to the
  # target unconditionally. Note that they are still part of care_map.
  clobbered_blocks = "0"

  return sparse_img.SparseImage(path, mappath, clobbered_blocks)


def CopyInstallTools(output_zip):
  install_path = os.path.join(OPTIONS.input_tmp, "INSTALL")
  for root, subdirs, files in os.walk(install_path):
    for f in files:
      install_source = os.path.join(root, f)
      install_target = os.path.join("install", os.path.relpath(root, install_path), f)
      output_zip.write(install_source, install_target)


def WriteFullOTAPackage(input_zip, output_zip):
  # TODO: how to determine this?  We don't know what version it will
  # be installed on top of. For now, we expect the API just won't
  # change very often. Similarly for fstab, it might have changed
  # in the target build.
  script = edify_generator.EdifyGenerator(3, OPTIONS.info_dict)

  oem_props = OPTIONS.info_dict.get("oem_fingerprint_properties")
  recovery_mount_options = OPTIONS.info_dict.get("recovery_mount_options")
  oem_dict = None
  if oem_props is not None and len(oem_props) > 0:
    if OPTIONS.oem_source is None:
      raise common.ExternalError("OEM source required for this build")
    script.Mount("/oem", recovery_mount_options)
    oem_dict = common.LoadDictionaryFromLines(
        open(OPTIONS.oem_source).readlines())

  if OPTIONS.override_prop:
    metadata = {"post-timestamp": GetBuildProp("ro.build.date.utc",
                                               OPTIONS.info_dict),
                }
  else:
    metadata = {"post-build": CalculateFingerprint(
                                 oem_props, oem_dict, OPTIONS.info_dict),
                "pre-device": GetOemProperty("ro.product.device", oem_props, oem_dict,
                                           OPTIONS.info_dict),
                "post-timestamp": GetBuildProp("ro.build.date.utc",
                                             OPTIONS.info_dict),
                }

  device_specific = common.DeviceSpecificParams(
      input_zip=input_zip,
      input_version=OPTIONS.info_dict["recovery_api_version"],
      output_zip=output_zip,
      script=script,
      input_tmp=OPTIONS.input_tmp,
      metadata=metadata,
      info_dict=OPTIONS.info_dict)

  has_recovery_patch = HasRecoveryPatch(input_zip)
  block_based = OPTIONS.block_based and has_recovery_patch

  #if not OPTIONS.omit_prereq:
  #  ts = GetBuildProp("ro.build.date.utc", OPTIONS.info_dict)
  #  ts_text = GetBuildProp("ro.build.date", OPTIONS.info_dict)
  #  script.AssertOlderBuild(ts, ts_text)

  AppendAssertions(script, OPTIONS.info_dict, oem_dict)
  device_specific.FullOTA_Assertions()

  # Two-step package strategy (in chronological order, which is *not*
  # the order in which the generated script has things):
  #
  # if stage is not "2/3" or "3/3":
  #    write recovery image to boot partition
  #    set stage to "2/3"
  #    reboot to boot partition and restart recovery
  # else if stage is "2/3":
  #    write recovery image to recovery partition
  #    set stage to "3/3"
  #    reboot to recovery partition and restart recovery
  # else:
  #    (stage must be "3/3")
  #    set stage to ""
  #    do normal full package installation:
  #       wipe and install system, boot image, etc.
  #       set up system to update recovery partition on first boot
  #    complete script normally
  #    (allow recovery to mark itself finished and reboot)

  recovery_img = common.GetBootableImage("recovery.img", "recovery.img",
                                         OPTIONS.input_tmp, "RECOVERY")
  if OPTIONS.two_step:
    if not OPTIONS.info_dict.get("multistage_support", None):
      assert False, "two-step packages not supported by this build"
    fs = OPTIONS.info_dict["fstab"]["/misc"]
    assert fs.fs_type.upper() == "EMMC", \
        "two-step packages only supported on devices with EMMC /misc partitions"
    bcb_dev = {"bcb_dev": fs.device}
    common.ZipWriteStr(output_zip, "recovery.img", recovery_img.data)
    script.AppendExtra("""
if get_stage("%(bcb_dev)s") == "2/3" then
""" % bcb_dev)
    script.WriteRawImage("/recovery", "recovery.img")
    script.AppendExtra("""
set_stage("%(bcb_dev)s", "3/3");
reboot_now("%(bcb_dev)s", "recovery");
else if get_stage("%(bcb_dev)s") == "3/3" then
""" % bcb_dev)

  # Dump fingerprints
  script.Print("Target: %s" % CalculateFingerprint(
      oem_props, oem_dict, OPTIONS.info_dict))

  script.AppendExtra("ifelse(is_mounted(\"/system\"), unmount(\"/system\"));")
  device_specific.FullOTA_InstallBegin()

  CopyInstallTools(output_zip)
  script.UnpackPackageDir("install", "/tmp/install")
  script.SetPermissionsRecursive("/tmp/install", 0, 0, 0o755, 0o644, None, None)
  script.SetPermissionsRecursive("/tmp/install/bin", 0, 0, 0o755, 0o755, None, None)

  if OPTIONS.backuptool:
    script.Mount("/system")
    script.RunBackup("backup")
    script.Unmount("/system")

  system_progress = 0.75

  if OPTIONS.wipe_user_data:
    system_progress -= 0.1
  if HasVendorPartition(input_zip):
    system_progress -= 0.1

  script.AppendExtra("if is_mounted(\"/data\") then")
  script.ValidateSignatures("data")
  script.AppendExtra("else")
  script.Mount("/data")
  script.ValidateSignatures("data")
  script.Unmount("/data")
  script.AppendExtra("endif;")

  if "selinux_fc" in OPTIONS.info_dict:
    WritePolicyConfig(OPTIONS.info_dict["selinux_fc"], output_zip)

  recovery_mount_options = OPTIONS.info_dict.get("recovery_mount_options")

  system_items = ItemSet("system", "META/filesystem_config.txt")
  script.ShowProgress(system_progress, 0)

  if block_based:
    # Full OTA is done as an "incremental" against an empty source
    # image.  This has the effect of writing new data from the package
    # to the entire partition, but lets us reuse the updater code that
    # writes incrementals to do it.
    system_tgt = GetImage("system", OPTIONS.input_tmp, OPTIONS.info_dict)
    system_tgt.ResetFileMap()
    system_diff = common.BlockDifference("system", system_tgt, src=None)
    system_diff.WriteScript(script, output_zip)
  else:
    script.FormatPartition("/system")
    script.Mount("/system", recovery_mount_options)
    if not has_recovery_patch:
      script.UnpackPackageDir("recovery", "/system")
    script.UnpackPackageDir("system", "/system")

    symlinks = CopyPartitionFiles(system_items, input_zip, output_zip)
    script.MakeSymlinks(symlinks)

  boot_img = common.GetBootableImage("boot.img", "boot.img",
                                     OPTIONS.input_tmp, "BOOT")

  if not block_based:
    def output_sink(fn, data):
      common.ZipWriteStr(output_zip, "recovery/" + fn, data)
      system_items.Get("system/" + fn)

    common.MakeRecoveryPatch(OPTIONS.input_tmp, output_sink,
                             recovery_img, boot_img)

    system_items.GetMetadata(input_zip)
    system_items.Get("system").SetPermissions(script)

  if HasVendorPartition(input_zip):
    vendor_items = ItemSet("vendor", "META/vendor_filesystem_config.txt")
    script.ShowProgress(0.1, 0)

    if block_based:
      vendor_tgt = GetImage("vendor", OPTIONS.input_tmp, OPTIONS.info_dict)
      vendor_tgt.ResetFileMap()
      vendor_diff = common.BlockDifference("vendor", vendor_tgt)
      vendor_diff.WriteScript(script, output_zip)
    else:
      script.FormatPartition("/vendor")
      script.Mount("/vendor", recovery_mount_options)
      script.UnpackPackageDir("vendor", "/vendor")

      symlinks = CopyPartitionFiles(vendor_items, input_zip, output_zip)
      script.MakeSymlinks(symlinks)

      vendor_items.GetMetadata(input_zip)
      vendor_items.Get("vendor").SetPermissions(script)

  common.CheckSize(boot_img.data, "boot.img", OPTIONS.info_dict)
  common.ZipWriteStr(output_zip, "boot.img", boot_img.data)

  device_specific.FullOTA_PostValidate()

  if OPTIONS.backuptool:
    script.ShowProgress(0.02, 10)
    if block_based:
      script.Mount("/system")
    script.RunBackup("restore")
    if block_based:
      script.Unmount("/system")

  if block_based:
    script.Print("Flashing SuperSU...")
    common.ZipWriteStr(output_zip, "supersu/supersu.zip",
                   ""+input_zip.read("SYSTEM/addon.d/UPDATE-SuperSU.zip"))
    script.Mount("/system")
    script.FlashSuperSU()
  if block_based:
    script.Unmount("/system")

  script.ShowProgress(0.05, 5)
  script.WriteRawImage("/boot", "boot.img")

  script.ShowProgress(0.2, 10)
  device_specific.FullOTA_InstallEnd()

  if OPTIONS.extra_script is not None:
    script.AppendExtra(OPTIONS.extra_script)

  script.UnmountAll()

  if OPTIONS.wipe_user_data:
    script.ShowProgress(0.1, 10)
    script.FormatPartition("/data")

  if OPTIONS.two_step:
    script.AppendExtra("""
set_stage("%(bcb_dev)s", "");
""" % bcb_dev)
    script.AppendExtra("else\n")
    script.WriteRawImage("/boot", "recovery.img")
    script.AppendExtra("""
set_stage("%(bcb_dev)s", "2/3");
reboot_now("%(bcb_dev)s", "");
endif;
endif;
""" % bcb_dev)
  script.AddToZip(input_zip, output_zip, input_path=OPTIONS.updater_binary)
  WriteMetadata(metadata, output_zip)

  common.ZipWriteStr(output_zip, "system/build.prop",
                     ""+input_zip.read("SYSTEM/build.prop"))

  common.ZipWriteStr(output_zip, "META-INF/org/cyanogenmod/releasekey",
                     ""+input_zip.read("META/releasekey.txt"))

def WritePolicyConfig(file_name, output_zip):
  common.ZipWrite(output_zip, file_name, os.path.basename(file_name))

def WriteMetadata(metadata, output_zip):
  common.ZipWriteStr(output_zip, "META-INF/com/android/metadata",
                     "".join(["%s=%s\n" % kv
                              for kv in sorted(metadata.items())]))


def LoadPartitionFiles(z, partition):
  """Load all the files from the given partition in a given target-files
  ZipFile, and return a dict of {filename: File object}."""
  out = {}
  prefix = partition.upper() + "/"
  for info in z.infolist():
    if info.filename.startswith(prefix) and not IsSymlink(info):
      basefilename = info.filename[len(prefix):]
      fn = partition + "/" + basefilename
      data = z.read(info.filename)
      out[fn] = common.File(fn, data)
  return out


def GetBuildProp(prop, info_dict):
  """Return the fingerprint of the build of a given target-files info_dict."""
  try:
    return info_dict.get("build.prop", {})[prop]
  except KeyError:
    raise common.ExternalError("couldn't find %s in build.prop" % (prop,))


def AddToKnownPaths(filename, known_paths):
  if filename[-1] == "/":
    return
  dirs = filename.split("/")[:-1]
  while len(dirs) > 0:
    path = "/".join(dirs)
    if path in known_paths:
      break
    known_paths.add(path)
    dirs.pop()


def WriteBlockIncrementalOTAPackage(target_zip, source_zip, output_zip):
  source_version = OPTIONS.source_info_dict["recovery_api_version"]
  target_version = OPTIONS.target_info_dict["recovery_api_version"]

  if source_version == 0:
    print ("WARNING: generating edify script for a source that "
           "can't install it.")
  script = edify_generator.EdifyGenerator(
      source_version, OPTIONS.target_info_dict,
      fstab=OPTIONS.source_info_dict["fstab"])

  if OPTIONS.override_prop:
    metadata = {"post-timestamp": GetBuildProp("ro.build.date.utc",
                                               OPTIONS.target_info_dict),
                }
  else:
    metadata = {"pre-device": GetBuildProp("ro.product.device",
                                           OPTIONS.source_info_dict),
                "post-timestamp": GetBuildProp("ro.build.date.utc",
                                               OPTIONS.target_info_dict),
                }

  device_specific = common.DeviceSpecificParams(
      source_zip=source_zip,
      source_version=source_version,
      target_zip=target_zip,
      target_version=target_version,
      output_zip=output_zip,
      script=script,
      metadata=metadata,
      info_dict=OPTIONS.source_info_dict)

  # TODO: Currently this works differently from WriteIncrementalOTAPackage().
  # This function doesn't consider thumbprints when writing
  # metadata["pre/post-build"]. One possible reason is that the current
  # devices with thumbprints are all using file-based OTAs. Long term we
  # should factor out the common parts into a shared one to avoid further
  # divergence.
  if not OPTIONS.override_prop:
    source_fp = GetBuildProp("ro.build.fingerprint", OPTIONS.source_info_dict)
    target_fp = GetBuildProp("ro.build.fingerprint", OPTIONS.target_info_dict)
    metadata["pre-build"] = source_fp
    metadata["post-build"] = target_fp

  source_boot = common.GetBootableImage(
      "/tmp/boot.img", "boot.img", OPTIONS.source_tmp, "BOOT",
      OPTIONS.source_info_dict)
  target_boot = common.GetBootableImage(
      "/tmp/boot.img", "boot.img", OPTIONS.target_tmp, "BOOT")
  updating_boot = (not OPTIONS.two_step and
                   (source_boot.data != target_boot.data))

  target_recovery = common.GetBootableImage(
      "/tmp/recovery.img", "recovery.img", OPTIONS.target_tmp, "RECOVERY")

  system_src = GetImage("system", OPTIONS.source_tmp, OPTIONS.source_info_dict)
  system_tgt = GetImage("system", OPTIONS.target_tmp, OPTIONS.target_info_dict)

  blockimgdiff_version = 1
  if OPTIONS.info_dict:
    blockimgdiff_version = max(
        int(i) for i in
        OPTIONS.info_dict.get("blockimgdiff_versions", "1").split(","))

  system_diff = common.BlockDifference("system", system_tgt, system_src,
                                       version=blockimgdiff_version)

  if HasVendorPartition(target_zip):
    if not HasVendorPartition(source_zip):
      raise RuntimeError("can't generate incremental that adds /vendor")
    vendor_src = GetImage("vendor", OPTIONS.source_tmp,
                          OPTIONS.source_info_dict)
    vendor_tgt = GetImage("vendor", OPTIONS.target_tmp,
                          OPTIONS.target_info_dict)
    vendor_diff = common.BlockDifference("vendor", vendor_tgt, vendor_src,
                                         version=blockimgdiff_version)
  else:
    vendor_diff = None

  oem_props = OPTIONS.target_info_dict.get("oem_fingerprint_properties")
  recovery_mount_options = OPTIONS.source_info_dict.get(
      "recovery_mount_options")
  oem_dict = None
  if oem_props is not None and len(oem_props) > 0:
    if OPTIONS.oem_source is None:
      raise common.ExternalError("OEM source required for this build")
    script.Mount("/oem", recovery_mount_options)
    oem_dict = common.LoadDictionaryFromLines(
        open(OPTIONS.oem_source).readlines())

  AppendAssertions(script, OPTIONS.target_info_dict, oem_dict)
  device_specific.IncrementalOTA_Assertions()

  # Two-step incremental package strategy (in chronological order,
  # which is *not* the order in which the generated script has
  # things):
  #
  # if stage is not "2/3" or "3/3":
  #    do verification on current system
  #    write recovery image to boot partition
  #    set stage to "2/3"
  #    reboot to boot partition and restart recovery
  # else if stage is "2/3":
  #    write recovery image to recovery partition
  #    set stage to "3/3"
  #    reboot to recovery partition and restart recovery
  # else:
  #    (stage must be "3/3")
  #    perform update:
  #       patch system files, etc.
  #       force full install of new boot image
  #       set up system to update recovery partition on first boot
  #    complete script normally
  #    (allow recovery to mark itself finished and reboot)

  if OPTIONS.two_step:
    if not OPTIONS.source_info_dict.get("multistage_support", None):
      assert False, "two-step packages not supported by this build"
    fs = OPTIONS.source_info_dict["fstab"]["/misc"]
    assert fs.fs_type.upper() == "EMMC", \
        "two-step packages only supported on devices with EMMC /misc partitions"
    bcb_dev = {"bcb_dev": fs.device}
    common.ZipWriteStr(output_zip, "recovery.img", target_recovery.data)
    script.AppendExtra("""
if get_stage("%(bcb_dev)s") == "2/3" then
""" % bcb_dev)
    script.AppendExtra("sleep(20);\n")
    script.WriteRawImage("/recovery", "recovery.img")
    script.AppendExtra("""
set_stage("%(bcb_dev)s", "3/3");
reboot_now("%(bcb_dev)s", "recovery");
else if get_stage("%(bcb_dev)s") != "3/3" then
""" % bcb_dev)

  # Dump fingerprints
  script.Print("Source: %s" % CalculateFingerprint(
      oem_props, oem_dict, OPTIONS.source_info_dict))
  script.Print("Target: %s" % CalculateFingerprint(
      oem_props, oem_dict, OPTIONS.target_info_dict))

  script.Print("Verifying current system...")

  device_specific.IncrementalOTA_VerifyBegin()

  if oem_props is None:
    # When blockimgdiff version is less than 3 (non-resumable block-based OTA),
    # patching on a device that's already on the target build will damage the
    # system. Because operations like move don't check the block state, they
    # always apply the changes unconditionally.
    if blockimgdiff_version <= 2:
      script.AssertSomeFingerprint(source_fp)
    else:
      script.AssertSomeFingerprint(source_fp, target_fp)
  else:
    if blockimgdiff_version <= 2:
      script.AssertSomeThumbprint(
          GetBuildProp("ro.build.thumbprint", OPTIONS.source_info_dict))
    else:
      script.AssertSomeThumbprint(
          GetBuildProp("ro.build.thumbprint", OPTIONS.target_info_dict),
          GetBuildProp("ro.build.thumbprint", OPTIONS.source_info_dict))

  if updating_boot:
    boot_type, boot_device = common.GetTypeAndDevice(
        "/boot", OPTIONS.source_info_dict)
    d = common.Difference(target_boot, source_boot)
    _, _, d = d.ComputePatch()
    if d is None:
      include_full_boot = True
      common.ZipWriteStr(output_zip, "boot.img", target_boot.data)
    else:
      include_full_boot = False

      print("boot      target: %d  source: %d  diff: %d" % (
          target_boot.size, source_boot.size, len(d)))

      common.ZipWriteStr(output_zip, "patch/boot.img.p", d)

      script.PatchCheck("%s:%s:%d:%s:%d:%s" %
                        (boot_type, boot_device,
                         source_boot.size, source_boot.sha1,
                         target_boot.size, target_boot.sha1))

  device_specific.IncrementalOTA_VerifyEnd()

  if OPTIONS.two_step:
    script.WriteRawImage("/boot", "recovery.img")
    script.AppendExtra("""
set_stage("%(bcb_dev)s", "2/3");
reboot_now("%(bcb_dev)s", "");
else
""" % bcb_dev)

  # Verify the existing partitions.
  system_diff.WriteVerifyScript(script)
  if vendor_diff:
    vendor_diff.WriteVerifyScript(script)

  script.Comment("---- start making changes here ----")

  device_specific.IncrementalOTA_InstallBegin()

  system_diff.WriteScript(script, output_zip,
                          progress=0.8 if vendor_diff else 0.9)
  if vendor_diff:
    vendor_diff.WriteScript(script, output_zip, progress=0.1)

  if OPTIONS.two_step:
    common.ZipWriteStr(output_zip, "boot.img", target_boot.data)
    script.WriteRawImage("/boot", "boot.img")
    print("writing full boot image (forced by two-step mode)")

  if not OPTIONS.two_step:
    if updating_boot:
      if include_full_boot:
        print("boot image changed; including full.")
        script.Print("Installing boot image...")
        script.WriteRawImage("/boot", "boot.img")
      else:
        # Produce the boot image by applying a patch to the current
        # contents of the boot partition, and write it back to the
        # partition.
        print("boot image changed; including patch.")
        script.Print("Patching boot image...")
        script.ShowProgress(0.1, 10)
        script.ApplyPatch("%s:%s:%d:%s:%d:%s"
                          % (boot_type, boot_device,
                             source_boot.size, source_boot.sha1,
                             target_boot.size, target_boot.sha1),
                          "-",
                          target_boot.size, target_boot.sha1,
                          source_boot.sha1, "patch/boot.img.p")
    else:
      print("boot image unchanged; skipping.")

  # Do device-specific installation (eg, write radio image).
  device_specific.IncrementalOTA_InstallEnd()

  if OPTIONS.extra_script is not None:
    script.AppendExtra(OPTIONS.extra_script)

  if OPTIONS.wipe_user_data:
    script.Print("Erasing user data...")
    script.FormatPartition("/data")

  if OPTIONS.two_step:
    script.AppendExtra("""
set_stage("%(bcb_dev)s", "");
endif;
endif;
""" % bcb_dev)

  script.SetProgress(1)
  script.AddToZip(target_zip, output_zip, input_path=OPTIONS.updater_binary)
  WriteMetadata(metadata, output_zip)


class FileDifference(object):
  def __init__(self, partition, source_zip, target_zip, output_zip):
    self.deferred_patch_list = None
    print("Loading target...")
    self.target_data = target_data = LoadPartitionFiles(target_zip, partition)
    print("Loading source...")
    self.source_data = source_data = LoadPartitionFiles(source_zip, partition)

    self.verbatim_targets = verbatim_targets = []
    self.patch_list = patch_list = []
    diffs = []
    self.renames = renames = {}
    known_paths = set()
    largest_source_size = 0

    matching_file_cache = {}
    for fn, sf in source_data.items():
      assert fn == sf.name
      matching_file_cache["path:" + fn] = sf
      if fn in target_data.keys():
        AddToKnownPaths(fn, known_paths)
      # Only allow eligibility for filename/sha matching
      # if there isn't a perfect path match.
      if target_data.get(sf.name) is None:
        matching_file_cache["file:" + fn.split("/")[-1]] = sf
        matching_file_cache["sha:" + sf.sha1] = sf

    for fn in sorted(target_data.keys()):
      tf = target_data[fn]
      assert fn == tf.name
      sf = ClosestFileMatch(tf, matching_file_cache, renames)
      if sf is not None and sf.name != tf.name:
        print("File has moved from " + sf.name + " to " + tf.name)
        renames[sf.name] = tf

      if sf is None or fn in OPTIONS.require_verbatim:
        # This file should be included verbatim
        if fn in OPTIONS.prohibit_verbatim:
          raise common.ExternalError("\"%s\" must be sent verbatim" % (fn,))
        print("send", fn, "verbatim")
        tf.AddToZip(output_zip)
        verbatim_targets.append((fn, tf.size, tf.sha1))
        if fn in target_data.keys():
          AddToKnownPaths(fn, known_paths)
      elif tf.sha1 != sf.sha1:
        # File is different; consider sending as a patch
        diffs.append(common.Difference(tf, sf))
      else:
        # Target file data identical to source (may still be renamed)
        pass

    common.ComputeDifferences(diffs)

    for diff in diffs:
      tf, sf, d = diff.GetPatch()
      path = "/".join(tf.name.split("/")[:-1])
      if d is None or len(d) > tf.size * OPTIONS.patch_threshold or \
          path not in known_paths:
        # patch is almost as big as the file; don't bother patching
        # or a patch + rename cannot take place due to the target
        # directory not existing
        tf.AddToZip(output_zip)
        verbatim_targets.append((tf.name, tf.size, tf.sha1))
        if sf.name in renames:
          del renames[sf.name]
        AddToKnownPaths(tf.name, known_paths)
      else:
        common.ZipWriteStr(output_zip, "patch/" + sf.name + ".p", d)
        patch_list.append((tf, sf, tf.size, common.sha1(d).hexdigest()))
        largest_source_size = max(largest_source_size, sf.size)

    self.largest_source_size = largest_source_size

  def EmitVerification(self, script):
    so_far = 0
    for tf, sf, _, _ in self.patch_list:
      if tf.name != sf.name:
        script.SkipNextActionIfTargetExists(tf.name, tf.sha1)
      script.PatchCheck("/"+sf.name, tf.sha1, sf.sha1)
      so_far += sf.size
    return so_far

  def EmitExplicitTargetVerification(self, script):
    for fn, _, sha1 in self.verbatim_targets:
      if fn[-1] != "/":
        script.FileCheck("/"+fn, sha1)
    for tf, _, _, _ in self.patch_list:
      script.FileCheck(tf.name, tf.sha1)

  def RemoveUnneededFiles(self, script, extras=()):
    script.DeleteFiles(
        ["/" + i[0] for i in self.verbatim_targets] +
        ["/" + i for i in sorted(self.source_data)
         if i not in self.target_data and i not in self.renames] +
        list(extras))

  def TotalPatchSize(self):
    return sum(i[1].size for i in self.patch_list)

  def EmitPatches(self, script, total_patch_size, so_far):
    self.deferred_patch_list = deferred_patch_list = []
    for item in self.patch_list:
      tf, sf, _, _ = item
      if tf.name == "system/build.prop":
        deferred_patch_list.append(item)
        continue
      if sf.name != tf.name:
        script.SkipNextActionIfTargetExists(tf.name, tf.sha1)
      script.ApplyPatch("/" + sf.name, "-", tf.size, tf.sha1, sf.sha1,
                        "patch/" + sf.name + ".p")
      so_far += tf.size
      script.SetProgress(so_far / total_patch_size)
    return so_far

  def EmitDeferredPatches(self, script):
    for item in self.deferred_patch_list:
      tf, sf, _, _ = item
      script.ApplyPatch("/"+sf.name, "-", tf.size, tf.sha1, sf.sha1,
                        "patch/" + sf.name + ".p")
    script.SetPermissions("/system/build.prop", 0, 0, 0o644, None, None)

  def EmitRenames(self, script):
    if len(self.renames) > 0:
      script.Print("Renaming files...")
      for src, tgt in self.renames.items():
        print("Renaming " + src + " to " + tgt.name)
        script.RenameFile(src, tgt.name)


def WriteIncrementalOTAPackage(target_zip, source_zip, output_zip):
  target_has_recovery_patch = HasRecoveryPatch(target_zip)
  source_has_recovery_patch = HasRecoveryPatch(source_zip)

  if (OPTIONS.block_based and
      target_has_recovery_patch and
      source_has_recovery_patch):
    return WriteBlockIncrementalOTAPackage(target_zip, source_zip, output_zip)

  source_version = OPTIONS.source_info_dict["recovery_api_version"]
  target_version = OPTIONS.target_info_dict["recovery_api_version"]

  if source_version == 0:
    print ("WARNING: generating edify script for a source that "
           "can't install it.")
  script = edify_generator.EdifyGenerator(
      source_version, OPTIONS.target_info_dict,
      fstab=OPTIONS.source_info_dict["fstab"])

  oem_props = OPTIONS.info_dict.get("oem_fingerprint_properties")
  recovery_mount_options = OPTIONS.source_info_dict.get(
      "recovery_mount_options")
  oem_dict = None
  if oem_props is not None and len(oem_props) > 0:
    if OPTIONS.oem_source is None:
      raise common.ExternalError("OEM source required for this build")
    script.Mount("/oem", recovery_mount_options)
    oem_dict = common.LoadDictionaryFromLines(
        open(OPTIONS.oem_source).readlines())

  if OPTIONS.override_prop:
    metadata = {"post-timestamp": GetBuildProp("ro.build.date.utc",
                                               OPTIONS.target_info_dict),
                }
  else:
    metadata = {"pre-device": GetOemProperty("ro.product.device", oem_props, oem_dict,
                                           OPTIONS.source_info_dict),
                "post-timestamp": GetBuildProp("ro.build.date.utc",
                                               OPTIONS.target_info_dict),
                }

  device_specific = common.DeviceSpecificParams(
      source_zip=source_zip,
      source_version=source_version,
      target_zip=target_zip,
      target_version=target_version,
      output_zip=output_zip,
      script=script,
      metadata=metadata,
      info_dict=OPTIONS.source_info_dict)

  system_diff = FileDifference("system", source_zip, target_zip, output_zip)
  script.Mount("/system", recovery_mount_options)
  if HasVendorPartition(target_zip):
    vendor_diff = FileDifference("vendor", source_zip, target_zip, output_zip)
    script.Mount("/vendor", recovery_mount_options)
  else:
    vendor_diff = None

  if not OPTIONS.override_prop:
    target_fp = CalculateFingerprint(oem_props, oem_dict, OPTIONS.target_info_dict)
    source_fp = CalculateFingerprint(oem_props, oem_dict, OPTIONS.source_info_dict)

    if oem_props is None:
      script.AssertSomeFingerprint(source_fp, target_fp)
    else:
      script.AssertSomeThumbprint(
          GetBuildProp("ro.build.thumbprint", OPTIONS.target_info_dict),
          GetBuildProp("ro.build.thumbprint", OPTIONS.source_info_dict))

    metadata["pre-build"] = source_fp
    metadata["post-build"] = target_fp

  source_boot = common.GetBootableImage(
      "/tmp/boot.img", "boot.img", OPTIONS.source_tmp, "BOOT",
      OPTIONS.source_info_dict)
  target_boot = common.GetBootableImage(
      "/tmp/boot.img", "boot.img", OPTIONS.target_tmp, "BOOT")
  updating_boot = (not OPTIONS.two_step and
                   (source_boot.data != target_boot.data))

  source_recovery = common.GetBootableImage(
      "/tmp/recovery.img", "recovery.img", OPTIONS.source_tmp, "RECOVERY",
      OPTIONS.source_info_dict)
  target_recovery = common.GetBootableImage(
      "/tmp/recovery.img", "recovery.img", OPTIONS.target_tmp, "RECOVERY")
  updating_recovery = (source_recovery.data != target_recovery.data)

  # Here's how we divide up the progress bar:
  #  0.1 for verifying the start state (PatchCheck calls)
  #  0.8 for applying patches (ApplyPatch calls)
  #  0.1 for unpacking verbatim files, symlinking, and doing the
  #      device-specific commands.

  AppendAssertions(script, OPTIONS.target_info_dict, oem_dict)
  device_specific.IncrementalOTA_Assertions()

  # Two-step incremental package strategy (in chronological order,
  # which is *not* the order in which the generated script has
  # things):
  #
  # if stage is not "2/3" or "3/3":
  #    do verification on current system
  #    write recovery image to boot partition
  #    set stage to "2/3"
  #    reboot to boot partition and restart recovery
  # else if stage is "2/3":
  #    write recovery image to recovery partition
  #    set stage to "3/3"
  #    reboot to recovery partition and restart recovery
  # else:
  #    (stage must be "3/3")
  #    perform update:
  #       patch system files, etc.
  #       force full install of new boot image
  #       set up system to update recovery partition on first boot
  #    complete script normally
  #    (allow recovery to mark itself finished and reboot)

  if OPTIONS.two_step:
    if not OPTIONS.source_info_dict.get("multistage_support", None):
      assert False, "two-step packages not supported by this build"
    fs = OPTIONS.source_info_dict["fstab"]["/misc"]
    assert fs.fs_type.upper() == "EMMC", \
        "two-step packages only supported on devices with EMMC /misc partitions"
    bcb_dev = {"bcb_dev": fs.device}
    common.ZipWriteStr(output_zip, "recovery.img", target_recovery.data)
    script.AppendExtra("""
if get_stage("%(bcb_dev)s") == "2/3" then
""" % bcb_dev)
    script.AppendExtra("sleep(20);\n")
    script.WriteRawImage("/recovery", "recovery.img")
    script.AppendExtra("""
set_stage("%(bcb_dev)s", "3/3");
reboot_now("%(bcb_dev)s", "recovery");
else if get_stage("%(bcb_dev)s") != "3/3" then
""" % bcb_dev)

  # Dump fingerprints
  script.Print("Source: %s" % source_fp)
  script.Print("Target: %s" % target_fp)

  script.Print("Verifying current system...")

  device_specific.IncrementalOTA_VerifyBegin()

  script.ShowProgress(0.1, 0)
  so_far = system_diff.EmitVerification(script)
  if vendor_diff:
    so_far += vendor_diff.EmitVerification(script)

  if updating_boot:
    d = common.Difference(target_boot, source_boot)
    _, _, d = d.ComputePatch()
    print("boot      target: %d  source: %d  diff: %d" % (
        target_boot.size, source_boot.size, len(d)))

    common.ZipWriteStr(output_zip, "patch/boot.img.p", d)

    boot_type, boot_device = common.GetTypeAndDevice(
        "/boot", OPTIONS.source_info_dict)

    script.PatchCheck("%s:%s:%d:%s:%d:%s" %
                      (boot_type, boot_device,
                       source_boot.size, source_boot.sha1,
                       target_boot.size, target_boot.sha1))
    so_far += source_boot.size

  size = []
  if system_diff.patch_list:
    size.append(system_diff.largest_source_size)
  if vendor_diff:
    if vendor_diff.patch_list:
      size.append(vendor_diff.largest_source_size)
  if size or updating_recovery or updating_boot:
    script.CacheFreeSpaceCheck(max(size))

  device_specific.IncrementalOTA_VerifyEnd()

  if OPTIONS.two_step:
    script.WriteRawImage("/boot", "recovery.img")
    script.AppendExtra("""
set_stage("%(bcb_dev)s", "2/3");
reboot_now("%(bcb_dev)s", "");
else
""" % bcb_dev)

  script.Comment("---- start making changes here ----")

  device_specific.IncrementalOTA_InstallBegin()

  if OPTIONS.two_step:
    common.ZipWriteStr(output_zip, "boot.img", target_boot.data)
    script.WriteRawImage("/boot", "boot.img")
    print("writing full boot image (forced by two-step mode)")

  script.Print("Removing unneeded files...")
  system_diff.RemoveUnneededFiles(script, ("/system/recovery.img",))
  if vendor_diff:
    vendor_diff.RemoveUnneededFiles(script)

  script.ShowProgress(0.8, 0)
  total_patch_size = 1.0 + system_diff.TotalPatchSize()
  if vendor_diff:
    total_patch_size += vendor_diff.TotalPatchSize()
  if updating_boot:
    total_patch_size += target_boot.size

  script.Print("Patching system files...")
  so_far = system_diff.EmitPatches(script, total_patch_size, 0)
  if vendor_diff:
    script.Print("Patching vendor files...")
    so_far = vendor_diff.EmitPatches(script, total_patch_size, so_far)

  if not OPTIONS.two_step:
    if updating_boot:
      # Produce the boot image by applying a patch to the current
      # contents of the boot partition, and write it back to the
      # partition.
      script.Print("Patching boot image...")
      script.ApplyPatch("%s:%s:%d:%s:%d:%s"
                        % (boot_type, boot_device,
                           source_boot.size, source_boot.sha1,
                           target_boot.size, target_boot.sha1),
                        "-",
                        target_boot.size, target_boot.sha1,
                        source_boot.sha1, "patch/boot.img.p")
      so_far += target_boot.size
      script.SetProgress(so_far / total_patch_size)
      print("boot image changed; including.")
    else:
      print("boot image unchanged; skipping.")

  system_items = ItemSet("system", "META/filesystem_config.txt")
  if vendor_diff:
    vendor_items = ItemSet("vendor", "META/vendor_filesystem_config.txt")

  if updating_recovery:
    # Recovery is generated as a patch using both the boot image
    # (which contains the same linux kernel as recovery) and the file
    # /system/etc/recovery-resource.dat (which contains all the images
    # used in the recovery UI) as sources.  This lets us minimize the
    # size of the patch, which must be included in every OTA package.
    #
    # For older builds where recovery-resource.dat is not present, we
    # use only the boot image as the source.

    if not target_has_recovery_patch:
      def output_sink(fn, data):
        common.ZipWriteStr(output_zip, "recovery/" + fn, data)
        system_items.Get("system/" + fn)

      common.MakeRecoveryPatch(OPTIONS.target_tmp, output_sink,
                               target_recovery, target_boot)
      script.DeleteFiles(["/system/recovery-from-boot.p",
                          "/system/etc/install-recovery.sh"])
    print("recovery image changed; including as patch from boot.")
  else:
    print("recovery image unchanged; skipping.")

  script.ShowProgress(0.1, 10)

  target_symlinks = CopyPartitionFiles(system_items, target_zip, None)
  if vendor_diff:
    target_symlinks.extend(CopyPartitionFiles(vendor_items, target_zip, None))

  temp_script = script.MakeTemporary()
  system_items.GetMetadata(target_zip)
  system_items.Get("system").SetPermissions(temp_script)
  if vendor_diff:
    vendor_items.GetMetadata(target_zip)
    vendor_items.Get("vendor").SetPermissions(temp_script)

  # Note that this call will mess up the trees of Items, so make sure
  # we're done with them.
  source_symlinks = CopyPartitionFiles(system_items, source_zip, None)
  if vendor_diff:
    source_symlinks.extend(CopyPartitionFiles(vendor_items, source_zip, None))

  target_symlinks_d = dict([(i[1], i[0]) for i in target_symlinks])
  source_symlinks_d = dict([(i[1], i[0]) for i in source_symlinks])

  # Delete all the symlinks in source that aren't in target.  This
  # needs to happen before verbatim files are unpacked, in case a
  # symlink in the source is replaced by a real file in the target.

  # If a symlink in the source will be replaced by a regular file, we cannot
  # delete the symlink/file in case the package gets applied again. For such
  # a symlink, we prepend a sha1_check() to detect if it has been updated.
  # (Bug: 23646151)
  replaced_symlinks = dict()
  if system_diff:
    for i in system_diff.verbatim_targets:
      replaced_symlinks["/%s" % (i[0],)] = i[2]
  if vendor_diff:
    for i in vendor_diff.verbatim_targets:
      replaced_symlinks["/%s" % (i[0],)] = i[2]

  if system_diff:
    for tf in system_diff.renames.values():
      replaced_symlinks["/%s" % (tf.name,)] = tf.sha1
  if vendor_diff:
    for tf in vendor_diff.renames.values():
      replaced_symlinks["/%s" % (tf.name,)] = tf.sha1

  always_delete = []
  may_delete = []
  for dest, link in source_symlinks:
    if link not in target_symlinks_d:
      if link in replaced_symlinks:
        may_delete.append((link, replaced_symlinks[link]))
      else:
        always_delete.append(link)
  script.DeleteFiles(always_delete)
  script.DeleteFilesIfNotMatching(may_delete)

  if system_diff.verbatim_targets:
    script.Print("Unpacking new system files...")
    script.UnpackPackageDir("system", "/system")
  if vendor_diff and vendor_diff.verbatim_targets:
    script.Print("Unpacking new vendor files...")
    script.UnpackPackageDir("vendor", "/vendor")

  if updating_recovery and not target_has_recovery_patch:
    script.Print("Unpacking new recovery...")
    script.UnpackPackageDir("recovery", "/system")

  system_diff.EmitRenames(script)
  if vendor_diff:
    vendor_diff.EmitRenames(script)

  script.Print("Symlinks and permissions...")

  # Create all the symlinks that don't already exist, or point to
  # somewhere different than what we want.  Delete each symlink before
  # creating it, since the 'symlink' command won't overwrite.
  to_create = []
  for dest, link in target_symlinks:
    if link in source_symlinks_d:
      if dest != source_symlinks_d[link]:
        to_create.append((dest, link))
    else:
      to_create.append((dest, link))
  script.DeleteFiles([i[1] for i in to_create])
  script.MakeSymlinks(to_create)

  # Now that the symlinks are created, we can set all the
  # permissions.
  script.AppendScript(temp_script)

  # Do device-specific installation (eg, write radio image).
  device_specific.IncrementalOTA_InstallEnd()

  if OPTIONS.extra_script is not None:
    script.AppendExtra(OPTIONS.extra_script)

  # Patch the build.prop file last, so if something fails but the
  # device can still come up, it appears to be the old build and will
  # get set the OTA package again to retry.
  script.Print("Patching remaining system files...")
  system_diff.EmitDeferredPatches(script)

  if OPTIONS.wipe_user_data:
    script.Print("Erasing user data...")
    script.FormatPartition("/data")

  if OPTIONS.two_step:
    script.AppendExtra("""
set_stage("%(bcb_dev)s", "");
endif;
endif;
""" % bcb_dev)

  if OPTIONS.verify and system_diff:
    script.Print("Remounting and verifying system partition files...")
    script.Unmount("/system")
    script.Mount("/system")
    system_diff.EmitExplicitTargetVerification(script)

  if OPTIONS.verify and vendor_diff:
    script.Print("Remounting and verifying vendor partition files...")
    script.Unmount("/vendor")
    script.Mount("/vendor")
    vendor_diff.EmitExplicitTargetVerification(script)
  script.AddToZip(target_zip, output_zip, input_path=OPTIONS.updater_binary)

  WriteMetadata(metadata, output_zip)

def main(argv):

  def option_handler(o, a):
    if o == "--board_config":
      pass   # deprecated
    elif o in ("-k", "--package_key"):
      OPTIONS.package_key = a
    elif o in ("-i", "--incremental_from"):
      OPTIONS.incremental_source = a
    elif o == "--full_radio":
      OPTIONS.full_radio = True
    elif o == "--full_bootloader":
      OPTIONS.full_bootloader = True
    elif o in ("-w", "--wipe_user_data"):
      OPTIONS.wipe_user_data = True
    elif o in ("-n", "--no_prereq"):
      OPTIONS.omit_prereq = True
    elif o in ("-o", "--oem_settings"):
      OPTIONS.oem_source = a
    elif o in ("-e", "--extra_script"):
      OPTIONS.extra_script = a
    elif o in ("-a", "--aslr_mode"):
      if a in ("on", "On", "true", "True", "yes", "Yes"):
        OPTIONS.aslr_mode = True
      else:
        OPTIONS.aslr_mode = False
    elif o in ("-t", "--worker_threads"):
      if a.isdigit():
        OPTIONS.worker_threads = int(a)
      else:
        raise ValueError("Cannot parse value %r for option %r - only "
                         "integers are allowed." % (a, o))
    elif o in ("-2", "--two_step"):
      OPTIONS.two_step = True
    elif o == "--no_signing":
      OPTIONS.no_signing = True
    elif o == "--verify":
      OPTIONS.verify = True
    elif o == "--block":
      OPTIONS.block_based = True
    elif o in ("-b", "--binary",):
      OPTIONS.updater_binary = a
    elif o in ("--no_fallback_to_full",):
      OPTIONS.fallback_to_full = False
    elif o == "--stash_threshold":
      try:
        OPTIONS.stash_threshold = float(a)
      except ValueError:
        raise ValueError("Cannot parse value %r for option %r - expecting "
                         "a float" % (a, o))
    elif o in ("--backup",):
      OPTIONS.backuptool = bool(a.lower() == 'true')
    elif o in ("--override_device",):
      OPTIONS.override_device = a
    elif o in ("--override_prop",):
      OPTIONS.override_prop = bool(a.lower() == 'true')
    else:
      return False
    return True

  args = common.ParseOptions(argv, __doc__,
                             extra_opts="b:k:i:d:wne:t:a:2o:",
                             extra_long_opts=[
                                 "board_config=",
                                 "package_key=",
                                 "incremental_from=",
                                 "full_radio",
                                 "full_bootloader",
                                 "wipe_user_data",
                                 "no_prereq",
                                 "extra_script=",
                                 "worker_threads=",
                                 "aslr_mode=",
                                 "two_step",
                                 "no_signing",
                                 "block",
                                 "binary=",
                                 "oem_settings=",
                                 "verify",
                                 "no_fallback_to_full",
                                 "stash_threshold=",
                                 "backup=",
                                 "override_device=",
                                 "override_prop="
                             ], extra_option_handler=option_handler)

  if len(args) != 2:
    common.Usage(__doc__)
    sys.exit(1)

  if OPTIONS.extra_script is not None:
    OPTIONS.extra_script = open(OPTIONS.extra_script).read()

  print("unzipping target target-files...")
  OPTIONS.input_tmp, input_zip = common.UnzipTemp(args[0])

  OPTIONS.target_tmp = OPTIONS.input_tmp
  OPTIONS.info_dict = common.LoadInfoDict(input_zip)

  # If this image was originally labelled with SELinux contexts, make sure we
  # also apply the labels in our new image. During building, the "file_contexts"
  # is in the out/ directory tree, but for repacking from target-files.zip it's
  # in the root directory of the ramdisk.
  if "selinux_fc" in OPTIONS.info_dict:
    OPTIONS.info_dict["selinux_fc"] = os.path.join(
        OPTIONS.input_tmp, "BOOT", "RAMDISK", "file_contexts")

  if OPTIONS.verbose:
    print("--- target info ---")
    common.DumpInfoDict(OPTIONS.info_dict)

  # If the caller explicitly specified the device-specific extensions
  # path via -s/--device_specific, use that.  Otherwise, use
  # META/releasetools.py if it is present in the target target_files.
  # Otherwise, take the path of the file from 'tool_extensions' in the
  # info dict and look for that in the local filesystem, relative to
  # the current directory.

  if OPTIONS.device_specific is None:
    from_input = os.path.join(OPTIONS.input_tmp, "META", "releasetools.py")
    if os.path.exists(from_input):
      print("(using device-specific extensions from target_files)")
      OPTIONS.device_specific = from_input
    else:
      OPTIONS.device_specific = OPTIONS.info_dict.get("tool_extensions", None)

  if OPTIONS.device_specific is not None:
    OPTIONS.device_specific = os.path.abspath(OPTIONS.device_specific)

  while True:

    if OPTIONS.no_signing:
      if os.path.exists(args[1]):
        os.unlink(args[1])
      output_zip = zipfile.ZipFile(args[1], "w",
                                   compression=zipfile.ZIP_DEFLATED)
    else:
      temp_zip_file = tempfile.NamedTemporaryFile()
      output_zip = zipfile.ZipFile(temp_zip_file, "w",
                                   compression=zipfile.ZIP_DEFLATED)

    cache_size = OPTIONS.info_dict.get("cache_size", None)
    if cache_size is None:
      print("--- can't determine the cache partition size ---")
    OPTIONS.cache_size = cache_size

    if OPTIONS.incremental_source is None:
      WriteFullOTAPackage(input_zip, output_zip)
      if OPTIONS.package_key is None:
        OPTIONS.package_key = OPTIONS.info_dict.get(
            "default_system_dev_certificate",
            "build/target/product/security/testkey")
      common.ZipClose(output_zip)
      break

    else:
      print("unzipping source target-files...")
      OPTIONS.source_tmp, source_zip = common.UnzipTemp(
          OPTIONS.incremental_source)
      OPTIONS.target_info_dict = OPTIONS.info_dict
      OPTIONS.source_info_dict = common.LoadInfoDict(source_zip)
      if "selinux_fc" in OPTIONS.source_info_dict:
        OPTIONS.source_info_dict["selinux_fc"] = os.path.join(
            OPTIONS.source_tmp, "BOOT", "RAMDISK", "file_contexts")
      if OPTIONS.package_key is None:
        OPTIONS.package_key = OPTIONS.source_info_dict.get(
            "default_system_dev_certificate",
            "build/target/product/security/testkey")
      if OPTIONS.verbose:
        print("--- source info ---")
        common.DumpInfoDict(OPTIONS.source_info_dict)
      try:
        WriteIncrementalOTAPackage(input_zip, source_zip, output_zip)
        common.ZipClose(output_zip)
        break
      except ValueError:
        if not OPTIONS.fallback_to_full:
          raise
        print("--- failed to build incremental; falling back to full ---")
        OPTIONS.incremental_source = None
        common.ZipClose(output_zip)

  if not OPTIONS.no_signing:
    SignOutput(temp_zip_file.name, args[1])
    temp_zip_file.close()

  print("done.")


if __name__ == '__main__':
  try:
    common.CloseInheritedPipes()
    main(sys.argv[1:])
  except common.ExternalError as e:
    print()
    print("   ERROR: %s" % e)
    print()
    sys.exit(1)
  finally:
    common.Cleanup()
