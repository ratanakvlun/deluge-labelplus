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


import labelplus.common
import labelplus.core.config


def convert_v1_v2(map, dict_in, dict_out):

  def convert_auto_queries(dict_in, op):

    rules = []
    case = "match case"

    if dict_in.get("auto_tracker"):
      prop = "Tracker"
    else:
      prop = "Name"

    for line in dict_in.get("auto_queries") or ():
      rules.append([prop, op, case, line])

    dict_in["autolabel_rules"] = rules
    dict_in["autolabel_match_all"] = False


  label_defaults = dict_out["prefs"]["defaults"]
  option_defaults = dict_out["prefs"]["options"]

  labels = dict_out["labels"]

  op = "contains words"
  if option_defaults.get("autolabel_uses_regex"):
    op = "matches regex"

  convert_auto_queries(label_defaults, op)

  for label in labels:
    if label in labelplus.common.RESERVED_IDS:
      continue

    convert_auto_queries(labels[label]["data"], op)


CONFIG_MAP_V1_V2 = {
  "version_in": 1,
  "version_out": 2,
  "defaults": labelplus.core.config.CONFIG_DEFAULTS_V2,
  "map": {
    "*": "*",
  },
  "post_func": convert_v1_v2,
}

CONFIG_MAPS = {
  (1, 2): CONFIG_MAP_V1_V2,
}
