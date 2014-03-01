#
# convert.py
#
# Copyright (C) 2014 Ratanak Lun <ratanakvlun@gmail.com>
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Linking this software with other modules is making a combined work
# based on this software. Thus, the terms and conditions of the GNU
# General Public License cover the whole combination.
#
# As a special exception, the copyright holders of this software give
# you permission to link this software with independent modules to
# produce a combined work, regardless of the license terms of these
# independent modules, and to copy and distribute the resulting work
# under terms of your choice, provided that you also meet, for each
# linked module in the combined work, the terms and conditions of the
# license of that module. An independent module is a module which is
# not derived from or based on this software. If you modify this
# software, you may extend this exception to your version of the
# software, but you are not obligated to do so. If you do not wish to
# do so, delete this exception statement from your version.
#


import copy

import labelplus.common


def get_path_mapped_dict(dict_in, path_in, path_out, use_deepcopy=False,
    strict_paths=False):

  # Traverse dict path up to "*" or the end of parts, starts at pos
  def traverse_parts(dict_in, parts, pos, build=False):

    while pos < len(parts)-1:
      key = parts[pos]
      if key == "*":
        break

      if not isinstance(dict_in, dict):
        raise KeyError("/".join(parts[:pos+1]))

      if key not in dict_in:
        if build:
          dict_in[key] = {}
        else:
          raise KeyError("/".join(parts[:pos+1]))

      dict_in = dict_in[key]
      pos += 1

    if not isinstance(dict_in, dict):
      raise KeyError("/".join(parts[:pos+1]))

    return dict_in, pos


  def recurse(dict_in, dict_out, pos_in, pos_out):

    try:
      dict_in, pos_in = traverse_parts(dict_in, parts_in, pos_in)
    except KeyError:
      if strict_paths:
        raise
      else:
        return False

    has_mapped = False
    # Set to True if at least one path was successfully mapped

    initial_dict_out = dict_out
    dict_out, pos_out = traverse_parts(dict_out, parts_out, pos_out, True)

    key_in = parts_in[pos_in]
    key_out = parts_out[pos_out]
    # Since number of "*" is required to be the same, both keys are
    # either "*" or the last key in their respective paths

    if key_in != "*":
    # Both keys are last keys; just copy value
      if key_in not in dict_in:
        if strict_paths:
          raise KeyError("/".join(parts_in))
      else:
        copy_dict_value(dict_in, dict_out, key_in, key_out, use_deepcopy)
        has_mapped = True
    else:
    # Both keys are wildcards
      if pos_in == len(parts_in)-1 and pos_out == len(parts_out)-1:
      # Both keys are last keys; for each child, copy value
        for key in dict_in:
          copy_dict_value(dict_in, dict_out, key, key, use_deepcopy)

        if len(dict_in) > 0:
          has_mapped = True
      elif pos_in == len(parts_in)-1:
      # Out has extra parts; for each child, build extra out parts, then copy
        for key in dict_in:
          dict_out[key] = {}
          dict_out_end, pos = traverse_parts(dict_out[key],
            parts_out, pos_out+1, True)

          key_out = parts_out[pos]
          copy_dict_value(dict_in, dict_out_end, key, key_out, use_deepcopy)

        if len(dict_in) > 0:
          has_mapped = True
      elif pos_out == len(parts_out)-1:
      # In has extra parts; for each child, traverse extra in parts, then copy
        for key in dict_in:
          try:
            parts_in[pos_in] = key

            dict_in_end, pos = traverse_parts(dict_in[key],
              parts_in, pos_in+1)
            key_in = parts_in[pos]

            if key_in not in dict_in_end:
              raise KeyError("/".join(parts_in))

            copy_dict_value(dict_in_end, dict_out, key_in, key, use_deepcopy)
            has_mapped = True
          except KeyError:
            if strict_paths:
              raise
            else:
              continue
          finally:
            parts_in[pos_in] = "*"
      else:
      # Both have more parts; for each child at this level, recurse
        for key in dict_in:
          parts_in[pos_in] = key

          dict_out[key] = {}
          if recurse(dict_in[key], dict_out[key], pos_in+1, pos_out+1):
            has_mapped = True
          else:
            del dict_out[key]

        parts_in[pos_in] = "*"

    if not has_mapped:
      initial_dict_out.clear()

    return has_mapped


  parts_in = path_in.split("/")
  parts_out = path_out.split("/")

  if parts_in.count("*") != parts_out.count("*"):
    raise ValueError("Wildcard mismatch in path: %r -> %r" %
      (path_in, path_out))

  buffer_out = {}
  recurse(dict_in, buffer_out, 0, 0)

  return buffer_out


def process_spec(spec, dict_in):

  working_dict = {}

  # Pre function meant for mapping preparations
  pre_func = spec.get("pre_func")
  if pre_func:
    dict_in = pre_func(spec, dict_in)

  # Mapping meant for excluding unused keys or rearranging keys
  for src, dest in sorted(spec["map"].items(), key=lambda x: x[1].count("/")):
    mapped = get_path_mapped_dict(dict_in, src, dest, spec["deepcopy"],
      spec["strict"])
    labelplus.common.update_dict(working_dict, mapped)

  # Post function meant for altering values
  post_func = spec.get("post_func")
  if post_func:
    working_dict = post_func(spec, working_dict)

  # Make sure any missing keys are in the final dict
  dict_out = copy.deepcopy(spec["defaults"])
  labelplus.common.update_dict(dict_out, working_dict)

  return dict_out


#
# spec format:
# {
#   "version_in": version of input config data,
#   "version_out": version of output config data,
#   "defaults": dict of defaults for the target output version,
#   "strict": whether or not invalid paths cause exceptions
#   "deepcopy": whether or not to deepcopy when copying values
#   "pre_func": called before mapping, pre_func(spec, dict),
#   "post_func": called after mapping, post_func(spec, dict),
#   "map": {
#     "path/variable": "path/variable",
#   },
# }
#

def convert(spec, config):

  version_in = spec["version_in"]
  version_out = spec["version_out"]

  if config._Config__version["file"] != version_in:
    raise ValueError("Unable to convert because version mismatch")

  input = config.config
  output = process_spec(spec, input)

  config._Config__version["file"] = version_out
  config._Config__config = output
