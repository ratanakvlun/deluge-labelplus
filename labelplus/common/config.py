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


import constant


def get_version(config):

  return config._Config__version["file"]


OPTION_DEFAULTS_V1 = {
  "include_children": False,
  "show_full_name": False,
  "move_on_changes": False,
  "autolabel_uses_regex": False,
  "shared_limit_update_interval": 5,
  "move_after_recheck": False,
}

LABEL_DEFAULTS_V1 = {
  "download_settings": False,
  "move_data_completed": False,
  "move_data_completed_path": "",
  "move_data_completed_mode": "folder",
  "prioritize_first_last": False,

  "bandwidth_settings": False,
  "max_download_speed": -1.0,
  "max_upload_speed": -1.0,
  "max_connections": -1,
  "max_upload_slots": -1,
  "shared_limit_on": False,

  "queue_settings": False,
  "auto_managed": False,
  "stop_at_ratio": False,
  "stop_ratio": 1.0,
  "remove_at_ratio": False,

  "auto_settings": False,
  "auto_name": True,
  "auto_tracker": False,
  "auto_queries": [],
}

CONFIG_DEFAULTS_V1 = {
  "prefs": {
    "options": OPTION_DEFAULTS_V1,
    "defaults": LABEL_DEFAULTS_V1,
  },
  "labels": {},   # "label_id": {"name": str, "data": dict}
  "mappings": {}, # "torrent_id": "label_id"
}

OPTION_DEFAULTS_V2 = {
  "include_children": False,
  "show_full_name": False,
  "move_on_changes": False,
  "shared_limit_update_interval": 5,
  "move_after_recheck": False,
}

LABEL_DEFAULTS_V2 = {
  "download_settings": False,
  "move_data_completed": False,
  "move_data_completed_path": "",
  "move_data_completed_mode": "folder",
  "prioritize_first_last": False,

  "bandwidth_settings": False,
  "max_download_speed": -1.0,
  "max_upload_speed": -1.0,
  "max_connections": -1,
  "max_upload_slots": -1,
  "shared_limit_on": False,

  "queue_settings": False,
  "auto_managed": False,
  "stop_at_ratio": False,
  "stop_ratio": 1.0,
  "remove_at_ratio": False,

  "auto_settings": False,
  "autolabel_match_all": False,
  "autolabel_rules": [],
}

CONFIG_DEFAULTS_V2 = {
  "prefs": {
    "options": OPTION_DEFAULTS_V2,
    "defaults": LABEL_DEFAULTS_V2,
  },
  "labels": {},   # "label_id": {"name": str, "data": dict}
  "mappings": {}, # "torrent_id": "label_id"
}

CONFIG_VERSION = 2
CONFIG_DEFAULTS = CONFIG_DEFAULTS_V2
OPTION_DEFAULTS = OPTION_DEFAULTS_V2
LABEL_DEFAULTS = LABEL_DEFAULTS_V2


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
    if label in constant.RESERVED_IDS:
      continue

    convert_auto_queries(labels[label]["data"], op)


CONFIG_MAP_V1_V2 = {
  "version_in": 1,
  "version_out": 2,
  "defaults": CONFIG_DEFAULTS_V2,
  "map": {
    "*": "*",
  },
  "post_func": convert_v1_v2,
}

CONFIG_MAPS = {
  (1, 2): CONFIG_MAP_V1_V2,
}
