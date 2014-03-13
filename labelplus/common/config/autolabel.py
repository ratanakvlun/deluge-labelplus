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


PROP_NAME = "Name"
PROP_TRACKER = "Tracker"

PROPS = (
  PROP_NAME,
  PROP_TRACKER,
)

OP_CONTAINS = "contains"
OP_DOESNT_CONTAIN = "doesn't contain"
OP_IS = "is"
OP_IS_NOT = "is not"
OP_STARTS_WITH = "starts with"
OP_ENDS_WITH = "ends with"
OP_MATCHES_REGEX = "matches regex"
OP_CONTAINS_WORDS = "contains words"

OPS = (
  OP_CONTAINS,
  OP_DOESNT_CONTAIN,
  OP_IS,
  OP_IS_NOT,
  OP_STARTS_WITH,
  OP_ENDS_WITH,
  OP_MATCHES_REGEX,
  OP_CONTAINS_WORDS,
)

CASE_MATCH = "match case"
CASE_IGNORE = "ignore case"

CASES = (
  CASE_MATCH,
  CASE_IGNORE,
)

OP_FUNCS = {
  OP_CONTAINS: lambda x,y,z: re.search(re.escape(y), x, z),
  OP_DOESNT_CONTAIN: lambda x,y,z: not OP_FUNCS[OP_CONTAINS](x, y, z),
  OP_IS: lambda x,y,z: re.search('^' + re.escape(y) + '$', x, z),
  OP_IS_NOT: lambda x,y,z: not OP_FUNCS[OP_IS](x, y, z),
  OP_STARTS_WITH: lambda x,y,z: re.search('^' + re.escape(y), x, z),
  OP_ENDS_WITH: lambda x,y,z: re.search(re.escape(y) + '$', x, z),
  OP_MATCHES_REGEX: lambda x,y,z: re.search(y, x, z),
  OP_CONTAINS_WORDS:
    lambda x,y,z: all(OP_FUNCS[OP_CONTAINS](x, s, z) for s in y.split()),
}

FIELD_PROP = 0
FIELD_OP = 1
FIELD_CASE = 2
FIELD_QUERY = 3
NUM_FIELDS = 4


#
# props format:
# {
#   "property_name": [property_values],
# }
#
# rules format: [[property, op, case, query],]
#

def find_match(props, rules, match_all=False, use_unicode=True):

  if not rules:
    return False

  for rule in rules:
    values = props[rule[FIELD_PROP]]
    op_func = OP_FUNCS[rule[FIELD_OP]]

    flags = re.UNICODE if use_unicode else 0

    if rule[FIELD_CASE] == CASE_IGNORE:
      flags |= re.IGNORECASE

    query = rule[FIELD_QUERY]

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
