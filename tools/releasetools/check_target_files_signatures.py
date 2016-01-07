#!/usr/bin/env python
#
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

"""
Check the signatures of all APKs in a target_files .zip file.  With
-c, compare the signatures of each package to the ones in a separate
target_files (usually a previously distributed build for the same
device) and flag any changes.

Usage:  check_target_file_signatures [flags] target_files

  -c  (--compare_with)  <other_target_files>
      Look for compatibility problems between the two sets of target
      files (eg., packages whose keys have changed).

  -l  (--local_cert_dirs)  <dir,dir,...>
      Comma-separated list of top-level directories to scan for
      .x509.pem files.  Defaults to "vendor,build".  Where cert files
      can be found that match APK signatures, the filename will be
      printed as the cert name, otherwise a hash of the cert plus its
      subject string will be printed instead.

  -t  (--text)
      Dump the certificate information for both packages in comparison
      mode (this output is normally suppressed).

"""

from __future__ import print_function

import sys

if sys.hexversion < 0x02070000:
  print("Python 2.7 or newer is required.", file=sys.stderr)
  sys.exit(1)

import os
import re
import shutil
import subprocess
import zipfile

import common


def iteritems(obj):
  if hasattr(obj, 'iteritems'):
    return obj.iteritems()
  return obj.items()


# Work around a bug in python's zipfile module that prevents opening
# of zipfiles if any entry has an extra field of between 1 and 3 bytes
# (which is common with zipaligned APKs).  This overrides the
# ZipInfo._decodeExtra() method (which contains the bug) with an empty
# version (since we don't need to decode the extra field anyway).
class MyZipInfo(zipfile.ZipInfo):
  def _decodeExtra(self):
    pass
zipfile.ZipInfo = MyZipInfo

OPTIONS = common.OPTIONS

OPTIONS.text = False
OPTIONS.compare_with = None
OPTIONS.local_cert_dirs = ("vendor", "build")

PROBLEMS = []
PROBLEM_PREFIX = []

def AddProblem(msg):
  PROBLEMS.append(" ".join(PROBLEM_PREFIX) + " " + msg)
def Push(msg):
  PROBLEM_PREFIX.append(msg)
def Pop():
  PROBLEM_PREFIX.pop()


def Banner(msg):
  print("-" * 70)
  print("  ", msg)
  print("-" * 70)


def GetCertSubject(cert):
  p = common.Run(["openssl", "x509", "-inform", "DER", "-text"],
                 stdin=subprocess.PIPE,
                 stdout=subprocess.PIPE)
  out, err = p.communicate(cert)
  if err and not err.strip():
    return "(error reading cert subject)"
  for line in out.split("\n"):
    line = line.strip()
    if line.startswith("Subject:"):
      return line[8:].strip()
  return "(unknown cert subject)"


class CertDB(object):
  def __init__(self):
    self.certs = {}

  def Add(self, cert, name=None):
    if cert in self.certs:
      if name:
        self.certs[cert] = self.certs[cert] + "," + name
    else:
      if name is None:
        name = "unknown cert %s (%s)" % (common.sha1(cert).hexdigest()[:12],
                                         GetCertSubject(cert))
      self.certs[cert] = name

  def Get(self, cert):
    """Return the name for a given cert."""
    return self.certs.get(cert, None)

  def FindLocalCerts(self):
    to_load = []
    for top in OPTIONS.local_cert_dirs:
      for dirpath, _, filenames in os.walk(top):
        certs = [os.path.join(dirpath, i)
                 for i in filenames if i.endswith(".x509.pem")]
        if certs:
          to_load.extend(certs)

    for i in to_load:
      f = open(i)
      cert = common.ParseCertificate(f.read())
      f.close()
      name, _ = os.path.splitext(i)
      name, _ = os.path.splitext(name)
      self.Add(cert, name)

ALL_CERTS = CertDB()


def CertFromPKCS7(data, filename):
  """Read the cert out of a PKCS#7-format file (which is what is
  stored in a signed .apk)."""
  Push(filename + ":")
  try:
    p = common.Run(["openssl", "pkcs7",
                    "-inform", "DER",
                    "-outform", "PEM",
                    "-print_certs"],
                   stdin=subprocess.PIPE,
                   stdout=subprocess.PIPE)
    out, err = p.communicate(data)
    if err and not err.strip():
      AddProblem("error reading cert:\n" + err)
      return None

    cert = common.ParseCertificate(out)
    if not cert:
      AddProblem("error parsing cert output")
      return None
    return cert
  finally:
    Pop()


