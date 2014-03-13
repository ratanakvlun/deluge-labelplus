#
# criteria_box.py
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


class CriteriaBox(gtk.VBox):

  def __init__(self, homogeneous=False, row_spacing=0, column_spacing=0):

    def add_new_row(widget):

      self.add_new_row()


    super(CriteriaBox, self).__init__(homogeneous, row_spacing)
    self.connect("destroy", self.destroy)

    self._column_spacing = column_spacing

    self._columns = []
    self._rows = []

    button = gtk.Button("+")
    button.set_size_request(25, -1)
    button.connect("clicked", add_new_row)

    row = gtk.HBox(spacing=self._column_spacing)
    row.pack_end(button, expand=False)

    self._add_button_row = row
    self.pack_start(self._add_button_row, expand=False)


  def destroy(self, *args):

    del self._add_button_row
    del self._rows
    del self._columns

    super(CriteriaBox, self).destroy()


  def set_row_spacing(self, spacing):

    self.set_spacing(spacing)


  def set_column_spacing(self, spacing):

    self._column_spacing = spacing

    for row in self._rows:
      row.set_spacing(spacing)


  def remove(self, widget):

    if widget in self.get_children():
      super(CriteriaBox, self).remove(widget)

    if widget in self._rows:
      self._rows.remove(widget)


  def clear_rows(self):

    for row in list(self._rows):
      self.remove(row)


  def _add_column(self, create_func, create_args, pos, expand):

    if pos is None:
      pos = len(self._columns)

    column_spec = [create_func, create_args, expand]
    self._columns.insert(pos, column_spec)
    pos = self._columns.index(column_spec)

    for row in self._rows:
      child = create_func(*create_args)
      row.pack_start(child, expand)
      row.reorder_child(child, pos)

    return pos


  def move_column(self, index, pos=None):

    if pos is None:
      pos = len(self._columns)-1

    column_spec = self._columns.pop(index)
    self._columns.insert(pos, column_spec)
    pos = self._columns.index(column_spec)

    for row in self._rows:
      child = row.get_children()[index]
      row.reorder_child(child, pos)

    return pos


  def remove_column(self, index):

    self._columns.pop(index)

    for row in self._rows:
      child = row.get_children()[index]
      row.remove(child)


  def add_entry_column(self, default_text="", pos=None, expand=False):

    def create(default_text):

      entry = gtk.Entry()
      entry.set_text(default_text)

      entry._setter = gtk.Entry.set_text
      entry._getter = gtk.Entry.get_text

      return entry

    return self._add_column(create, [default_text], pos, expand)


  def add_combobox_column(self, model, text_column=0, pos=None, expand=False):

    def create(model, text_column):

      combo = gtk.ComboBox(model)
      renderer = gtk.CellRendererText()
      combo.pack_start(renderer)
      combo.add_attribute(renderer, "text", text_column)

      if len(model) > 0:
        combo.set_active(0)

      combo._setter = gtk.ComboBox.set_active
      combo._getter = gtk.ComboBox.get_active

      return combo

    return self._add_column(create, [model, text_column], pos, expand)


  def add_new_row(self, pairs=None):

    def remove_row(widget):

      self.remove(widget.get_parent())


    if pairs:
      indices = pairs[::2]
      values = pairs[1::2]

    row = gtk.HBox(spacing=self._column_spacing)

    for i, column_spec in enumerate(self._columns):
      create_func, create_args, expand = column_spec
      child = create_func(*create_args)
      row.pack_start(child, expand)

      if pairs and i in indices:
        child._setter(child, values[indices.index(i)])

    button = gtk.Button("-")
    button.set_size_request(25, -1)
    button.connect("clicked", remove_row)

    row.pack_end(button, expand=False)
    row.show_all()

    self.add(row)
    self._rows.append(row)
    self.child_set(row, "expand", False)

    self.reorder_child(self._add_button_row, -1)

    return row


  def get_rows(self):

    return list(self._rows)


  def get_row_pairs(self, row):

    pairs = []

    for i in range(len(self._columns)):
      child = row.get_children()[i]
      value = child._getter(child)
      pairs.append(i)
      pairs.append(value)

    return pairs


  def set_row_pairs(self, row, pairs):

    indices = pairs[::2]
    values = pairs[1::2]

    for i in range(len(self._columns)):
      child = row.get_children()[i]

      if i in indices:
        child._setter(child, values[indices.index(i)])


  def get_row_values(self, row):

    values = []

    for i in range(len(self._columns)):
      child = row.get_children()[i]
      value = child._getter(child)
      values.append(value)

    return values


  def set_row_values(self, row, values):

    for i in range(len(self._columns)):
      child = row.get_children()[i]
      child._setter(child, values[i])


  def get_all_row_values(self):

    rows = []

    for row in self._rows:
      rows.append(self.get_row_values(row))

    return rows


  def set_all_row_values(self, rows):

    self.clear_rows()

    for row in rows:
      pairs = [x for pair in zip(range(len(row)), row) for x in pair]
      self.add_new_row(pairs)
