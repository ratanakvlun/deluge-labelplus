#
# __init__.py
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


import convert


MOVE_PARENT = "parent"
MOVE_SUBFOLDER = "subfolder"
MOVE_FOLDER = "folder"
MOVE_MODES = (MOVE_PARENT, MOVE_SUBFOLDER, MOVE_FOLDER)

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
  "move_data_completed_mode": MOVE_FOLDER,
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
  "move_on_changes": False,
  "shared_limit_interval": 5,
  "move_after_recheck": False,
}

LABEL_DEFAULTS_V2 = {
  "download_settings": False,
  "move_completed": False,
  "move_completed_path": "",
  "move_completed_mode": MOVE_FOLDER,
  "prioritize_first_last": False,

  "bandwidth_settings": False,
  "max_download_speed": -1.0,
  "max_upload_speed": -1.0,
  "max_connections": -1,
  "max_upload_slots": -1,
  "shared_limit": False,

  "queue_settings": False,
  "auto_managed": False,
  "stop_at_ratio": False,
  "stop_ratio": 1.0,
  "remove_at_ratio": False,

  "autolabel_settings": False,
  "autolabel_match_all": False,
  "autolabel_rules": [],
}

CONFIG_DEFAULTS_V2 = {
  "prefs": {
    "options": OPTION_DEFAULTS_V2,
    "label": LABEL_DEFAULTS_V2,
  },
  "labels": {},   # "label_id": {"name": str, "data": dict}
  "mappings": {}, # "torrent_id": "label_id"
}

CONFIG_VERSION = 2
CONFIG_DEFAULTS = CONFIG_DEFAULTS_V2
OPTION_DEFAULTS = OPTION_DEFAULTS_V2
LABEL_DEFAULTS = LABEL_DEFAULTS_V2


def get_version(config):

  return config._Config__version["file"]


def set_version(config, version):

  config._Config__version["file"] = version


def init_config(config, defaults, version, specs):

  if len(config.config) == 0:
    config.config.update(copy.deepcopy(defaults))
    set_version(config, version)

  file_ver = get_version(config)
  ver = file_ver
  while ver != version:
    if ver < version:
      key = (ver, ver+1)
    else:
      key = (ver, ver-1)

    spec = specs.get(key)
    if spec:
      convert.convert(spec, config)
      ver = get_version(config)
    else:
      raise ValueError("Config file conversion v%s -> v%s not supported" %
        (file_ver, version))

  for key in config.config.keys():
    if key not in defaults:
      del config.config[key]
