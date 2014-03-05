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


import gtk

import labelplus.common.label
import labelplus.gtkui.common

from labelplus.gtkui import RT


class LabelSelectionMenu(gtk.Menu):

  def __init__(self, plugin, on_activate, headers=False, root_items=[],
      base_items=[]):

    super(LabelSelectionMenu, self).__init__()

    self._build_menu(plugin.model, on_activate, headers, root_items,
      base_items)

    self.show_all()


  def _build_menu(self, model, on_activate, headers, root_items, base_items):

    def create_item(iter, menu):

      id, data = model[iter]
      if id in labelplus.common.label.RESERVED_IDS:
        return

      name = data["name"]

      item = gtk.MenuItem(name); RT.register(item, __name__)
      menu.append(item)

      if not model.iter_has_child(iter) and not base_items:
        item.connect("activate", on_activate, id)
      else:
        submenu = gtk.Menu(); RT.register(submenu, __name__)

        if headers:
          labelplus.gtkui.common.menu_add_items(submenu,
            [(name, on_activate)], id)
          labelplus.gtkui.common.menu_add_separator(submenu)

        children = labelplus.gtkui.common.treemodel_get_children(model, iter)

        if base_items:
          labelplus.gtkui.common.menu_add_items(submenu, base_items, id)
          if children:
            labelplus.gtkui.common.menu_add_separator(submenu)

        for child in children:
          create_item(child, submenu)

        item.set_submenu(submenu)


    children = labelplus.gtkui.common.treemodel_get_children(model)

    if root_items:
      labelplus.gtkui.common.menu_add_items(self, root_items,
        labelplus.common.label.ID_NULL)
      if children:
        labelplus.gtkui.common.menu_add_separator(self)

    for child in children:
      create_item(child, self)