class APK(object):
  def __init__(self, full_filename, filename):
    self.filename = filename
    self.certs = None
    self.shared_uid = None
    self.package = None

    Push(filename+":")
    try:
      self.RecordCerts(full_filename)
      self.ReadManifest(full_filename)
    finally:
      Pop()

  def RecordCerts(self, full_filename):
    out = set()
    try:
      f = open(full_filename)
      apk = zipfile.ZipFile(f, "r")
      pkcs7 = None
      for info in apk.infolist():
        if info.filename.startswith("META-INF/") and \
           (info.filename.endswith(".DSA") or info.filename.endswith(".RSA")):
          pkcs7 = apk.read(info.filename)
          cert = CertFromPKCS7(pkcs7, info.filename)
          out.add(cert)
          ALL_CERTS.Add(cert)
      if not pkcs7:
        AddProblem("no signature")
    finally:
      f.close()
      self.certs = frozenset(out)

  def ReadManifest(self, full_filename):
    p = common.Run(["aapt", "dump", "xmltree", full_filename,
                    "AndroidManifest.xml"],
                   stdout=subprocess.PIPE)
    manifest, err = p.communicate()
    if err:
      AddProblem("failed to read manifest")
      return

    self.shared_uid = None
    self.package = None

    for line in manifest.split("\n"):
      line = line.strip()
      m = re.search(r'A: (\S*?)(?:\(0x[0-9a-f]+\))?="(.*?)" \(Raw', line)
      if m:
        name = m.group(1)
        if name == "android:sharedUserId":
          if self.shared_uid is not None:
            AddProblem("multiple sharedUserId declarations")
          self.shared_uid = m.group(2)
        elif name == "package":
          if self.package is not None:
            AddProblem("multiple package declarations")
          self.package = m.group(2)

    if self.package is None:
      AddProblem("no package declaration")


