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


import labelplus.common.label


GTKUI_DEFAULTS_V1 = {
  "name_input_size": None,
  "name_input_pos": None,
  "label_options_size": None,
  "label_options_pos": None,
  "prefs_state": [],
  "sidebar_state": {
    "selected": labelplus.common.label.ID_ALL,
    "expanded": [],
  },
  "show_label_bandwidth": False,
}

DAEMON_DEFAULTS_V1 = {
  "sidebar_state": {
    "selected": labelplus.common.label.ID_ALL,
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
    "status_include_sublabel": False,
  },
  "daemon": {},
}

CONFIG_VERSION = 2
GTKUI_DEFAULTS = GTKUI_DEFAULTS_V2
DAEMON_DEFAULTS = DAEMON_DEFAULTS_V1
