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


import os
import copy
import pkg_resources
import gettext
import datetime


# General

_ = gettext.gettext

PLUGIN_NAME = "LabelPlus"
MODULE_NAME = "labelplus"
DISPLAY_NAME = _("LabelPlus")

STATUS_ID = "%s_id" % MODULE_NAME
STATUS_NAME = "%s_name" % MODULE_NAME

DATETIME_010101 = datetime.datetime(1, 1, 1)


def get_resource(filename):

  return pkg_resources.resource_filename(
      MODULE_NAME, os.path.join("data", filename))


# Logging

class PluginPrefixFilter(object):

  def filter(self, record):

    record.msg = "[%s] %s" % (PLUGIN_NAME, record.msg)
    return True


LOG_FILTER = PluginPrefixFilter()


# Dictionary

def copy_dict_value(src, dest, src_key, dest_key, use_deepcopy=False):

  if use_deepcopy:
    dest[dest_key] = copy.deepcopy(src[src_key])
  else:
    dest[dest_key] = src[src_key]


def update_dict(dest, src, use_deepcopy=False):

  for key in src.keys():
    if key not in dest or not isinstance(src[key], dict):
      copy_dict_value(src, dest, key, key, use_deepcopy)
      continue

    if src[key] is not dest[key]:
      update_dict(dest[key], src[key], use_deepcopy)
