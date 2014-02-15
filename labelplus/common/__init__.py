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
import pkg_resources
import re
import gettext


# General

_ = gettext.gettext

PLUGIN_NAME = "LabelPlus"
MODULE_NAME = "labelplus"
DISPLAY_NAME = _("LabelPlus")

STATUS_ID = "%s_id" % MODULE_NAME
STATUS_NAME = "%s_name" % MODULE_NAME

NULL_PARENT = "-"
ID_ALL = "All"
ID_NONE = "None"
RESERVED_IDS = (NULL_PARENT, ID_ALL, ID_NONE)


def get_resource(filename):

  return pkg_resources.resource_filename(
      MODULE_NAME, os.path.join("data", filename))


# Logging

class PluginPrefixFilter(object):

  def filter(self, record):

    record.msg = "[%s] %s" % (PLUGIN_NAME, record.msg)
    return True


LOG_FILTER = PluginPrefixFilter()


# Label

def get_parent_id(label_id):

  return label_id.rpartition(":")[0]


def is_ancestor(ancestor_id, label_id):

  prefix = "%s:" % ancestor_id

  return ancestor_id != label_id and label_id.startswith(prefix)


def get_name_by_depth(full_name, depth=0):

  if depth < 1:
    return full_name

  return "/".join(name.split("/")[-depth:])


# Validation

RE_INVALID_CHARS = re.compile("[\x00-\x1f\x7f\x22\*/:<>\?|\\\\]")


def validate_name(label_name):

  if not label_name:
    raise ValueError("Empty label")

  if RE_INVALID_CHARS.search(label_name):
    raise ValueError("Invalid characters")
