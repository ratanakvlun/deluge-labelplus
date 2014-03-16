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

from labelplus.gtkui.label_selection_menu import LabelSelectionMenu
from labelplus.gtkui.label_options_dialog import LabelOptionsDialog


log = logging.getLogger(__name__)

from labelplus.gtkui import RT


class TorrentViewExt(object):

  # Section: Initialization

  def __init__(self, plugin):

    log.debug("Initializing TorrentViewExt...")

    try:
      self._plugin = plugin

      self._view = deluge.component.get("TorrentView")
      self._handlers = []

      self._add_column()
      self._add_context_menus()

      self._register_handlers()

      log.debug("TorrentViewExt initialized")
    except:
      log.debug("Error initializing TorrentViewExt")
      raise


  def _add_column(self):

    def cell_data_func(column, cell, model, row, indices):

      id = model[row][indices[1]]
      name = model[row][indices[0]]
      cell.set_property("text", name)


    log.debug("Adding column...")

    self._view.add_func_column(labelplus.common.DISPLAY_NAME,
      cell_data_func, col_types=[str, str],
      status_field=[labelplus.common.STATUS_NAME, labelplus.common.STATUS_ID])


  def _add_context_menus(self):

    log.debug("Adding context menus...")

    menubar = deluge.component.get("MenuBar")

    self._sep = menubar.add_torrentmenu_separator()
    self._menu = self._create_torrent_menu()
    menubar.torrentmenu.append(self._menu)

    RT.register(self._sep, "context separator")
    RT.register(self._menu, "context menu")

    self._alt_menu = self._create_alternate_menu()


  def _register_handlers(self):

    log.debug("Registering handlers...")

    self._register_handler(self._view.treeview, "button-press-event",
      self._on_view_button_press)


  # Section: Deinitialization

  def unload(self):

    log.debug("Deinitializing TorrentViewExt...")

    try:
      self._deregister_handlers()

      self._remove_context_menus()
      self._remove_column()

      log.debug("TorrentViewExt deinitialized")
    except:
      log.debug("Error deinitializing TorrentViewExt")
      raise


  def _deregister_handlers(self):

    log.debug("Deregistering handlers...")

    for widget, handle in self._handlers:
      widget.disconnect(handle)


  def _remove_context_menus(self):

    log.debug("Removing context menus...")

    menubar = deluge.component.get("MenuBar")

    menubar.torrentmenu.remove(self._menu)
    menubar.torrentmenu.remove(self._sep)

    self._menu.destroy()

    del self._menu
    del self._sep
    del self._alt_menu


  def _remove_column(self):

    log.debug("Removing column...")

    # Workaround for Deluge 1.3.6 bug
    column = self._view.columns[labelplus.common.DISPLAY_NAME]
    column.column_indices = sorted(column.column_indices, reverse=True)

    self._view.remove_column(labelplus.common.DISPLAY_NAME)


  # Section: General

  def _register_handler(self, obj, signal, func, *args, **kwargs):

    handle = obj.connect(signal, func, *args, **kwargs)
    self._handlers.append((obj, handle))


  def _get_selected_torrents_label(self):

    torrent_ids = self._view.get_selected_torrents()
    label_id = None

    if len(torrent_ids) > 0:
      status = self._view.get_torrent_status(torrent_ids[0])
      if labelplus.common.STATUS_ID not in status:
        return None

      label_id = status[labelplus.common.STATUS_ID] or \
        labelplus.common.label.ID_NONE

      for id in torrent_ids:
        status = self._view.get_torrent_status(id)
        other_label_id = status[labelplus.common.STATUS_ID] or \
          labelplus.common.label.ID_NONE

        if other_label_id != label_id:
          return None

    return label_id


  def _get_view_column(self):

    return self._view.columns[labelplus.common.DISPLAY_NAME].column


  # Section: Torrent View: Handlers

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
        log.debug("doubleclick on %r", id)
        log.debug("filter %r", self._view.filter)
        return
        sidebar = self._plugin.get_extension("SidebarExt")
        if sidebar:
          if sidebar.page_selected() and sidebar.get_selected_label() == id:
            log.debug("Open label options")
            #self._do_open_label_options(widget, event)
        else:
          log.debug("Set label filter")
          #self._do_go_to_label(widget)


  # Section: Torrent View: Context Menu

  def _create_torrent_menu(self):

    def on_open_menu(widget):

      id = self._get_selected_torrents_label()
      if (id != labelplus.common.label.ID_NONE and
          id in self._plugin.data):
        label_options_item.show()
      else:
        label_options_item.hide()


    jump_menu = self._create_jump_menu()
    set_label_menu = self._create_set_label_menu()
    label_options_item = self._create_label_options_item()

    menu = gtk.MenuItem(labelplus.common.DISPLAY_NAME)
    menu.connect("activate", on_open_menu)

    menu.set_submenu(gtk.Menu())
    menu.get_submenu().append(jump_menu)
    menu.get_submenu().append(set_label_menu)
    menu.get_submenu().append(label_options_item)

    menu.show_all()

    RT.register(jump_menu, "jump menu")
    RT.register(set_label_menu, "set menu")
    RT.register(label_options_item, "optionsitem")
    RT.register(menu, "context menu raw")
    RT.register(menu.get_submenu(), "context menu submenu")

    return menu


  def _create_alternate_menu(self):

    item = gtk.MenuItem(labelplus.common.DISPLAY_NAME)
    item.set_submenu(gtk.Menu())
    item.get_submenu().append(self._create_jump_menu())

    menu = gtk.Menu()
    menu.append(item)

    menu.show_all()

    RT.register(item, "alt item")
    RT.register(item.get_submenu(), "alt item submenu")
    RT.register(menu, "alt menu")

    return menu


  # Section: Torrent View: Context Menu: Jump

  def _create_jump_menu(self):

    def on_select_label(widget, label_id):

      self._do_go_to_label(widget, label_id)


    def on_event(widget):

      log.debug("ON SHOW")


    def on_open_menu(widget):

      log.debug("ON OPEN MENU")
      selected_item.hide()
      parent_item.hide()

      id = self._get_selected_torrents_label()
      if id:
        if getattr(selected_item, "handle", None):
          selected_item.disconnect(selected_item.handle)

        handle = selected_item.connect("activate", on_select_label, id)
        selected_item.handle = handle
        selected_item.show()
      else:
        sidebar = self._plugin.get_extension("SidebarExt")
        if sidebar:
          if sidebar.page_selected():
            id = sidebar.get_selected_label()

      if id:
        parent_id = labelplus.common.label.get_parent_id(id)
        if parent_id in self._plugin.data:
          if getattr(parent_item, "handle", None):
            parent_item.disconnect(parent_item.handle)

          handle = parent_item.connect("activate", on_select_label, parent_id)
          parent_item.handle = handle
          parent_item.show()


    all_item = gtk.MenuItem(_(labelplus.common.label.ID_ALL))
    all_item.connect("activate", on_select_label,
      labelplus.common.label.ID_ALL)

    none_item = gtk.MenuItem(_(labelplus.common.label.ID_NONE))
    none_item.connect("activate", on_select_label,
      labelplus.common.label.ID_NONE)

    selected_item = gtk.MenuItem(_("Selected"))
    parent_item = gtk.MenuItem(_("Parent"))
    sep = gtk.SeparatorMenuItem()

    items = [all_item, none_item, selected_item, parent_item, sep]

    menu = LabelSelectionMenu(_("Jump To"), self._plugin,
      on_select_label, items)
    menu.connect("activate", on_open_menu)
    menu.get_submenu().connect("show", on_event)

    RT.register(all_item, "jump all")
    RT.register(none_item, "jump none")
    RT.register(selected_item, "jump selected")
    RT.register(parent_item, "jump parent")
    RT.register(sep, "jump sep")
    RT.register(menu, "jump menu")
    RT.register(menu.get_submenu(), "jump submenu")
    return menu


  def _do_go_to_label(self, widget, id=None):

    if not id:
      id = self._get_selected_torrents_label()

    log.debug("should set filter to %r", id)
    return
    if id is not None:
      self.label_sidebar.select_label(id)


  # Section: Torrent View: Context Menu: Set Label

  def _create_set_label_menu(self):

    def on_select_label(widget, label_id):

      torrent_ids = self._view.get_selected_torrents()
      if torrent_ids:
        log.debug("Setting label for selected torrents to %r", label_id)
        client.labelplus.set_torrent_labels(torrent_ids, label_id)


    def on_open_menu(widget):

      parent_item.hide()

      id = self._get_selected_torrents_label()
      if id:
        parent_id = labelplus.common.label.get_parent_id(id)
        if parent_id in self._plugin.data:
          if getattr(parent_item, "handle", None):
            parent_item.disconnect(parent_item.handle)

          handle = parent_item.connect("activate", on_select_label, parent_id)
          parent_item.handle = handle
          parent_item.show()


    none_item = gtk.MenuItem(_(labelplus.common.label.ID_NONE))
    none_item.connect("activate", on_select_label,
      labelplus.common.label.ID_NONE)

    parent_item = gtk.MenuItem(_("Parent"))
    sep = gtk.SeparatorMenuItem()

    items = [none_item, parent_item, sep]

    menu = LabelSelectionMenu(_("Set Label"), self._plugin,
      on_select_label, items)
    menu.connect("activate", on_open_menu)

    RT.register(none_item, "set none")
    RT.register(parent_item, "set parent")
    RT.register(sep, "set sep")
    RT.register(menu, "set menu")
    RT.register(menu.get_submenu(), "set submenu")
    return menu


  # Section: Torrent View: Context Menu: Label Options

  def _create_label_options_item(self):

    def on_activate(widget):

      id = self._get_selected_torrents_label()
      if (id != labelplus.common.label.ID_NONE and
          id in self._plugin.data):
        log.debug("Opening label options dialog for %r", id)
        LabelOptionsDialog(self._plugin, id)


    item = gtk.MenuItem(_("Label Options"))
    item.connect("activate", on_activate)

    RT.register(item, "label options item")

    return item
