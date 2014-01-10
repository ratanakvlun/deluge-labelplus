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
#     (path_segments, ..., variable): (path_segments, ..., variable),
#   }
# }
#

def convert(config, map):

  version_in = map["version_in"]
  version_out = map["version_out"]

  require(get_version(config) == version_in,
    "Convert: version mismatch")

  output = dict(map["defaults"])
  output["version"] = version_out

  for path in map["map"]:
    iter = config
    name = None

    parts = path.split("/")
    for name in parts:
      require(isinstance(iter, dict),
        "Convert: malformed path in config data")

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
