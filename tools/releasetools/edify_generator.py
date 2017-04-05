# Copyright (C) 2009 The Android Open Source Project
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

import re

import common

class EdifyGenerator(object):
  """Class to generate scripts in the 'edify' recovery script language
  used from donut onwards."""

  def __init__(self, version, info, fstab=None):
    self.script = []
    self.mounts = set()
    self._required_cache = 0
    self.version = version
    self.info = info
    if fstab is None:
      self.fstab = self.info.get("fstab", None)
    else:
      self.fstab = fstab

  def MakeTemporary(self):
    """Make a temporary script object whose commands can latter be
    appended to the parent script with AppendScript().  Used when the
    caller wants to generate script commands out-of-order."""
    x = EdifyGenerator(self.version, self.info)
    x.mounts = self.mounts
    return x

  @property
  def required_cache(self):
    """Return the minimum cache size to apply the update."""
    return self._required_cache

  @staticmethod
  def WordWrap(cmd, linelen=80):
    """'cmd' should be a function call with null characters after each
    parameter (eg, "somefun(foo,\0bar,\0baz)").  This function wraps cmd
    to a given line length, replacing nulls with spaces and/or newlines
    to format it nicely."""
    indent = cmd.index("(")+1
    out = []
    first = True
    x = re.compile("^(.{,%d})\0" % (linelen-indent,))
    while True:
      if not first:
        out.append(" " * indent)
      first = False
      m = x.search(cmd)
      if not m:
        parts = cmd.split("\0", 1)
        out.append(parts[0]+"\n")
        if len(parts) == 1:
          break
        else:
          cmd = parts[1]
          continue
      out.append(m.group(1)+"\n")
      cmd = cmd[m.end():]

    return "".join(out).replace("\0", " ").rstrip("\n")

  def AppendScript(self, other):
    """Append the contents of another script (which should be created
    with temporary=True) to this one."""
    self.script.extend(other.script)

  def AssertOemProperty(self, name, value):
    """Assert that a property on the OEM paritition matches a value."""
    if not name:
      raise ValueError("must specify an OEM property")
    if not value:
      raise ValueError("must specify the OEM value")
    if common.OPTIONS.oem_no_mount:
      cmd = ('getprop("{name}") == "{value}" || '
             'abort("E{code}: This package expects the value \\"{value}\\" for '
             '\\"{name}\\"; this has value \\"" + '
             'getprop("{name}") + "\\".");').format(
                 code=common.ErrorCode.OEM_PROP_MISMATCH,
                 name=name, value=value)
    else:
      cmd = ('file_getprop("/oem/oem.prop", "{name}") == "{value}" || '
             'abort("E{code}: This package expects the value \\"{value}\\" for '
             '\\"{name}\\" on the OEM partition; this has value \\"" + '
             'file_getprop("/oem/oem.prop", "{name}") + "\\".");').format(
                 code=common.ErrorCode.OEM_PROP_MISMATCH,
                 name=name, value=value)
    self.script.append(cmd)

  def AssertSomeFingerprint(self, *fp):
    """Assert that the current recovery build fingerprint is one of *fp."""
    if not fp:
      raise ValueError("must specify some fingerprints")
    cmd = (' ||\n    '.join([('getprop("ro.build.fingerprint") == "%s"') % i
                             for i in fp]) +
           ' ||\n    abort("E%d: Package expects build fingerprint of %s; '
           'this device has " + getprop("ro.build.fingerprint") + ".");') % (
               common.ErrorCode.FINGERPRINT_MISMATCH, " or ".join(fp))
    self.script.append(cmd)

  def AssertSomeThumbprint(self, *fp):
    """Assert that the current recovery build thumbprint is one of *fp."""
    if not fp:
      raise ValueError("must specify some thumbprints")
    cmd = (' ||\n    '.join([('getprop("ro.build.thumbprint") == "%s"') % i
                             for i in fp]) +
           ' ||\n    abort("E%d: Package expects build thumbprint of %s; this '
           'device has " + getprop("ro.build.thumbprint") + ".");') % (
               common.ErrorCode.THUMBPRINT_MISMATCH, " or ".join(fp))
    self.script.append(cmd)

  def AssertOlderBuild(self, timestamp, timestamp_text):
    """Assert that the build on the device is older (or the same as)
    the given timestamp."""
    self.script.append(
        ('(!less_than_int(%s, getprop("ro.build.date.utc"))) || '
         'abort("E%d: Can\'t install this package (%s) over newer '
         'build (" + getprop("ro.build.date") + ").");') % (timestamp,
             common.ErrorCode.OLDER_BUILD, timestamp_text))

  def AssertDevice(self, device):
    """Assert that the device identifier is the given string."""
    cmd = ('assert(' +
           ' || '.join(['getprop("ro.product.device") == "%s" || getprop("ro.build.product") == "%s"'
                         % (i, i) for i in device.split(",")]) +
           ' || abort("E%d: This package is for device: %s; ' +
           'this device is " + getprop("ro.product.device") + ".");' +
           ');') % (common.ErrorCode.DEVICE_MISMATCH, device)
    self.script.append(cmd)

  def AssertSomeBootloader(self, *bootloaders):
    """Assert that the bootloader version is one of *bootloaders."""
    cmd = ("assert(" +
           " || ".join(['getprop("ro.bootloader") == "%s"' % (b,)
                         for b in bootloaders]) +
           ' || abort("This package supports bootloader(s): ' +
           ", ".join(["%s" % (b,) for b in bootloaders]) +
           '; this device has bootloader " + getprop("ro.bootloader") + ".");' +
           ");")
    self.script.append(self.WordWrap(cmd))

  def AssertSomeBaseband(self, *basebands):
    """Assert that the baseband version is one of *basebands."""
    cmd = ("assert(" +
           " || ".join(['getprop("ro.baseband") == "%s"' % (b,)
                         for b in basebands]) +
           ' || abort("This package supports baseband(s): ' +
           ", ".join(["%s" % (b,) for b in basebands]) +
           '; this device has baseband " + getprop("ro.baseband") + ".");' +
           ");")
    self.script.append(self.WordWrap(cmd))

  def RunBackup(self, command):
    self.script.append(('run_program("/tmp/install/bin/backuptool.sh", "%s");' % command))

  def ValidateSignatures(self, command):
    self.script.append('package_extract_file("META-INF/org/lineageos/releasekey", "/tmp/releasekey");')
    # Exit code 124 == abort. run_program returns raw, so left-shift 8bit
    self.script.append('run_program("/tmp/install/bin/otasigcheck.sh") != "31744" || abort("Can\'t install this package on top of incompatible data. Please try another package or run a factory reset");')

  def FlashMagisk(self):
    self.script.append('package_extract_dir("magisk", "/tmp/magisk");')
    self.script.append('run_program("/sbin/busybox", "unzip", "/tmp/magisk/magisk.zip", "META-INF/com/google/android/*", "-d", "/tmp/magisk");')
    self.script.append('run_program("/sbin/sh", "/tmp/magisk/META-INF/com/google/android/update-binary", "dummy", "1", "/tmp/magisk/magisk.zip");')

  def ShowProgress(self, frac, dur):
    """Update the progress bar, advancing it over 'frac' over the next
    'dur' seconds.  'dur' may be zero to advance it via SetProgress
    commands instead of by time."""
    self.script.append("show_progress(%f, %d);" % (frac, int(dur)))

  def SetProgress(self, frac):
    """Set the position of the progress bar within the chunk defined
    by the most recent ShowProgress call.  'frac' should be in
    [0,1]."""
    self.script.append("set_progress(%f);" % (frac,))

  def PatchCheck(self, filename, *sha1):
    """Check that the given file (or MTD reference) has one of the
    given *sha1 hashes, checking the version saved in cache if the
    file does not match."""
    self.script.append(
        'apply_patch_check("%s"' % (filename,) +
        "".join([', "%s"' % (i,) for i in sha1]) +
        ') || abort("E%d: \\"%s\\" has unexpected contents.");' % (
            common.ErrorCode.BAD_PATCH_FILE, filename))

  def Verify(self, filename):
    """Check that the given file (or MTD reference) has one of the
    given hashes (encoded in the filename)."""
    self.script.append(
        'apply_patch_check("{filename}") && '
        'ui_print("    Verified.") || '
        'ui_print("\\"{filename}\\" has unexpected contents.");'.format(
            filename=filename))

  def FileCheck(self, filename, *sha1):
    """Check that the given file (or MTD reference) has one of the
    given *sha1 hashes."""
    self.script.append('assert(sha1_check(read_file("%s")' % (filename,) +
                       "".join([', "%s"' % (i,) for i in sha1]) +
                       '));')

  def CacheFreeSpaceCheck(self, amount):
    """Check that there's at least 'amount' space that can be made
    available on /cache."""
    self._required_cache = max(self._required_cache, amount)
    self.script.append(('apply_patch_space(%d) || abort("E%d: Not enough free '
                        'space on /cache to apply patches.");') % (
                            amount,
                            common.ErrorCode.INSUFFICIENT_CACHE_SPACE))

  def Mount(self, mount_point, mount_options_by_format=""):
    """Mount the partition with the given mount_point.
      mount_options_by_format:
      [fs_type=option[,option]...[|fs_type=option[,option]...]...]
      where option is optname[=optvalue]
      E.g. ext4=barrier=1,nodelalloc,errors=panic|f2fs=errors=recover
    """
    fstab = self.fstab
    if fstab:
      p = fstab[mount_point]
      mount_dict = {}
      if mount_options_by_format is not None:
        for option in mount_options_by_format.split("|"):
          if "=" in option:
            key, value = option.split("=", 1)
            mount_dict[key] = value
      mount_flags = mount_dict.get(p.fs_type, "")
      if p.context is not None:
        mount_flags = p.context + ("," + mount_flags if mount_flags else "")
      self.script.append('mount("%s", "%s", "%s", "%s", "%s");' % (
          p.fs_type, common.PARTITION_TYPES[p.fs_type], p.device,
          p.mount_point, mount_flags))
      self.mounts.add(p.mount_point)

  def Unmount(self, mount_point):
    """Unmount the partition with the given mount_point."""
    if mount_point in self.mounts:
      self.mounts.remove(mount_point)
      self.script.append('unmount("%s");' % (mount_point,))

  def UnpackPackageDir(self, src, dst):
    """Unpack a given directory from the OTA package into the given
    destination directory."""
    self.script.append('package_extract_dir("%s", "%s");' % (src, dst))

  def Comment(self, comment):
    """Write a comment into the update script."""
    self.script.append("")
    for i in comment.split("\n"):
      self.script.append("# " + i)
    self.script.append("")

  def Print(self, message):
    """Log a message to the screen (if the logs are visible)."""
    self.script.append('ui_print("%s");' % (message,))

  def TunePartition(self, partition, *options):
    fstab = self.fstab
    if fstab:
      p = fstab[partition]
      if p.fs_type not in ("ext2", "ext3", "ext4"):
        raise ValueError("Partition %s cannot be tuned\n" % (partition,))
    self.script.append(
        'tune2fs(' + "".join(['"%s", ' % (i,) for i in options]) +
        '"%s") || abort("E%d: Failed to tune partition %s");' % (
            p.device, common.ErrorCode.TUNE_PARTITION_FAILURE, partition))

  def FormatPartition(self, partition):
    """Format the given partition, specified by its mount point (eg,
    "/system")."""

    fstab = self.fstab
    if fstab:
      p = fstab[partition]
      self.script.append('format("%s", "%s", "%s", "%s", "%s");' %
                         (p.fs_type, common.PARTITION_TYPES[p.fs_type],
                          p.device, p.length, p.mount_point))

  def WipeBlockDevice(self, partition):
    if partition not in ("/system", "/vendor"):
      raise ValueError(("WipeBlockDevice doesn't work on %s\n") % (partition,))
    fstab = self.fstab
    size = self.info.get(partition.lstrip("/") + "_size", None)
    device = fstab[partition].device

    self.script.append('wipe_block_device("%s", %s);' % (device, size))

  def DeleteFiles(self, file_list):
    """Delete all files in file_list."""
    if not file_list:
      return
    cmd = "delete(" + ",\0".join(['"%s"' % (i,) for i in file_list]) + ");"
    self.script.append(self.WordWrap(cmd))

  def DeleteFilesIfNotMatching(self, file_list):
    """Delete the file in file_list if not matching the checksum."""
    if not file_list:
      return
    for name, sha1 in file_list:
      cmd = ('sha1_check(read_file("{name}"), "{sha1}") || '
             'delete("{name}");'.format(name=name, sha1=sha1))
      self.script.append(self.WordWrap(cmd))

  def RenameFile(self, srcfile, tgtfile):
    """Moves a file from one location to another."""
    if self.info.get("update_rename_support", False):
      self.script.append('rename("%s", "%s");' % (srcfile, tgtfile))
    else:
      raise ValueError("Rename not supported by update binary")

  def SkipNextActionIfTargetExists(self, tgtfile, tgtsha1):
    """Prepend an action with an apply_patch_check in order to
       skip the action if the file exists.  Used when a patch
       is later renamed."""
    cmd = ('sha1_check(read_file("%s"), %s) ||' % (tgtfile, tgtsha1))
    self.script.append(self.WordWrap(cmd))

  def ApplyPatch(self, srcfile, tgtfile, tgtsize, tgtsha1, *patchpairs):
    """Apply binary patches (in *patchpairs) to the given srcfile to
    produce tgtfile (which may be "-" to indicate overwriting the
    source file."""
    if len(patchpairs) % 2 != 0 or len(patchpairs) == 0:
      raise ValueError("bad patches given to ApplyPatch")
    cmd = ['apply_patch("%s",\0"%s",\0%s,\0%d'
           % (srcfile, tgtfile, tgtsha1, tgtsize)]
    for i in range(0, len(patchpairs), 2):
      cmd.append(',\0%s,\0package_extract_file("%s")' % patchpairs[i:i+2])
    cmd.append(') ||\n    abort("E%d: Failed to apply patch to %s");' % (
        common.ErrorCode.APPLY_PATCH_FAILURE, srcfile))
    cmd = "".join(cmd)
    self.script.append(self.WordWrap(cmd))

  def WriteRawImage(self, mount_point, fn, mapfn=None):
    """Write the given package file into the partition for the given
    mount point."""

    fstab = self.fstab
    if fstab:
      p = fstab[mount_point]
      partition_type = common.PARTITION_TYPES[p.fs_type]
      args = {'device': p.device, 'fn': fn}
      if partition_type == "MTD":
        self.script.append(
            'write_raw_image(package_extract_file("%(fn)s"), "%(device)s");'
            % args)
      elif partition_type == "OSIP":
        self.script.append(
            'write_osip_image(package_extract_file("%(fn)s"), "%(device)s");'
            % args)
      elif partition_type == "EMMC":
        if mapfn:
          args["map"] = mapfn
          self.script.append(
              'package_extract_file("%(fn)s", "%(device)s", "%(map)s");' % args)
        else:
          self.script.append(
              'package_extract_file("%(fn)s", "%(device)s");' % args)
      else:
        raise ValueError(
            "don't know how to write \"%s\" partitions" % p.fs_type)

  def SetPermissions(self, fn, uid, gid, mode, selabel, capabilities):
    """Set file ownership and permissions."""
    if not self.info.get("use_set_metadata", False):
      self.script.append('set_perm(%d, %d, 0%o, "%s");' % (uid, gid, mode, fn))
    else:
      cmd = 'set_metadata("%s", "uid", %d, "gid", %d, "mode", 0%o' \
          % (fn, uid, gid, mode)
      if capabilities is not None:
        cmd += ', "capabilities", %s' % ( capabilities )
      if selabel is not None:
        cmd += ', "selabel", "%s"' % selabel
      cmd += ');'
      self.script.append(cmd)

  def SetPermissionsRecursive(self, fn, uid, gid, dmode, fmode, selabel,
                              capabilities):
    """Recursively set path ownership and permissions."""
    if not self.info.get("use_set_metadata", False):
      self.script.append('set_perm_recursive(%d, %d, 0%o, 0%o, "%s");'
                         % (uid, gid, dmode, fmode, fn))
    else:
      cmd = 'set_metadata_recursive("%s", "uid", %d, "gid", %d, ' \
          '"dmode", 0%o, "fmode", 0%o' \
          % (fn, uid, gid, dmode, fmode)
      if capabilities is not None:
        cmd += ', "capabilities", "%s"' % ( capabilities )
      if selabel is not None:
        cmd += ', "selabel", "%s"' % selabel
      cmd += ');'
      self.script.append(cmd)

  def MakeSymlinks(self, symlink_list):
    """Create symlinks, given a list of (dest, link) pairs."""
    by_dest = {}
    for d, l in symlink_list:
      by_dest.setdefault(d, []).append(l)

    for dest, links in sorted(by_dest.iteritems()):
      cmd = ('symlink("%s", ' % (dest,) +
             ",\0".join(['"' + i + '"' for i in sorted(links)]) + ");")
      self.script.append(self.WordWrap(cmd))

  def AppendExtra(self, extra):
    """Append text verbatim to the output script."""
    self.script.append(extra)

  def Unmount(self, mount_point):
    self.script.append('unmount("%s");' % mount_point)
    self.mounts.remove(mount_point)

  def UnmountAll(self):
    for p in sorted(self.mounts):
      self.script.append('unmount("%s");' % (p,))
    self.mounts = set()

  def AddToZip(self, input_zip, output_zip, input_path=None):
    """Write the accumulated script to the output_zip file.  input_zip
    is used as the source for the 'updater' binary needed to run
    script.  If input_path is not None, it will be used as a local
    path for the binary instead of input_zip."""

    self.UnmountAll()

    common.ZipWriteStr(output_zip, "META-INF/com/google/android/updater-script",
                       "\n".join(self.script) + "\n")

    if input_path is None:
      data = input_zip.read("OTA/bin/updater")
    else:
      data = open(input_path, "rb").read()
    common.ZipWriteStr(output_zip, "META-INF/com/google/android/update-binary",
                       data, perms=0o755)
