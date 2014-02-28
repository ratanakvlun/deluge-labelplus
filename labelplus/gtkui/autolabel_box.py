#
# autolabel_box.py
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


import gtk

import labelplus.common.config.autolabel

from labelplus.gtkui.criteria_box import CriteriaBox


def build_store(values):

  ls = gtk.ListStore(str)

  for value in values:
    ls.append([value])

  return ls


class AutolabelBox(CriteriaBox):

  def __init__(self, homogeneous=False, row_spacing=0, column_spacing=0):

    super(AutolabelBox, self).__init__(homogeneous, row_spacing,
      column_spacing)

    prop_store = build_store(labelplus.common.config.autolabel.PROPS)
    op_store = build_store(labelplus.common.config.autolabel.OPS)
    cases_store = build_store(labelplus.common.config.autolabel.CASES)

    self.add_combobox_column(prop_store)
    self.add_combobox_column(op_store)
    self.add_combobox_column(cases_store)
    self.add_entry_column(expand=True)

    # Determine minimum width
    row = self.add_new_row()
    self.show()
    size = self.size_request()
    self.remove(row)
    self.set_size_request(size[0], -1)


  def get_all_row_values(self):

    rows = super(AutolabelBox, self).get_all_row_values()

    for row in rows:
      row[labelplus.common.config.autolabel.FIELD_PROP] = \
        labelplus.common.config.autolabel.PROPS[
          row[labelplus.common.config.autolabel.FIELD_PROP]]

      row[labelplus.common.config.autolabel.FIELD_OP] = \
        labelplus.common.config.autolabel.OPS[
          row[labelplus.common.config.autolabel.FIELD_OP]]

      row[labelplus.common.config.autolabel.FIELD_CASE] = \
        labelplus.common.config.autolabel.CASES[
          row[labelplus.common.config.autolabel.FIELD_CASE]]

    return rows


  def set_all_row_values(self, rows):

    converted_rows = []

    for row in rows:
      row = list(row)

      row[labelplus.common.config.autolabel.FIELD_PROP] = \
        labelplus.common.config.autolabel.PROPS.index(
          row[labelplus.common.config.autolabel.FIELD_PROP])

      row[labelplus.common.config.autolabel.FIELD_OP] = \
        labelplus.common.config.autolabel.OPS.index(
          row[labelplus.common.config.autolabel.FIELD_OP])

      row[labelplus.common.config.autolabel.FIELD_CASE] = \
        labelplus.common.config.autolabel.CASES.index(
          row[labelplus.common.config.autolabel.FIELD_CASE])

      converted_rows.append(row)

    super(AutolabelBox, self).set_all_row_values(converted_rows)
