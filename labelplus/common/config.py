#
# config.py
#
# Copyright (C) 2014 Ratanak Lun <ratanakvlun@gmail.com>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#


import copy


# DEPRECATED START


from validation import require


def get_version(config):

  return config.get("version", 1)


#
# Map format:
# {
#   "version_in": version of input config data
#   "version_out": version of output config data
#   "defaults": dict of defaults for the target output version
#   "map": {
#     "path/variable": "path/variable",
#   }
# }
#

def convert(config, map):

  version_in = map["version_in"]
  version_out = map["version_out"]

  require(get_version(config) == version_in,
    "Unable to convert because version mismatch")

  output = copy.deepcopy(map["defaults"])
  output["version"] = version_out

  for path in map["map"]:
    iter = config
    name = None

    parts = path.split("/")
    for name in parts:
      require(isinstance(iter, dict),
        "Malformed path in config data during conversion")

      if name not in iter:
        name = None
        break

      iter = iter[name]

    if name is None:
      continue

    value_in = iter
    iter = output

    parts = map["map"][path].split("/")
    for i, name in enumerate(parts):
      if i < len(parts)-1:
        iter = iter[name]

    iter[name] = value_in

  return output


# DEPRECATED END


def get_path_mapped_dict(dict_in, path_in, path_out, use_deepcopy=False,
    strict_paths=False):

  # Traverse dict path up to "*" or the end of parts, starting from pos
  def traverse_parts(dict_in, parts, pos):

    while pos < len(parts)-1:
      key = parts[pos]
      if key == "*":
        break

      if not isinstance(dict_in, dict):
        raise KeyError("/".join(parts[:pos+1]))

      if key not in dict_in:
        raise KeyError("/".join(parts[:pos+1]))

      dict_in = dict_in[key]
      pos += 1

    if not isinstance(dict_in, dict):
      raise KeyError("/".join(parts[:pos+1]))

    return dict_in, pos


  # Build dict path up to "*" or the end of parts, starting from pos
  def build_parts(dict_in, parts, pos):

    while pos < len(parts)-1:
      key = parts[pos]
      if key == "*":
        break

      dict_in[key] = {}
      dict_in = dict_in[key]
      pos += 1

    return dict_in, pos


  def copy_value(dict_in, dict_out, key_in, key_out):

    if use_deepcopy:
      dict_out[key_out] = copy.deepcopy(dict_in[key_in])
    else:
      dict_out[key_out] = dict_in[key_in]


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
    dict_out, pos_out = build_parts(dict_out, parts_out, pos_out)

    key_in = parts_in[pos_in]
    key_out = parts_out[pos_out]
    # Since number of "*" is required to be the same, either both keys are "*"
    # or are both the last keys in their respective paths

    if key_in != "*":
    # Both keys are last keys; just copy value
      if key_in not in dict_in:
        if strict_paths:
          raise KeyError("/".join(parts_in))
      else:
        copy_value(dict_in, dict_out, key_in, key_out)
        has_mapped = True
    else:
    # Both keys are wildcards
      if pos_in == len(parts_in)-1 and pos_out == len(parts_out)-1:
      # Both keys are last keys; for each child, copy value
        for key in dict_in:
          copy_value(dict_in, dict_out, key, key)

        if len(dict_in) > 0:
          has_mapped = True
      elif pos_in == len(parts_in)-1:
      # Out has extra parts; for each child, build extra out parts, then copy
        for key in dict_in:
          dict_out[key] = {}
          dict_out_end, pos = build_parts(dict_out[key], parts_out, pos_out+1)
          key_out = parts_out[pos]
          copy_value(dict_in, dict_out_end, key, key_out)

        if len(dict_in) > 0:
          has_mapped = True
      elif pos_out == len(parts_out)-1:
      # In has extra parts; for each child, traverse extra in parts, then copy
        for key in dict_in:
          try:
            parts_in[pos_in] = key

            dict_in_end, pos = traverse_parts(dict_in[key], parts_in, pos_in+1)
            key_in = parts_in[pos]

            if key_in not in dict_in_end:
              raise KeyError("/".join(parts_in))

            copy_value(dict_in_end, dict_out, key_in, key)
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


#
# map format:
# {
#   "version_in": version of input config data,
#   "version_out": version of output config data,
#   "defaults": dict of defaults for the target output version,
#   "map": {
#     "path/variable": "path/variable",
#   },
#   "post_func": func to run after mapping, func(map, dict_in, dict_out),
# }
#

def convert_new(config, map):

  version_in = map["version_in"]
  version_out = map["version_out"]

  if config._Config__version["file"] != version_in:
    raise ValueError("Unable to convert because version mismatch")

  input = config.config
  output = copy.deepcopy(map["defaults"])

  for path in map["map"]:
    mapped = get_path_mapped_dict(input, path, map["map"][path])
    output.update(mapped)

  post_func = map.get("post_func")
  if post_func:
    post_func(map, input, output)

  config._Config__version["file"] = version_out
  config._Config__config = output
