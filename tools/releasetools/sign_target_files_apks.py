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
Signs all the APK files in a target-files zipfile, producing a new
target-files zip.

Usage:  sign_target_files_apks [flags] input_target_files output_target_files

  -e  (--extra_apks)  <name,name,...=key>
      Add extra APK name/key pairs as though they appeared in
      apkcerts.txt (so mappings specified by -k and -d are applied).
      Keys specified in -e override any value for that app contained
      in the apkcerts.txt file.  Option may be repeated to give
      multiple extra packages.

  -k  (--key_mapping)  <src_key=dest_key>
      Add a mapping from the key name as specified in apkcerts.txt (the
      src_key) to the real key you wish to sign the package with
      (dest_key).  Option may be repeated to give multiple key
      mappings.

  -d  (--default_key_mappings)  <dir>
      Set up the following key mappings:

        $devkey/devkey    ==>  $dir/releasekey
        $devkey/testkey   ==>  $dir/releasekey
        $devkey/media     ==>  $dir/media
        $devkey/shared    ==>  $dir/shared
        $devkey/platform  ==>  $dir/platform

      where $devkey is the directory part of the value of
      default_system_dev_certificate from the input target-files's
      META/misc_info.txt.  (Defaulting to "build/target/product/security"
      if the value is not present in misc_info.

      -d and -k options are added to the set of mappings in the order
      in which they appear on the command line.

  -o  (--replace_ota_keys)
      Replace the certificate (public key) used by OTA package verification
      with the ones specified in the input target_files zip (in the
      META/otakeys.txt file). Key remapping (-k and -d) is performed on the
      keys. For A/B devices, the payload verification key will be replaced
      as well. If there're multiple OTA keys, only the first one will be used
      for payload verification.

  -t  (--tag_changes)  <+tag>,<-tag>,...
      Comma-separated list of changes to make to the set of tags (in
      the last component of the build fingerprint).  Prefix each with
      '+' or '-' to indicate whether that tag should be added or
      removed.  Changes are processed in the order they appear.
      Default value is "-test-keys,-dev-keys,+release-keys".

  --replace_verity_private_key <key>
      Replace the private key used for verity signing. It expects a filename
      WITHOUT the extension (e.g. verity_key).

  --replace_verity_public_key <key>
      Replace the certificate (public key) used for verity verification. The
      key file replaces the one at BOOT/RAMDISK/verity_key (or ROOT/verity_key
      for devices using system_root_image). It expects the key filename WITH
      the extension (e.g. verity_key.pub).

  --replace_verity_keyid <path_to_X509_PEM_cert_file>
      Replace the veritykeyid in BOOT/cmdline of input_target_file_zip
      with keyid of the cert pointed by <path_to_X509_PEM_cert_file>.

  --avb_{boot,system,vendor,dtbo,vbmeta}_algorithm <algorithm>
  --avb_{boot,system,vendor,dtbo,vbmeta}_key <key>
      Use the specified algorithm (e.g. SHA256_RSA4096) and the key to AVB-sign
      the specified image. Otherwise it uses the existing values in info dict.

  --avb_{boot,system,vendor,dtbo,vbmeta}_extra_args <args>
      Specify any additional args that are needed to AVB-sign the image
      (e.g. "--signing_helper /path/to/helper"). The args will be appended to
      the existing ones in info dict.
"""

import sys

if sys.hexversion < 0x02070000:
  print >> sys.stderr, "Python 2.7 or newer is required."
  sys.exit(1)

import base64
import cStringIO
import copy
import errno
import gzip
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

import add_img_to_target_files
import common

OPTIONS = common.OPTIONS

OPTIONS.extra_apks = {}
OPTIONS.key_map = {}
OPTIONS.rebuild_recovery = False
OPTIONS.replace_ota_keys = False
OPTIONS.replace_verity_public_key = False
OPTIONS.replace_verity_private_key = False
OPTIONS.replace_verity_keyid = False
OPTIONS.tag_changes = ("-test-keys", "-dev-keys", "+release-keys")
OPTIONS.avb_keys = {}
OPTIONS.avb_algorithms = {}
OPTIONS.avb_extra_args = {}

def GetApkCerts(certmap):
  # apply the key remapping to the contents of the file
  for apk, cert in certmap.iteritems():
    certmap[apk] = OPTIONS.key_map.get(cert, cert)

  # apply all the -e options, overriding anything in the file
  for apk, cert in OPTIONS.extra_apks.iteritems():
    if not cert:
      cert = "PRESIGNED"
    certmap[apk] = OPTIONS.key_map.get(cert, cert)

  return certmap


def CheckAllApksSigned(input_tf_zip, apk_key_map, compressed_extension):
  """Check that all the APKs we want to sign have keys specified, and
  error out if they don't."""
  unknown_apks = []
  compressed_apk_extension = None
  if compressed_extension:
    compressed_apk_extension = ".apk" + compressed_extension
  for info in input_tf_zip.infolist():
    if (info.filename.endswith(".apk") or
        (compressed_apk_extension and info.filename.endswith(compressed_apk_extension))):
      name = os.path.basename(info.filename)
      if compressed_apk_extension and name.endswith(compressed_apk_extension):
        name = name[:-len(compressed_extension)]
      if name not in apk_key_map:
        unknown_apks.append(name)
  if unknown_apks:
    print "ERROR: no key specified for:\n\n ",
    print "\n  ".join(unknown_apks)
    print "\nUse '-e <apkname>=' to specify a key (which may be an"
    print "empty string to not sign this apk)."
    sys.exit(1)


def SignApk(data, keyname, pw, platform_api_level, codename_to_api_level_map,
            is_compressed):
  unsigned = tempfile.NamedTemporaryFile()
  unsigned.write(data)
  unsigned.flush()

  if is_compressed:
    uncompressed = tempfile.NamedTemporaryFile()
    with gzip.open(unsigned.name, "rb") as in_file, open(uncompressed.name, "wb") as out_file:
      shutil.copyfileobj(in_file, out_file)

    # Finally, close the "unsigned" file (which is gzip compressed), and then
    # replace it with the uncompressed version.
    #
    # TODO(narayan): All this nastiness can be avoided if python 3.2 is in use,
    # we could just gzip / gunzip in-memory buffers instead.
    unsigned.close()
    unsigned = uncompressed

  signed = tempfile.NamedTemporaryFile()

  # For pre-N builds, don't upgrade to SHA-256 JAR signatures based on the APK's
  # minSdkVersion to avoid increasing incremental OTA update sizes. If an APK
  # didn't change, we don't want its signature to change due to the switch
  # from SHA-1 to SHA-256.
  # By default, APK signer chooses SHA-256 signatures if the APK's minSdkVersion
  # is 18 or higher. For pre-N builds we disable this mechanism by pretending
  # that the APK's minSdkVersion is 1.
  # For N+ builds, we let APK signer rely on the APK's minSdkVersion to
  # determine whether to use SHA-256.
  min_api_level = None
  if platform_api_level > 23:
    # Let APK signer choose whether to use SHA-1 or SHA-256, based on the APK's
    # minSdkVersion attribute
    min_api_level = None
  else:
    # Force APK signer to use SHA-1
    min_api_level = 1

  common.SignFile(unsigned.name, signed.name, keyname, pw,
      min_api_level=min_api_level,
      codename_to_api_level_map=codename_to_api_level_map)

  data = None;
  if is_compressed:
    # Recompress the file after it has been signed.
    compressed = tempfile.NamedTemporaryFile()
    with open(signed.name, "rb") as in_file, gzip.open(compressed.name, "wb") as out_file:
      shutil.copyfileobj(in_file, out_file)

    data = compressed.read()
    compressed.close()
  else:
    data = signed.read()

  unsigned.close()
  signed.close()

  return data


def ProcessTargetFiles(input_tf_zip, output_tf_zip, misc_info,
                       apk_key_map, key_passwords, platform_api_level,
                       codename_to_api_level_map,
                       compressed_extension):

  compressed_apk_extension = None
  if compressed_extension:
    compressed_apk_extension = ".apk" + compressed_extension

  maxsize = max([len(os.path.basename(i.filename))
                 for i in input_tf_zip.infolist()
                 if i.filename.endswith('.apk') or
                 (compressed_apk_extension and i.filename.endswith(compressed_apk_extension))])
  system_root_image = misc_info.get("system_root_image") == "true"

  for info in input_tf_zip.infolist():
    if info.filename.startswith("IMAGES/"):
      continue

    data = input_tf_zip.read(info.filename)
    out_info = copy.copy(info)

    # Sign APKs.
    if (info.filename.endswith(".apk") or
        (compressed_apk_extension and info.filename.endswith(compressed_apk_extension))):
      is_compressed = compressed_extension and info.filename.endswith(compressed_apk_extension)
      name = os.path.basename(info.filename)
      if is_compressed:
        name = name[:-len(compressed_extension)]

      key = apk_key_map[name]
      if key not in common.SPECIAL_CERT_STRINGS:
        print "    signing: %-*s (%s)" % (maxsize, name, key)
        signed_data = SignApk(data, key, key_passwords[key], platform_api_level,
            codename_to_api_level_map, is_compressed)
        common.ZipWriteStr(output_tf_zip, out_info, signed_data)
      else:
        # an APK we're not supposed to sign.
        print "NOT signing: %s" % (name,)
        common.ZipWriteStr(output_tf_zip, out_info, data)

    # System properties.
    elif info.filename in ("SYSTEM/build.prop",
                           "VENDOR/build.prop",
                           "SYSTEM/etc/prop.default",
                           "BOOT/RAMDISK/prop.default",
                           "BOOT/RAMDISK/default.prop",  # legacy
                           "ROOT/default.prop",  # legacy
                           "RECOVERY/RAMDISK/prop.default",
                           "RECOVERY/RAMDISK/default.prop"):  # legacy
      print "rewriting %s:" % (info.filename,)
      if stat.S_ISLNK(info.external_attr >> 16):
        new_data = data
      else:
        new_data = RewriteProps(data, misc_info)
      common.ZipWriteStr(output_tf_zip, out_info, new_data)

    elif info.filename.endswith("mac_permissions.xml"):
      print "rewriting %s with new keys." % (info.filename,)
      new_data = ReplaceCerts(data)
      common.ZipWriteStr(output_tf_zip, out_info, new_data)
    elif info.filename.startswith("SYSTEM/etc/permissions/"):
      print("rewriting %s with new keys." % info.filename)
      new_data = ReplaceCerts(data)
      common.ZipWriteStr(output_tf_zip, out_info, new_data)

    # Ask add_img_to_target_files to rebuild the recovery patch if needed.
    elif info.filename in ("SYSTEM/recovery-from-boot.p",
                           "SYSTEM/etc/recovery.img",
                           "SYSTEM/bin/install-recovery.sh"):
      OPTIONS.rebuild_recovery = True

    # Don't copy OTA keys if we're replacing them.
    elif (OPTIONS.replace_ota_keys and
          info.filename in (
              "BOOT/RAMDISK/res/keys",
              "BOOT/RAMDISK/etc/update_engine/update-payload-key.pub.pem",
              "RECOVERY/RAMDISK/res/keys",
              "SYSTEM/etc/security/otacerts.zip",
              "SYSTEM/etc/update_engine/update-payload-key.pub.pem")):
      pass

    # Skip META/misc_info.txt since we will write back the new values later.
    elif info.filename == "META/misc_info.txt":
      pass

    # Skip verity public key if we will replace it.
    elif (OPTIONS.replace_verity_public_key and
          info.filename in ("BOOT/RAMDISK/verity_key",
                            "ROOT/verity_key")):
      pass

    # Skip verity keyid (for system_root_image use) if we will replace it.
    elif (OPTIONS.replace_verity_keyid and
          info.filename == "BOOT/cmdline"):
      pass

    # Skip the care_map as we will regenerate the system/vendor images.
    elif info.filename == "META/care_map.txt":
      pass

    # A non-APK file; copy it verbatim.
    else:
      common.ZipWriteStr(output_tf_zip, out_info, data)

  if OPTIONS.replace_ota_keys:
    ReplaceOtaKeys(input_tf_zip, output_tf_zip, misc_info)

  # Replace the keyid string in misc_info dict.
  if OPTIONS.replace_verity_private_key:
    ReplaceVerityPrivateKey(misc_info, OPTIONS.replace_verity_private_key[1])

  if OPTIONS.replace_verity_public_key:
    if system_root_image:
      dest = "ROOT/verity_key"
    else:
      dest = "BOOT/RAMDISK/verity_key"
    # We are replacing the one in boot image only, since the one under
    # recovery won't ever be needed.
    ReplaceVerityPublicKey(
        output_tf_zip, dest, OPTIONS.replace_verity_public_key[1])

  # Replace the keyid string in BOOT/cmdline.
  if OPTIONS.replace_verity_keyid:
    ReplaceVerityKeyId(input_tf_zip, output_tf_zip,
                       OPTIONS.replace_verity_keyid[1])

  # Replace the AVB signing keys, if any.
  ReplaceAvbSigningKeys(misc_info)

  # Write back misc_info with the latest values.
  ReplaceMiscInfoTxt(input_tf_zip, output_tf_zip, misc_info)


def ReplaceCerts(data):
  """Given a string of data, replace all occurences of a set
  of X509 certs with a newer set of X509 certs and return
  the updated data string."""
  for old, new in OPTIONS.key_map.iteritems():
    try:
      if OPTIONS.verbose:
        print "    Replacing %s.x509.pem with %s.x509.pem" % (old, new)
      f = open(old + ".x509.pem")
      old_cert16 = base64.b16encode(common.ParseCertificate(f.read())).lower()
      f.close()
      f = open(new + ".x509.pem")
      new_cert16 = base64.b16encode(common.ParseCertificate(f.read())).lower()
      f.close()
      # Only match entire certs.
      pattern = "\\b"+old_cert16+"\\b"
      (data, num) = re.subn(pattern, new_cert16, data, flags=re.IGNORECASE)
      if OPTIONS.verbose:
        print "    Replaced %d occurence(s) of %s.x509.pem with " \
            "%s.x509.pem" % (num, old, new)
    except IOError as e:
      if e.errno == errno.ENOENT and not OPTIONS.verbose:
        continue

      print "    Error accessing %s. %s. Skip replacing %s.x509.pem " \
          "with %s.x509.pem." % (e.filename, e.strerror, old, new)

  return data


def EditTags(tags):
  """Given a string containing comma-separated tags, apply the edits
  specified in OPTIONS.tag_changes and return the updated string."""
  tags = set(tags.split(","))
  for ch in OPTIONS.tag_changes:
    if ch[0] == "-":
      tags.discard(ch[1:])
    elif ch[0] == "+":
      tags.add(ch[1:])
  return ",".join(sorted(tags))


def RewriteProps(data, misc_info):
  output = []
  for line in data.split("\n"):
    line = line.strip()
    original_line = line
    if line and line[0] != '#' and "=" in line:
      key, value = line.split("=", 1)
      if (key in ("ro.build.fingerprint", "ro.vendor.build.fingerprint")
          and misc_info.get("oem_fingerprint_properties") is None):
        pieces = value.split("/")
        pieces[-1] = EditTags(pieces[-1])
        value = "/".join(pieces)
      elif (key in ("ro.build.thumbprint", "ro.vendor.build.thumbprint")
            and misc_info.get("oem_fingerprint_properties") is not None):
        pieces = value.split("/")
        pieces[-1] = EditTags(pieces[-1])
        value = "/".join(pieces)
      elif key == "ro.bootimage.build.fingerprint":
        pieces = value.split("/")
        pieces[-1] = EditTags(pieces[-1])
        value = "/".join(pieces)
      elif key == "ro.build.description":
        pieces = value.split(" ")
        assert len(pieces) == 5
        pieces[-1] = EditTags(pieces[-1])
        value = " ".join(pieces)
      elif key == "ro.build.tags":
        value = EditTags(value)
      elif key == "ro.build.display.id":
        # change, eg, "JWR66N dev-keys" to "JWR66N"
        value = value.split()
        if len(value) > 1 and value[-1].endswith("-keys"):
          value.pop()
        value = " ".join(value)
      line = key + "=" + value
    if line != original_line:
      print "  replace: ", original_line
      print "     with: ", line
    output.append(line)
  return "\n".join(output) + "\n"


def ReplaceOtaKeys(input_tf_zip, output_tf_zip, misc_info):
  try:
    keylist = input_tf_zip.read("META/otakeys.txt").split()
  except KeyError:
    raise common.ExternalError("can't read META/otakeys.txt from input")

  extra_recovery_keys = misc_info.get("extra_recovery_keys", None)
  if extra_recovery_keys:
    extra_recovery_keys = [OPTIONS.key_map.get(k, k) + ".x509.pem"
                           for k in extra_recovery_keys.split()]
    if extra_recovery_keys:
      print "extra recovery-only key(s): " + ", ".join(extra_recovery_keys)
  else:
    extra_recovery_keys = []

  mapped_keys = []
  for k in keylist:
    m = re.match(r"^(.*)\.x509\.pem$", k)
    if not m:
      raise common.ExternalError(
          "can't parse \"%s\" from META/otakeys.txt" % (k,))
    k = m.group(1)
    mapped_keys.append(OPTIONS.key_map.get(k, k) + ".x509.pem")

  if mapped_keys:
    print "using:\n   ", "\n   ".join(mapped_keys)
    print "for OTA package verification"
  else:
    devkey = misc_info.get("default_system_dev_certificate",
                           "build/target/product/security/testkey")
    mapped_keys.append(
        OPTIONS.key_map.get(devkey, devkey) + ".x509.pem")
    print("META/otakeys.txt has no keys; using %s for OTA package"
          " verification." % (mapped_keys[0],))

  # recovery uses a version of the key that has been slightly
  # predigested (by DumpPublicKey.java) and put in res/keys.
  # extra_recovery_keys are used only in recovery.
  cmd = ([OPTIONS.java_path] + OPTIONS.java_args +
         ["-jar",
          os.path.join(OPTIONS.search_path, "framework", "dumpkey.jar")] +
         mapped_keys + extra_recovery_keys)
  p = common.Run(cmd, stdout=subprocess.PIPE)
  new_recovery_keys, _ = p.communicate()
  if p.returncode != 0:
    raise common.ExternalError("failed to run dumpkeys")

  # system_root_image puts the recovery keys at BOOT/RAMDISK.
  if misc_info.get("system_root_image") == "true":
    recovery_keys_location = "BOOT/RAMDISK/res/keys"
  else:
    recovery_keys_location = "RECOVERY/RAMDISK/res/keys"
  common.ZipWriteStr(output_tf_zip, recovery_keys_location, new_recovery_keys)

  # SystemUpdateActivity uses the x509.pem version of the keys, but
  # put into a zipfile system/etc/security/otacerts.zip.
  # We DO NOT include the extra_recovery_keys (if any) here.

  temp_file = cStringIO.StringIO()
  certs_zip = zipfile.ZipFile(temp_file, "w")
  for k in mapped_keys:
    common.ZipWrite(certs_zip, k)
  common.ZipClose(certs_zip)
  common.ZipWriteStr(output_tf_zip, "SYSTEM/etc/security/otacerts.zip",
                     temp_file.getvalue())

  # For A/B devices, update the payload verification key.
  if misc_info.get("ab_update") == "true":
    # Unlike otacerts.zip that may contain multiple keys, we can only specify
    # ONE payload verification key.
    if len(mapped_keys) > 1:
      print("\n  WARNING: Found more than one OTA keys; Using the first one"
            " as payload verification key.\n\n")

    print "Using %s for payload verification." % (mapped_keys[0],)
    cmd = common.Run(
        ["openssl", "x509", "-pubkey", "-noout", "-in", mapped_keys[0]],
        stdout=subprocess.PIPE)
    pubkey, _ = cmd.communicate()
    common.ZipWriteStr(
        output_tf_zip,
        "SYSTEM/etc/update_engine/update-payload-key.pub.pem",
        pubkey)
    common.ZipWriteStr(
        output_tf_zip,
        "BOOT/RAMDISK/etc/update_engine/update-payload-key.pub.pem",
        pubkey)

  return new_recovery_keys


def ReplaceVerityPublicKey(targetfile_zip, filename, key_path):
  print "Replacing verity public key with %s" % (key_path,)
  common.ZipWrite(targetfile_zip, key_path, arcname=filename)


def ReplaceVerityPrivateKey(misc_info, key_path):
  print "Replacing verity private key with %s" % (key_path,)
  misc_info["verity_key"] = key_path


def ReplaceVerityKeyId(targetfile_input_zip, targetfile_output_zip, keypath):
  in_cmdline = targetfile_input_zip.read("BOOT/cmdline")
  # copy in_cmdline to output_zip if veritykeyid is not present in in_cmdline
  if "veritykeyid" not in in_cmdline:
    common.ZipWriteStr(targetfile_output_zip, "BOOT/cmdline", in_cmdline)
    return in_cmdline
  out_cmdline = []
  for param in in_cmdline.split():
    if "veritykeyid" in param:
      # extract keyid using openssl command
      p = common.Run(
          ["openssl", "x509", "-in", keypath, "-text"],
          stdout=subprocess.PIPE)
      keyid, stderr = p.communicate()
      keyid = re.search(
          r'keyid:([0-9a-fA-F:]*)', keyid).group(1).replace(':', '').lower()
      print "Replacing verity keyid with %s error=%s" % (keyid, stderr)
      out_cmdline.append("veritykeyid=id:%s" % (keyid,))
    else:
      out_cmdline.append(param)

  out_cmdline = ' '.join(out_cmdline)
  out_cmdline = out_cmdline.strip()
  print "out_cmdline %s" % (out_cmdline)
  common.ZipWriteStr(targetfile_output_zip, "BOOT/cmdline", out_cmdline)


def ReplaceMiscInfoTxt(input_zip, output_zip, misc_info):
  """Replaces META/misc_info.txt.

  Only writes back the ones in the original META/misc_info.txt. Because the
  current in-memory dict contains additional items computed at runtime.
  """
  misc_info_old = common.LoadDictionaryFromLines(
      input_zip.read('META/misc_info.txt').split('\n'))
  items = []
  for key in sorted(misc_info):
    if key in misc_info_old:
      items.append('%s=%s' % (key, misc_info[key]))
  common.ZipWriteStr(output_zip, "META/misc_info.txt", '\n'.join(items))


def ReplaceAvbSigningKeys(misc_info):
  """Replaces the AVB signing keys."""

  AVB_FOOTER_ARGS_BY_PARTITION = {
    'boot' : 'avb_boot_add_hash_footer_args',
    'dtbo' : 'avb_dtbo_add_hash_footer_args',
    'system' : 'avb_system_add_hashtree_footer_args',
    'vendor' : 'avb_vendor_add_hashtree_footer_args',
    'vbmeta' : 'avb_vbmeta_args',
  }

  def ReplaceAvbPartitionSigningKey(partition):
    key = OPTIONS.avb_keys.get(partition)
    if not key:
      return

    algorithm = OPTIONS.avb_algorithms.get(partition)
    assert algorithm, 'Missing AVB signing algorithm for %s' % (partition,)

    print 'Replacing AVB signing key for %s with "%s" (%s)' % (
        partition, key, algorithm)
    misc_info['avb_' + partition + '_algorithm'] = algorithm
    misc_info['avb_' + partition + '_key_path'] = key

    extra_args = OPTIONS.avb_extra_args.get(partition)
    if extra_args:
      print 'Setting extra AVB signing args for %s to "%s"' % (
          partition, extra_args)
      args_key = AVB_FOOTER_ARGS_BY_PARTITION[partition]
      misc_info[args_key] = (misc_info.get(args_key, '') + ' ' + extra_args)

  for partition in AVB_FOOTER_ARGS_BY_PARTITION:
    ReplaceAvbPartitionSigningKey(partition)


def BuildKeyMap(misc_info, key_mapping_options):
  for s, d in key_mapping_options:
    if s is None:   # -d option
      devkey = misc_info.get("default_system_dev_certificate",
                             "build/target/product/security/testkey")
      devkeydir = os.path.dirname(devkey)

      OPTIONS.key_map.update({
          devkeydir + "/testkey":  d + "/releasekey",
          devkeydir + "/devkey":   d + "/releasekey",
          devkeydir + "/media":    d + "/media",
          devkeydir + "/shared":   d + "/shared",
          devkeydir + "/platform": d + "/platform",
          })
    else:
      OPTIONS.key_map[s] = d


def GetApiLevelAndCodename(input_tf_zip):
  data = input_tf_zip.read("SYSTEM/build.prop")
  api_level = None
  codename = None
  for line in data.split("\n"):
    line = line.strip()
    if line and line[0] != '#' and "=" in line:
      key, value = line.split("=", 1)
      key = key.strip()
      if key == "ro.build.version.sdk":
        api_level = int(value.strip())
      elif key == "ro.build.version.codename":
        codename = value.strip()

  if api_level is None:
    raise ValueError("No ro.build.version.sdk in SYSTEM/build.prop")
  if codename is None:
    raise ValueError("No ro.build.version.codename in SYSTEM/build.prop")

  return (api_level, codename)


def GetCodenameToApiLevelMap(input_tf_zip):
  data = input_tf_zip.read("SYSTEM/build.prop")
  api_level = None
  codenames = None
  for line in data.split("\n"):
    line = line.strip()
    if line and line[0] != '#' and "=" in line:
      key, value = line.split("=", 1)
      key = key.strip()
      if key == "ro.build.version.sdk":
        api_level = int(value.strip())
      elif key == "ro.build.version.all_codenames":
        codenames = value.strip().split(",")

  if api_level is None:
    raise ValueError("No ro.build.version.sdk in SYSTEM/build.prop")
  if codenames is None:
    raise ValueError("No ro.build.version.all_codenames in SYSTEM/build.prop")

  result = dict()
  for codename in codenames:
    codename = codename.strip()
    if len(codename) > 0:
      result[codename] = api_level
  return result


def main(argv):

  key_mapping_options = []

  def option_handler(o, a):
    if o in ("-e", "--extra_apks"):
      names, key = a.split("=")
      names = names.split(",")
      for n in names:
        OPTIONS.extra_apks[n] = key
    elif o in ("-d", "--default_key_mappings"):
      key_mapping_options.append((None, a))
    elif o in ("-k", "--key_mapping"):
      key_mapping_options.append(a.split("=", 1))
    elif o in ("-o", "--replace_ota_keys"):
      OPTIONS.replace_ota_keys = True
    elif o in ("-t", "--tag_changes"):
      new = []
      for i in a.split(","):
        i = i.strip()
        if not i or i[0] not in "-+":
          raise ValueError("Bad tag change '%s'" % (i,))
        new.append(i[0] + i[1:].strip())
      OPTIONS.tag_changes = tuple(new)
    elif o == "--replace_verity_public_key":
      OPTIONS.replace_verity_public_key = (True, a)
    elif o == "--replace_verity_private_key":
      OPTIONS.replace_verity_private_key = (True, a)
    elif o == "--replace_verity_keyid":
      OPTIONS.replace_verity_keyid = (True, a)
    elif o == "--avb_vbmeta_key":
      OPTIONS.avb_keys['vbmeta'] = a
    elif o == "--avb_vbmeta_algorithm":
      OPTIONS.avb_algorithms['vbmeta'] = a
    elif o == "--avb_vbmeta_extra_args":
      OPTIONS.avb_extra_args['vbmeta'] = a
    elif o == "--avb_boot_key":
      OPTIONS.avb_keys['boot'] = a
    elif o == "--avb_boot_algorithm":
      OPTIONS.avb_algorithms['boot'] = a
    elif o == "--avb_boot_extra_args":
      OPTIONS.avb_extra_args['boot'] = a
    elif o == "--avb_dtbo_key":
      OPTIONS.avb_keys['dtbo'] = a
    elif o == "--avb_dtbo_algorithm":
      OPTIONS.avb_algorithms['dtbo'] = a
    elif o == "--avb_dtbo_extra_args":
      OPTIONS.avb_extra_args['dtbo'] = a
    elif o == "--avb_system_key":
      OPTIONS.avb_keys['system'] = a
    elif o == "--avb_system_algorithm":
      OPTIONS.avb_algorithms['system'] = a
    elif o == "--avb_system_extra_args":
      OPTIONS.avb_extra_args['system'] = a
    elif o == "--avb_vendor_key":
      OPTIONS.avb_keys['vendor'] = a
    elif o == "--avb_vendor_algorithm":
      OPTIONS.avb_algorithms['vendor'] = a
    elif o == "--avb_vendor_extra_args":
      OPTIONS.avb_extra_args['vendor'] = a
    else:
      return False
    return True

  args = common.ParseOptions(
      argv, __doc__,
      extra_opts="e:d:k:ot:",
      extra_long_opts=[
        "extra_apks=",
        "default_key_mappings=",
        "key_mapping=",
        "replace_ota_keys",
        "tag_changes=",
        "replace_verity_public_key=",
        "replace_verity_private_key=",
        "replace_verity_keyid=",
        "avb_vbmeta_algorithm=",
        "avb_vbmeta_key=",
        "avb_vbmeta_extra_args=",
        "avb_boot_algorithm=",
        "avb_boot_key=",
        "avb_boot_extra_args=",
        "avb_dtbo_algorithm=",
        "avb_dtbo_key=",
        "avb_dtbo_extra_args=",
        "avb_system_algorithm=",
        "avb_system_key=",
        "avb_system_extra_args=",
        "avb_vendor_algorithm=",
        "avb_vendor_key=",
        "avb_vendor_extra_args=",
      ],
      extra_option_handler=option_handler)

  if len(args) != 2:
    common.Usage(__doc__)
    sys.exit(1)

  input_zip = zipfile.ZipFile(args[0], "r")
  output_zip = zipfile.ZipFile(args[1], "w",
                               compression=zipfile.ZIP_DEFLATED,
                               allowZip64=True)

  misc_info = common.LoadInfoDict(input_zip)

  BuildKeyMap(misc_info, key_mapping_options)

  certmap, compressed_extension = common.ReadApkCerts(input_zip)
  apk_key_map = GetApkCerts(certmap)
  CheckAllApksSigned(input_zip, apk_key_map, compressed_extension)

  key_passwords = common.GetKeyPasswords(set(apk_key_map.values()))
  platform_api_level, _ = GetApiLevelAndCodename(input_zip)
  codename_to_api_level_map = GetCodenameToApiLevelMap(input_zip)

  ProcessTargetFiles(input_zip, output_zip, misc_info,
                     apk_key_map, key_passwords,
                     platform_api_level,
                     codename_to_api_level_map,
                     compressed_extension)

  common.ZipClose(input_zip)
  common.ZipClose(output_zip)

  # Skip building userdata.img and cache.img when signing the target files.
  new_args = ["--is_signing"]
  # add_img_to_target_files builds the system image from scratch, so the
  # recovery patch is guaranteed to be regenerated there.
  if OPTIONS.rebuild_recovery:
    new_args.append("--rebuild_recovery")
  new_args.append(args[1])
  add_img_to_target_files.main(new_args)

  print "done."


if __name__ == '__main__':
  try:
    main(sys.argv[1:])
  except common.ExternalError, e:
    print
    print "   ERROR: %s" % (e,)
    print
    sys.exit(1)
  finally:
    common.Cleanup()
