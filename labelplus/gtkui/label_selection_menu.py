#
# label_selection_menu.py
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


import datetime

import gtk

import labelplus.common
import labelplus.common.label

import labelplus.gtkui.util


class LabelSelectionMenu(gtk.MenuItem):

  def __init__(self, label, plugin, select_func, base_items=[]):

    super(LabelSelectionMenu, self).__init__(label)

    self._plugin = plugin
    self._select_func = select_func
    self._base_items = base_items

    self._last_updated = labelplus.common.DATETIME_010101

    self.set_submenu(gtk.Menu())
    self.connect("activate", self._on_activate)


  def _on_activate(self, widget):

    if self._last_updated <= self._plugin.last_updated:
      self._clear_menu()
      self._build_menu(self._plugin.store)
      self.show_all()

      self._last_updated = datetime.datetime.now()


  def _clear_menu(self):

    for item in list(self.get_submenu().get_children()):
      self.get_submenu().remove(item)


  def _build_menu(self, model):

    def create_item(model, row, menus):

      if row:
        id, data = model[row]

        if id in labelplus.common.label.RESERVED_IDS:
          return

        name = data["name"]

        item = gtk.MenuItem(name)
        menus[-1].append(item)

        if not model.iter_has_child(row):
          item.connect("activate", self._select_func, id)
        else:
          sub_item = gtk.MenuItem(name)
          sub_item.connect("activate", self._select_func, id)

          item.set_submenu(gtk.Menu())
          item.get_submenu().append(sub_item)
          item.get_submenu().append(gtk.SeparatorMenuItem())

          # Push the menu to be appended by children
          menus.append(item.get_submenu())


    def pop_menu(model, row, menus):

      if row and model.iter_has_child(row):
        menus.pop()


    for item in self._base_items:
      self.get_submenu().append(item)

    labelplus.gtkui.util.treemodel_recurse(model, None, create_item,
      pop_menu, menus=[self.get_submenu()])
