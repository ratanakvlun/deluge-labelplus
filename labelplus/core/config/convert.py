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


import labelplus.common.label
import labelplus.common.config
import labelplus.common.config.autolabel


def convert_v1_v2(spec, dict_in):

  def remove_v1_prefix(dict_in):

    labels = dict_in["labels"]
    for id in labels.keys():
      if id.startswith("-"):
        data = labels[id]
        del labels[id]

        new_id = id.partition(":")[2]
        labels[new_id] = data

    mappings = dict_in["mappings"]
    for id in mappings:
      label_id = mappings[id]
      if label_id.startswith("-:"):
        mappings[id] = label_id.partition(":")[2]


  def convert_auto_queries(dict_in, op):

    rules = []
    case = labelplus.common.config.autolabel.CASE_MATCH

    if dict_in["auto_tracker"]:
      prop = labelplus.common.config.autolabel.PROP_TRACKER
    else:
      prop = labelplus.common.config.autolabel.PROP_NAME

    for line in dict_in["auto_queries"]:
      rules.append([prop, op, case, line])

    dict_in["autolabel_rules"] = rules
    dict_in["autolabel_match_all"] = False


  label_defaults = dict_in["prefs"]["defaults"]
  option_defaults = dict_in["prefs"]["options"]

  remove_v1_prefix(dict_in)

  op = labelplus.common.config.autolabel.OP_CONTAINS_WORDS
  if option_defaults.get("autolabel_uses_regex"):
    op = labelplus.common.config.autolabel.OP_MATCHES_REGEX

  convert_auto_queries(label_defaults, op)

  labels = dict_in["labels"]
  for id in labels.keys():
    if id in labelplus.common.label.RESERVED_IDS:
      del labels[id]
      continue

    convert_auto_queries(labels[id]["data"], op)

  return dict_in


CONFIG_SPEC_V1_V2 = {
  "version_in": 1,
  "version_out": 2,
  "defaults": labelplus.common.config.CONFIG_DEFAULTS_V2,
  "map": {
    "prefs/options": "prefs/options",
    "prefs/options/shared_limit_update_interval":
      "prefs/options/shared_limit_interval",

    "prefs/defaults": "prefs/label",
    "prefs/defaults/move_data_completed":
      "prefs/label/move_completed",
    "prefs/defaults/move_data_completed_path":
      "prefs/label/move_completed_path",
    "prefs/defaults/move_data_completed_mode":
      "prefs/label/move_completed_mode",
    "prefs/defaults/shared_limit_on":
      "prefs/label/shared_limit",
    "prefs/defaults/auto_settings":
      "prefs/label/autolabel_settings",

    "labels": "labels",
    "labels/*/data": "labels/*/options",
    "labels/*/data/move_data_completed":
      "labels/*/options/move_completed",
    "labels/*/data/move_data_completed_path":
      "labels/*/options/move_completed_path",
    "labels/*/data/move_data_completed_mode":
      "labels/*/options/move_completed_mode",
    "labels/*/data/shared_limit_on":
      "labels/*/options/shared_limit",
    "labels/*/data/auto_settings":
      "labels/*/options/autolabel_settings",

    "mappings": "mappings",
  },
  "post_func": convert_v1_v2,
}

CONFIG_SPECS = {
  (1, 2): CONFIG_SPEC_V1_V2,
}
