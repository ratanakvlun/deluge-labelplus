#
# label.py
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


import re


ID_NULL = ""
ID_ALL = "All"
ID_NONE = "None"
RESERVED_IDS = (ID_NULL, ID_ALL, ID_NONE)

RE_INVALID_CHARS = re.compile("[\x00-\x1f\x7f\x22\*/:<>\?|\\\\]")


def get_parent_id(label_id):

  return label_id.rpartition(":")[0]


def is_ancestor(ancestor_id, label_id):

  if ancestor_id == ID_NULL:
    prefix = ""
  else:
    prefix = "%s:" % ancestor_id

  return ancestor_id != label_id and label_id.startswith(prefix)


def resolve_name_by_degree(name, degree):

  if degree < 1:
    return ""

  return "/".join(name.split("/")[-degree:])


def validate_name(label_name):

  if not label_name:
    raise ValueError("Empty label")

  if RE_INVALID_CHARS.search(label_name):
    raise ValueError("Invalid characters")
