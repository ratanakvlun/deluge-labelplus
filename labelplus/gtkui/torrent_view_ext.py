#
# torrent_view_ext.py
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


import logging

import gtk

import deluge.component

import labelplus.common
import labelplus.common.label


from deluge.ui.client import client

from labelplus.gtkui.label_options_dialog import LabelOptionsDialog
from labelplus.gtkui.label_selection_menu import LabelSelectionMenu


from labelplus.common import (
  DISPLAY_NAME,

  STATUS_NAME, STATUS_ID,
)

from labelplus.common.label import (
  ID_NULL, ID_ALL, ID_NONE, RESERVED_IDS,
)

from labelplus.common.literals import (
  TITLE_SET_FILTER, TITLE_SET_LABEL,

  STR_ALL, STR_NONE, STR_PARENT, STR_SELECTED,
)


log = logging.getLogger(__name__)

from labelplus.gtkui import RT


class TorrentViewExt(object):

  # Section: Initialization

  def __init__(self, plugin):

    self._plugin = plugin
    self._view = deluge.component.get("TorrentView")
    self._menubar = deluge.component.get("MenuBar")

    self._store = None

    self._menu = None
    self._sep = None
    self._submenus = []

    self._alt_menu = None

    self._handlers = []

    try:
      self._store = plugin.store.copy()
      RT.register(self._store, __name__)

      self._add_column()

      self._create_menus()
      self._install_context_menu()

      self._register_handlers()

      self._plugin.register_update_func(self.update_store)
    except:
      self.unload()
      raise


  def _add_column(self):

    def cell_data_func(column, cell, model, row, indices):

      name = model[row][indices[0]]
      id = model[row][indices[1]]

      if id not in RESERVED_IDS and id in self._store:
        if self._plugin.config["common"]["torrent_view_fullname"]:
          name = self._store[id]["fullname"]
        else:
          name = self._store[id]["name"]

      cell.set_property("text", name)


    self._view.add_func_column(DISPLAY_NAME, cell_data_func,
      col_types=[str, str], status_field=[STATUS_NAME, STATUS_ID])

    RT.register(self._get_view_column(), __name__)


  def _create_menus(self):

    self._menu = self._create_context_menu()
    self._submenus = self._create_submenus()
    self._install_submenus()

    self._alt_menu = self._create_alternate_menu()


  def _install_context_menu(self):

    self._sep = self._menubar.add_torrentmenu_separator()
    self._menubar.torrentmenu.append(self._menu)

    RT.register(self._sep, __name__)


  def _register_handlers(self):

    self._register_handler(self._view.treeview, "button-press-event",
      self._on_view_button_press)


  # Section: Deinitialization

  def unload(self):

    self._plugin.deregister_update_func(self.update_store)

    self._deregister_handlers()

    self._uninstall_context_menu()
    self._destroy_menus()

    self._remove_column()


  def _deregister_handlers(self):

    for widget, handle in self._handlers:
      widget.disconnect(handle)


  def _uninstall_context_menu(self):

    if self._menu in self._menubar.torrentmenu:
      self._menubar.torrentmenu.remove(self._menu)

    if self._sep in self._menubar.torrentmenu:
      self._menubar.torrentmenu.remove(self._sep)

    self._sep = None


  def _destroy_menus(self):

    self._destroy_alternate_menu()

    self._submenus = []
    self._destroy_context_menu()


  def _remove_column(self):

    # Workaround for Deluge removing indices in the wrong order
    column = self._view.columns.get(DISPLAY_NAME)
    if column:
      column.column_indices = sorted(column.column_indices, reverse=True)
      self._view.remove_column(DISPLAY_NAME)


  # Section: General

  def _register_handler(self, obj, signal, func, *args, **kwargs):

    handle = obj.connect(signal, func, *args, **kwargs)
    self._handlers.append((obj, handle))


  def _get_view_column(self):

    column = self._view.columns.get(DISPLAY_NAME)
    if column:
      return column.column

    return None


  def _get_selected_torrents_label(self):

    label_id = None
    torrent_ids = self._view.get_selected_torrents()

    if torrent_ids:
      status = self._view.get_torrent_status(torrent_ids[0])
      if STATUS_ID not in status:
        return None

      label_id = status[STATUS_ID] or ID_NONE

      for id in torrent_ids:
        status = self._view.get_torrent_status(id)
        other_label_id = status[STATUS_ID] or ID_NONE

        if other_label_id != label_id:
          return None

    return label_id


  def _get_any_selected_label(self):

    id = self._get_selected_torrents_label()
    if id:
      return id
    else:
      sidebar = self._plugin.get_extension("SidebarExt")
      if sidebar and sidebar.page_selected():
        return sidebar.get_selected_label()

    return None


  def _set_filter(self, id):

    if id in self._store:
      sidebar = self._plugin.get_extension("SidebarExt")
      if sidebar:
        sidebar.select_label(id)
      else:
        if id == ID_ALL:
          filter = {}
        else:
          filter = {STATUS_ID: id}

        log.info("Setting filter to %r", id if id in RESERVED_IDS else
          self._store[id]["fullname"])
        self._view.set_filter(filter)


  def _is_filter(self, id):

    ids = self._view.filter.get(STATUS_ID)

    if ids:
      if isinstance(ids, (list, tuple)):
        if len(ids) == 1 and ids[0] == id:
          return True
      else:
        if ids == id:
          return True

    return False


  def _has_valid_parent(self, id):

    if id and id not in RESERVED_IDS:
      parent_id = labelplus.common.label.get_parent_id(id)
      if parent_id in self._store:
        return True

    return False


  # Section: Update

  def update_store(self, store):

    self._store.destroy()
    self._store = store.copy()
    RT.register(self._store, __name__)

    self._destroy_alternate_menu()
    self._alt_menu = self._create_alternate_menu()

    self._uninstall_submenus()
    self._destroy_submenus()
    self._submenus = self._create_submenus()
    self._install_submenus()


  # Section: Context Menu

  def _create_context_menu(self):

    item = gtk.MenuItem(DISPLAY_NAME)
    item.set_submenu(gtk.Menu())

    RT.register(item, __name__)
    RT.register(item.get_submenu(), __name__)

    return item


  def _destroy_context_menu(self):

    if self._menu:
      self._menu.destroy()
      self._menu = None


  def _create_alternate_menu(self):

    item = self._create_context_menu()
    item.get_submenu().append(self._create_filter_menu())

    menu = gtk.Menu()
    menu.append(item)
    menu.show_all()

    RT.register(menu, __name__)

    return menu


  def _destroy_alternate_menu(self):

    if self._alt_menu:
      self._alt_menu.destroy()
      self._alt_menu = None


  # Section: Context Menu: Submenu

  def _create_submenus(self):

    menus = []
    menus.append(self._create_filter_menu())
    menus.append(self._create_set_label_menu())

    return menus


  def _destroy_submenus(self):

    while self._submenus:
      menu = self._submenus.pop()
      menu.destroy()


  def _install_submenus(self):

    submenu = self._menu.get_submenu()

    for menu in self._submenus:
      submenu.append(menu)

    self._menu.show_all()


  def _uninstall_submenus(self):

    submenu = self._menu.get_submenu()

    for menu in self._submenus:
      if menu in submenu:
        submenu.remove(menu)


  # Section: Context Menu: Submenu: Set Filter

  def _create_filter_menu(self):

    def on_activate(widget, label_id):

      self._set_filter(label_id)


    def on_activate_parent(widget):

      id = self._get_any_selected_label()
      parent_id = labelplus.common.label.get_parent_id(id)
      on_activate(widget, parent_id)


    def on_activate_selected(widget):

      id = self._get_selected_torrents_label()
      on_activate(widget, id)


    def on_show_menu(widget):

      items[0].hide()
      items[1].hide()

      id = self._get_any_selected_label()
      if self._has_valid_parent(id):
        items[0].show()

      id = self._get_selected_torrents_label()
      if id and id not in RESERVED_IDS:
        items[1].show()


    root_items = (
      ((gtk.MenuItem, _(STR_ALL)), on_activate, ID_ALL),
      ((gtk.MenuItem, _(STR_NONE)), on_activate, ID_NONE),
    )

    menu = LabelSelectionMenu(self._store.model, on_activate,
      root_items=root_items)
    menu.connect("show", on_show_menu)

    items = labelplus.gtkui.common.menu_add_items(menu, 2,
      (
        ((gtk.MenuItem, _(STR_PARENT)), on_activate_parent),
        ((gtk.MenuItem, _(STR_SELECTED)), on_activate_selected),
      )
    )

    root = gtk.MenuItem(_(TITLE_SET_FILTER))
    root.set_submenu(menu)

    RT.register(menu, __name__)
    RT.register(root, __name__)

    return root


  # Section: Context Menu: Submenu: Set Label

  def _create_set_label_menu(self):

    def on_activate(widget, label_id):

      torrent_ids = self._view.get_selected_torrents()
      if torrent_ids and label_id in self._store:
        log.info("Setting label for selected torrents to %r", label_id if
          label_id in RESERVED_IDS else self._store[label_id]["fullname"])
        client.labelplus.set_torrent_labels(torrent_ids, label_id)


    def on_activate_parent(widget):

      id = self._get_selected_torrents_label()
      parent_id = labelplus.common.label.get_parent_id(id)
      on_activate(widget, parent_id)


    def on_show_menu(widget):

      items[0].hide()

      id = self._get_selected_torrents_label()
      if self._has_valid_parent(id):
        items[0].show()


    root_items = (((gtk.MenuItem, _(STR_NONE)), on_activate, ID_NONE),)

    menu = LabelSelectionMenu(self._store.model, on_activate,
      root_items=root_items)
    menu.connect("show", on_show_menu)

    items = labelplus.gtkui.common.menu_add_items(menu, 1,
      (((gtk.MenuItem, _(STR_PARENT)), on_activate_parent),))

    root = gtk.MenuItem(_(TITLE_SET_LABEL))
    root.set_submenu(menu)

    RT.register(menu, __name__)
    RT.register(root, __name__)

    return root


  # Section: Deluge Handlers

  def _on_view_button_press(self, widget, event):

    x, y = event.get_coords()
    path_info = widget.get_path_at_pos(int(x), int(y))
    if not path_info:
      if event.button == 3:
        self._alt_menu.popup(None, None, None, event.button, event.time)
      return

    if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
      if path_info[1] == self._get_view_column():
        id = self._get_selected_torrents_label()

        if self._is_filter(id):
          try:
            dialog = LabelOptionsDialog(self._plugin, id)
            dialog.show()
            RT.register(dialog, __name__)
          except:
            pass
        else:
          self._set_filter(id)
