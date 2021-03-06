# Copyright 2012 the V8 project authors. All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#     * Neither the name of Google Inc. nor the names of its
#       contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import re
import shlex

from ..local import command
from ..local import utils

FLAGS_PATTERN = re.compile(r"//\s+Flags:(.*)")


class TestCase(object):
  def __init__(self, suite, path, name):
    self.suite = suite        # TestSuite object

    self.path = path          # string, e.g. 'div-mod', 'test-api/foo'
    self.name = name          # string that identifies test in the status file

    self.variant = None       # name of the used testing variant
    self.variant_flags = []   # list of strings, flags specific to this test

    self.output = None
    self.id = None  # int, used to map result back to TestCase instance
    self.duration = None  # assigned during execution
    self.run = 1  # The nth time this test is executed.
    self.cmd = None

  def precompute(self):
    """It precomputes all things that can be shared among all variants of this
    object (like flags from source file). Values calculated here should be
    immutable and shared among all copies (in _copy implementation).
    """
    pass

  def create_variant(self, variant, flags):
    copy = self._copy()
    if not self.variant_flags:
      copy.variant_flags = flags
    else:
      copy.variant_flags = self.variant_flags + flags
    copy.variant = variant
    return copy

  def _copy(self):
    """Makes a copy of the object. It should be overriden in case of any
    additional constructor parameters or precomputed fields.
    """
    return self.__class__(self.suite, self.path, self.name)

  def get_command(self, context):
    params = self._get_cmd_params(context)
    env = self._get_cmd_env()
    shell, shell_flags = self._get_shell_with_flags(context)
    timeout = self._get_timeout(params, context.timeout)
    return self._create_cmd(shell, shell_flags + params, env, timeout, context)

  def _get_cmd_params(self, ctx):
    """Gets command parameters and combines them in the following order:
      - files [empty by default]
      - extra flags (from command line)
      - user flags (variant/fuzzer flags)
      - statusfile flags
      - mode flags (based on chosen mode)
      - source flags (from source code) [empty by default]

    The best way to modify how parameters are created is to only override
    methods for getting partial parameters.
    """
    return (
        self._get_files_params(ctx) +
        self._get_extra_flags(ctx) +
        self._get_variant_flags() +
        self._get_statusfile_flags() +
        self._get_mode_flags(ctx) +
        self._get_source_flags() +
        self._get_suite_flags(ctx)
    )

  def _get_cmd_env(self):
    return {}

  def _get_files_params(self, ctx):
    return []

  def _get_extra_flags(self, ctx):
    return ctx.extra_flags

  def _get_variant_flags(self):
    return self.variant_flags

  def _get_statusfile_flags(self):
    """Gets runtime flags from a status file.

    Every outcome that starts with "--" is a flag. Status file has to be loaded
    before using this function.
    """

    flags = []
    for outcome in self.suite.GetStatusFileOutcomes(self.name, self.variant):
      if outcome.startswith('--'):
        flags.append(outcome)
    return flags

  def _get_mode_flags(self, ctx):
    return ctx.mode_flags

  def _get_source_flags(self):
    return []

  def _get_suite_flags(self, ctx):
    return []

  def _get_shell_with_flags(self, ctx):
    shell = self._get_shell()
    shell_flags = []
    if shell == 'd8':
      shell_flags.append('--test')
    if utils.IsWindows():
      shell += '.exe'
    if ctx.random_seed:
      shell_flags.append('--random-seed=%s' % ctx.random_seed)
    return shell, shell_flags

  def _get_timeout(self, params, timeout):
    if "--stress-opt" in params:
      timeout *= 4
    if "--noenable-vfp3" in params:
      timeout *= 2

    # TODO(majeski): make it slow outcome dependent.
    timeout *= 2
    return timeout

  def _get_shell(self):
    return 'd8'

  def _get_suffix(self):
    return '.js'

  def _create_cmd(self, shell, params, env, timeout, ctx):
    return command.Command(
      cmd_prefix=ctx.command_prefix,
      shell=os.path.abspath(os.path.join(ctx.shell_dir, shell)),
      args=params,
      env=env,
      timeout=timeout,
      verbose=ctx.verbose
    )

  def _parse_source_flags(self, source=None):
    source = source or self.get_source()
    flags = []
    for match in re.findall(FLAGS_PATTERN, source):
      flags += shlex.split(match.strip())
    return flags

  def is_source_available(self):
    return self._get_source_path() is not None

  def get_source(self):
    with open(self._get_source_path()) as f:
      return f.read()

  def _get_source_path(self):
    return None

  def __cmp__(self, other):
    # Make sure that test cases are sorted correctly if sorted without
    # key function. But using a key function is preferred for speed.
    return cmp(
        (self.suite.name, self.name, self.variant_flags),
        (other.suite.name, other.name, other.variant_flags)
    )

  def __str__(self):
    return self.suite.name + '/' + self.name

  # TODO(majeski): Rename `id` field or `get_id` function since they're
  # unrelated.
  def get_id(self):
    return '%s/%s %s' % (
        self.suite.name, self.name, ' '.join(self.variant_flags))
