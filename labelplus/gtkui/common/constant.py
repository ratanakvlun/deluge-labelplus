#
# constant.py
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


from labelplus.common.constant import MODULE_NAME
from labelplus.common.constant import ID_ALL


GTKUI_CONFIG = "%s_ui.conf" % MODULE_NAME

GTKUI_DEFAULTS_V1 = {
  "name_input_size": None,
  "name_input_pos": None,
  "label_options_size": None,
  "label_options_pos": None,
  "prefs_state": [],
  "sidebar_state": {
    "selected": ID_ALL,
    "expanded": [],
  },
  "show_label_bandwidth": False,
}

DAEMON_DEFAULTS_V1 = {
  "sidebar_state": {
    "selected": ID_ALL,
    "expanded": [],
  },
}

GTKUI_DEFAULTS_V2 = {
  "version": 2,
  "common": {
    "name_input_size": None,
    "name_input_pos": None,
    "label_options_size": None,
    "label_options_pos": None,
    "prefs_state": [],
    "show_label_bandwidth": False,
  },
  "daemon": {
    "127.0.0.1:58846": dict(DAEMON_DEFAULTS_V1),
  },
}

GTKUI_DEFAULTS = GTKUI_DEFAULTS_V1
DAEMON_DEFAULTS = DAEMON_DEFAULTS_V1

GTKUI_MAP_V1_V2 = {
  "version_in": 1,
  "version_out": 2,
  "defaults": GTKUI_DEFAULTS_V2,
  "map": {
    "name_input_size": "common/name_input_size",
    "name_input_pos": "common/name_input_pos",
    "label_options_size": "common/label_options_size",
    "label_options_pos": "common/label_options_pos",
    "prefs_state": "common/prefs_state",
    "show_label_bandwidth": "common/show_label_bandwidth",
  },
}
