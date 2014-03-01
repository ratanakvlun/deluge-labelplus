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


import labelplus.common.config


def remove_invalid_keys(dict_in):

  for key in dict_in.keys():
    if key not in labelplus.common.config.CONFIG_DEFAULTS:
      del dict_in[key]

  for key in dict_in["prefs"].keys():
    if key not in labelplus.common.config.CONFIG_DEFAULTS["prefs"]:
      del dict_in["prefs"][key]

  for key in dict_in["prefs"]["options"].keys():
    if key not in labelplus.common.config.OPTION_DEFAULTS:
      del dict_in["prefs"]["options"][key]

  for key in dict_in["prefs"]["label"].keys():
    if key not in labelplus.common.config.LABEL_DEFAULTS:
      del dict_in["prefs"]["label"][key]

  for id in dict_in["labels"]:
    options = dict_in["labels"][id]["options"]
    for key in options.keys():
      if key not in labelplus.common.config.LABEL_DEFAULTS:
        del options[key]
