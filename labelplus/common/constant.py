#
# constant.py
#
# Copyright (C) 2013 Ratanak Lun <ratanakvlun@gmail.com>
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


PLUGIN_NAME = "LabelPlus"
MODULE_NAME = "labelplus"
DISPLAY_NAME = _("Label Plus")

CORE_CONFIG = "%s.conf" % MODULE_NAME
GTKUI_CONFIG = "%s_ui.conf" % MODULE_NAME
WEBUI_SCRIPT = "%s.js" % MODULE_NAME

STATUS_ID = "%s_id" % MODULE_NAME
STATUS_PATH = "%s_path" % MODULE_NAME

NULL_PARENT = "-"
ID_ALL = "All"
ID_NONE = "None"
RESERVED_IDS = (NULL_PARENT, ID_ALL, ID_NONE)

GTKUI_DEFAULTS = {
  "name_input_size": (-1, -1),
  "label_options_size": (-1, -1),
  "prefs_state": [],
  "sidebar_state": {
    "selected": ID_ALL,
    "expanded": [],
  },
}

OPTION_DEFAULTS = {
  "include_children": False,
}

LABEL_DEFAULTS = {
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
