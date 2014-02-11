#
# autolabel.py
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


PROPS = [
  "Name",
  "Tracker",
]

OPS = [
  "contains",
  "doesn't contain",
  "is",
  "is not",
  "starts with",
  "ends with",
  "matches regex",
  "contains words",
]

CASES = [
  "match case",
  "ignore case",
]

OP_FUNCS = {
  OPS[0]: lambda x,y,z: re.search(re.escape(y), x, z),
  OPS[1]: lambda x,y,z: not OP_FUNCS[OPS[0]](x, y, z),
  OPS[2]: lambda x,y,z: re.search('^' + re.escape(y) + '$', x, z),
  OPS[3]: lambda x,y,z: not OP_FUNCS[OPS[2]](x, y, z),
  OPS[4]: lambda x,y,z: re.search('^' + re.escape(y), x, z),
  OPS[5]: lambda x,y,z: re.search(re.escape(y) + '$', x, z),
  OPS[6]: lambda x,y,z: re.search(y, x, z),
  OPS[7]: lambda x,y,z: all(OP_FUNCS[OPS[0]](x, s, z) for s in y.split()),
}

# Columns
COLUMN_PROP = 0
COLUMN_OP = 1
COLUMN_CASE = 2
COLUMN_QUERY = 3
NUM_COLUMNS = 4


#
# props format:
# {
#   "property_name": [property_values],
# }
#
# rules format: [[property, op, case, query],]
#

def find_match(props, rules, match_all=False):

  for rule in rules:
    values = props[rule[COLUMN_PROP]]
    op_func = OP_FUNCS[rule[COLUMN_OP]]

    flags = 0

    if rule[COLUMN_CASE] == "ignore case":
      flags |= re.IGNORECASE

    query = rule[COLUMN_QUERY]
    try:
      query = unicode(query, "utf8")
      flags |= re.UNICODE
    except TypeError:
      flags |= re.UNICODE
    except UnicodeDecodeError:
      pass

    has_match = False

    for value in values:
      if op_func(value, query, flags):
        has_match = True
        break

    if match_all and not has_match:
      return False

    if not match_all and has_match:
      return True

  return match_all
