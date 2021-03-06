# Copyright 2016 the V8 project authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import itertools
import os

from testrunner.local import testsuite
from testrunner.local import utils
from testrunner.objects import testcase

PROTOCOL_TEST_JS = "protocol-test.js"
EXPECTED_SUFFIX = "-expected.txt"
RESOURCES_FOLDER = "resources"

class TestSuite(testsuite.TestSuite):
  def ListTests(self, context):
    tests = []
    for dirname, dirs, files in os.walk(
        os.path.join(self.root), followlinks=True):
      for dotted in [x for x in dirs if x.startswith('.')]:
        dirs.remove(dotted)
      if dirname.endswith(os.path.sep + RESOURCES_FOLDER):
        continue
      dirs.sort()
      files.sort()
      for filename in files:
        if filename.endswith(".js") and filename != PROTOCOL_TEST_JS:
          fullpath = os.path.join(dirname, filename)
          relpath = fullpath[len(self.root) + 1 : -3]
          testname = relpath.replace(os.path.sep, "/")
          test = self._create_test(testname)
          tests.append(test)
    return tests

  def _test_class(self):
    return TestCase

  def _IgnoreLine(self, string):
    """Ignore empty lines, valgrind output and Android output."""
    if not string:
      return True
    return (string.startswith("==") or string.startswith("**") or
            string.startswith("ANDROID") or
            # FIXME(machenbach): The test driver shouldn't try to use slow
            # asserts if they weren't compiled. This fails in optdebug=2.
            string == "Warning: unknown flag --enable-slow-asserts." or
            string == "Try --help for options")

  def IsFailureOutput(self, test):
    file_name = os.path.join(self.root, test.path) + EXPECTED_SUFFIX
    with file(file_name, "r") as expected:
      expected_lines = expected.readlines()

    def ExpIterator():
      for line in expected_lines:
        if not line.strip():
          continue
        yield line.strip()

    def ActIterator(lines):
      for line in lines:
        if self._IgnoreLine(line.strip()):
          continue
        yield line.strip()

    def ActBlockIterator():
      """Iterates over blocks of actual output lines."""
      lines = test.output.stdout.splitlines()
      start_index = 0
      found_eqeq = False
      for index, line in enumerate(lines):
        # If a stress test separator is found:
        if line.startswith("=="):
          # Iterate over all lines before a separator except the first.
          if not found_eqeq:
            found_eqeq = True
          else:
            yield ActIterator(lines[start_index:index])
          # The next block of output lines starts after the separator.
          start_index = index + 1
      # Iterate over complete output if no separator was found.
      if not found_eqeq:
        yield ActIterator(lines)

    for act_iterator in ActBlockIterator():
      for (expected, actual) in itertools.izip_longest(
          ExpIterator(), act_iterator, fillvalue=''):
        if expected != actual:
          return True
      return False


class TestCase(testcase.TestCase):
  def __init__(self, *args, **kwargs):
    super(TestCase, self).__init__(*args, **kwargs)

    # precomputed
    self._source_flags = None

  def precompute(self):
    self._source_flags = self._parse_source_flags()

  def _copy(self):
    copy = super(TestCase, self)._copy()
    copy._source_flags = self._source_flags
    return copy

  def _get_files_params(self, ctx):
    return [
      os.path.join(self.suite.root, PROTOCOL_TEST_JS),
      os.path.join(self.suite.root, self.path + self._get_suffix()),
    ]

  def _get_source_flags(self):
    return self._source_flags

  def _get_source_path(self):
    return os.path.join(self.suite.root, self.path + self._get_suffix())

  def _get_shell(self):
    return 'inspector-test'


def GetSuite(name, root):
  return TestSuite(name, root)
