#
# add_torrent_ext.py
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

from labelplus.common import LabelPlusError

from labelplus.gtkui.common.widgets.label_selection_menu import (
  LabelSelectionMenu)

from labelplus.gtkui.common.gtklib.widget_encapsulator import (
  WidgetEncapsulator)

from labelplus.gtkui import RT


from labelplus.common.label import (
  ID_NONE, RESERVED_IDS,
)

from labelplus.common.literals import (
  STR_NONE,
  ERR_INVALID_LABEL,
)


log = logging.getLogger(__name__)


class AddTorrentExt(WidgetEncapsulator):

  # Section: Constants

  GLADE_FILE = labelplus.common.get_resource("blk_add_torrent_ext.glade")
  ROOT_WIDGET = "blk_add_torrent_ext"

  TORRENT_ID = 0


  # Section: Initialization

  def __init__(self, plugin):

    self._plugin = plugin
    self._dialog = deluge.component.get("AddTorrentDialog")
    self._view = self._dialog.listview_torrents

    self._store = None
    self._menu = None

    self._mappings = {}
    self._handlers = []

    super(AddTorrentExt, self).__init__(self.GLADE_FILE, self.ROOT_WIDGET, "_")

    try:
      self._store = plugin.store.copy()
      if __debug__: RT.register(self._store, __name__)

      self._setup_widgets()
      self._install_widgets()
      self._register_handlers()

      self._create_menu()

      self._display_torrent_label(None)
      self._update_sensitivity()

      self._plugin.register_update_func(self.update_store)
    except:
      self.unload()
      raise


  def _setup_widgets(self):

    def on_click(widget):

      if self._menu:
        self._menu.popup(None, None, None, 1, gtk.gdk.CURRENT_TIME)


    def on_toggle(widget):

      self._refresh_torrent_label()


    self._blk_add_torrent_ext.get_label_widget().set_markup("<b>%s</b>" %
      labelplus.common.DISPLAY_NAME)

    self._btn_select.connect("clicked", on_click)
    self._tgb_fullname.connect("toggled", on_toggle)

    self._load_state()


  def _install_widgets(self):

    widget = self._dialog.glade.get_widget("button_revert")

    box = widget.get_ancestor(gtk.VBox)
    box.pack_start(self._blk_add_torrent_ext, expand=False)

    box.child_set_property(self._blk_add_torrent_ext, "position",
      box.child_get_property(self._blk_add_torrent_ext, "position")-1)


  def _register_handlers(self):

    self._register_handler(self._view.get_selection(), "changed",
      self._on_selection_changed)

    self._register_handler(self._dialog.glade.get_widget("button_revert"),
      "clicked", self._do_revert)

    self._register_handler(self._dialog.glade.get_widget("button_apply"),
      "clicked", self._do_apply_to_all)

    self._register_handler(self._dialog.glade.get_widget("button_remove"),
      "clicked", self._on_remove_torrent)

    self._register_handler(self._dialog.glade.get_widget("button_cancel"),
      "clicked", self._on_close)

    self._register_handler(self._dialog.glade.get_widget("button_add"),
      "clicked", self._on_add_torrent)


  def _create_menu(self):

    def on_activate(widget, label_id):

      id = self._get_selected_torrent()
      if id:
        self._set_torrent_label(id, label_id)
        self._display_torrent_label(id)


    items = (((gtk.MenuItem, _(STR_NONE)), on_activate, ID_NONE),)

    self._menu = LabelSelectionMenu(self._store.model, on_activate,
      root_items=items)

    if __debug__: RT.register(self._menu, __name__)


  # Section: Deinitialization

  def unload(self):

    self._plugin.deregister_update_func(self.update_store)

    self._deregister_handlers()
    self._uninstall_widgets()

    self._destroy_menu()
    self._destroy_store()

    super(AddTorrentExt, self).destroy()


  def _deregister_handlers(self):

    for widget, handle in self._handlers:
      widget.disconnect(handle)


  def _uninstall_widgets(self):

    box = self._blk_add_torrent_ext.get_parent()
    if box:
      box.remove(self._blk_add_torrent_ext)


  def _destroy_menu(self):

    if self._menu:
      self._menu.destroy()
      self._menu = None


  def _destroy_store(self):

    if self._store:
      self._store.destroy()
      self._store = None


  # Section: General

  def _register_handler(self, obj, signal, func, *args, **kwargs):

    handle = obj.connect(signal, func, *args, **kwargs)
    self._handlers.append((obj, handle))


  def _get_selected_torrent(self):

    model, row = self._view.get_selection().get_selected()
    if row:
      return model[row][self.TORRENT_ID]

    return None


  # Section: Update

  def update_store(self, store):

    self._store.destroy()
    self._store = store.copy()
    if __debug__: RT.register(self._store, __name__)

    self._destroy_menu()
    self._create_menu()

    self._refresh_torrent_label()


  # Section: Widget State

  def _load_state(self):

    if self._plugin.initialized:
      self._tgb_fullname.set_active(
        self._plugin.config["common"]["add_torrent_ext_fullname"])


  def _save_state(self):

    if self._plugin.initialized:
      self._plugin.config["common"]["add_torrent_ext_fullname"] = \
        self._tgb_fullname.get_active()

      self._plugin.config.save()


  # Section: Widget Modifiers

  def _update_sensitivity(self):

    id = self._get_selected_torrent()
    self._blk_add_torrent_ext.set_sensitive(id is not None)


  def _display_torrent_label(self, id):

    if id in self._mappings:
      label_id = self._mappings[id]
    else:
      label_id = None

    if label_id in self._store:
      name = self._store[label_id]["name"]
      fullname = self._store[label_id]["fullname"]
    else:
      name = _(STR_NONE)
      fullname = _(STR_NONE)

    if self._tgb_fullname.get_active():
      self._lbl_name.set_text(fullname)
    else:
      self._lbl_name.set_text(name)

    if label_id:
      self._lbl_name.set_tooltip_text(fullname)
    else:
      self._lbl_name.set_tooltip_text(None)


  def _refresh_torrent_label(self):

    id = self._get_selected_torrent()
    self._display_torrent_label(id)


  def _set_torrent_label(self, torrent_id, label_id):

    if label_id not in RESERVED_IDS and label_id in self._store:
      log.info("Setting label for %s to %r", torrent_id,
        self._store[label_id]["fullname"])
      self._mappings[torrent_id] = label_id
    else:
      log.info("Removing label from %s", torrent_id)

      if label_id not in self._store:
        log.error("%s", LabelPlusError(ERR_INVALID_LABEL))

      if torrent_id in self._mappings:
        del self._mappings[torrent_id]


  def _clear(self):

    self._mappings.clear()
    self._display_torrent_label(None)


  # Section: Deluge Handlers

  def _on_selection_changed(self, selection):

    self._refresh_torrent_label()
    self._update_sensitivity()


  def _do_revert(self, widget):

    id = self._get_selected_torrent()
    if id in self._mappings:
      log.info("Resetting label setting on %s", id)
      del self._mappings[id]
      self._display_torrent_label(None)


  def _do_apply_to_all(self, widget):

    def set_mapping(model, path, row):

      id = model[row][self.TORRENT_ID]
      self._mappings[id] = label_id


    id = self._get_selected_torrent()
    if id in self._mappings:
      label_id = self._mappings[id]
      log.info("Applying label %r to all torrents",
        self._store[label_id]["fullname"])
      self._view.get_model().foreach(set_mapping)
    else:
      self._mappings.clear()


  def _on_remove_torrent(self, widget):

    ids = self._dialog.files.keys()
    for key in self._mappings.keys():
      if key not in ids:
        del self._mappings[key]

    self._refresh_torrent_label()


  def _on_add_torrent(self, widget):

    log.info("Applying labels to the torrents added")

    reverse_map = {}
    for torrent_id, label_id in self._mappings.iteritems():
      if label_id in RESERVED_IDS or label_id not in self._store:
        continue

      if label_id not in reverse_map:
        reverse_map[label_id] = []

      reverse_map[label_id].append(torrent_id)

    for label_id, torrent_ids in reverse_map.iteritems():
      client.labelplus.set_torrent_labels(torrent_ids, label_id)

    self._on_close(widget)


  def _on_close(self, widget):

    self._save_state()
    self._clear()