class TargetFiles(object):
  def __init__(self):
    self.max_pkg_len = 30
    self.max_fn_len = 20
    self.apks = None
    self.apks_by_basename = None
    self.certmap = None

  def LoadZipFile(self, filename):
    d, z = common.UnzipTemp(filename, '*.apk')
    try:
      self.apks = {}
      self.apks_by_basename = {}
      for dirpath, _, filenames in os.walk(d):
        for fn in filenames:
          if fn.endswith(".apk"):
            fullname = os.path.join(dirpath, fn)
            displayname = fullname[len(d)+1:]
            apk = APK(fullname, displayname)
            self.apks[apk.package] = apk
            self.apks_by_basename[os.path.basename(apk.filename)] = apk

            self.max_pkg_len = max(self.max_pkg_len, len(apk.package))
            self.max_fn_len = max(self.max_fn_len, len(apk.filename))
    finally:
      shutil.rmtree(d)

    self.certmap = common.ReadApkCerts(z)
    z.close()

  def CheckSharedUids(self):
    """Look for any instances where packages signed with different
    certs request the same sharedUserId."""
    apks_by_uid = {}
    for apk in self.apks.values():
      if apk.shared_uid:
        apks_by_uid.setdefault(apk.shared_uid, []).append(apk)

    for uid in sorted(apks_by_uid.keys()):
      apks = apks_by_uid[uid]
      for apk in apks[1:]:
        if apk.certs != apks[0].certs:
          break
      else:
        # all packages have the same set of certs; this uid is fine.
        continue

      AddProblem("different cert sets for packages with uid %s" % (uid,))

      print("uid %s is shared by packages with different cert sets:" % uid)
      for apk in apks:
        print("%-*s  [%s]" % (self.max_pkg_len, apk.package, apk.filename))
        for cert in apk.certs:
          print("   ", ALL_CERTS.Get(cert))
      print()

  def CheckExternalSignatures(self):
    for apk_filename, certname in iteritems(self.certmap):
      if certname == "EXTERNAL":
        # Apps marked EXTERNAL should be signed with the test key
        # during development, then manually re-signed after
        # predexopting.  Consider it an error if this app is now
        # signed with any key that is present in our tree.
        apk = self.apks_by_basename[apk_filename]
        name = ALL_CERTS.Get(apk.cert)
        if not name.startswith("unknown "):
          Push(apk.filename)
          AddProblem("hasn't been signed with EXTERNAL cert")
          Pop()

  def PrintCerts(self):
    """Display a table of packages grouped by cert."""
    by_cert = {}
    for apk in self.apks.values():
      for cert in apk.certs:
        by_cert.setdefault(cert, []).append((apk.package, apk))

    order = [(-len(v), k) for (k, v) in iteritems(by_cert)]
    order.sort()

    for _, cert in order:
      print("%s:" % ALL_CERTS.Get(cert))
      apks = by_cert[cert]
      apks.sort()
      for _, apk in apks:
        if apk.shared_uid:
          print("  %-*s  %-*s  [%s]" % (self.max_fn_len, apk.filename,
                                        self.max_pkg_len, apk.package,
                                        apk.shared_uid))
        else:
          print("  %-*s  %-*s" % (self.max_fn_len, apk.filename,
                                  self.max_pkg_len, apk.package))
      print()

  def CompareWith(self, other):
    """Look for instances where a given package that exists in both
    self and other have different certs."""

    all_apks = set(self.apks.keys())
    all_apks.update(other.apks.keys())

    max_pkg_len = max(self.max_pkg_len, other.max_pkg_len)

    by_certpair = {}

    for i in all_apks:
      if i in self.apks:
        if i in other.apks:
          # in both; should have same set of certs
          if self.apks[i].certs != other.apks[i].certs:
            by_certpair.setdefault((other.apks[i].certs,
                                    self.apks[i].certs), []).append(i)
        else:
          print("%s [%s]: new APK (not in comparison target_files)" % (
              i, self.apks[i].filename))
      else:
        if i in other.apks:
          print("%s [%s]: removed APK (only in comparison target_files)" % (
              i, other.apks[i].filename))

    if by_certpair:
      AddProblem("some APKs changed certs")
      Banner("APK signing differences")
      for (old, new), packages in sorted(by_certpair.items()):
        for i, o in enumerate(old):
          if i == 0:
            print("was", ALL_CERTS.Get(o))
          else:
            print("   ", ALL_CERTS.Get(o))
        for i, n in enumerate(new):
          if i == 0:
            print("now", ALL_CERTS.Get(n))
          else:
            print("   ", ALL_CERTS.Get(n))
        for i in sorted(packages):
          old_fn = other.apks[i].filename
          new_fn = self.apks[i].filename
          if old_fn == new_fn:
            print("  %-*s  [%s]" % (max_pkg_len, i, old_fn))
          else:
            print("  %-*s  [was: %s; now: %s]" % (max_pkg_len, i,
                                                  old_fn, new_fn))
        print()


def main(argv):
  def option_handler(o, a):
    if o in ("-c", "--compare_with"):
      OPTIONS.compare_with = a
    elif o in ("-l", "--local_cert_dirs"):
      OPTIONS.local_cert_dirs = [i.strip() for i in a.split(",")]
    elif o in ("-t", "--text"):
      OPTIONS.text = True
    else:
      return False
    return True

  args = common.ParseOptions(argv, __doc__,
                             extra_opts="c:l:t",
                             extra_long_opts=["compare_with=",
                                              "local_cert_dirs="],
                             extra_option_handler=option_handler)

  if len(args) != 1:
    common.Usage(__doc__)
    sys.exit(1)

  ALL_CERTS.FindLocalCerts()

  Push("input target_files:")
  try:
    target_files = TargetFiles()
    target_files.LoadZipFile(args[0])
  finally:
    Pop()

  compare_files = None
  if OPTIONS.compare_with:
    Push("comparison target_files:")
    try:
      compare_files = TargetFiles()
      compare_files.LoadZipFile(OPTIONS.compare_with)
    finally:
      Pop()

  if OPTIONS.text or not compare_files:
    Banner("target files")
    target_files.PrintCerts()
  target_files.CheckSharedUids()
  target_files.CheckExternalSignatures()
  if compare_files:
    if OPTIONS.text:
      Banner("comparison files")
      compare_files.PrintCerts()
    target_files.CompareWith(compare_files)

  if PROBLEMS:
    print("%d problem(s) found:\n" % len(PROBLEMS))
    for p in PROBLEMS:
      print(p)
    return 1

  return 0


if __name__ == '__main__':
  try:
    r = main(sys.argv[1:])
    sys.exit(r)
  except common.ExternalError as e:
    print()
    print("   ERROR: %s" % e)
    print()
    sys.exit(1)
