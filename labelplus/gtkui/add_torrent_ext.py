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

from deluge.ui.client import client

import labelplus.common
import labelplus.common.label

from labelplus.gtkui.label_selection_menu import LabelSelectionMenu
from labelplus.gtkui.widget_encapsulator import WidgetEncapsulator

from labelplus.gtkui import RT


LABEL_ID = 0
LABEL_NAME = 1

log = logging.getLogger(__name__)


class AddTorrentExt(WidgetEncapsulator):

  # Section: Initialization

  def __init__(self, plugin):

    log.info("Initializing %s...", self.__class__.__name__)

    super(AddTorrentExt, self).__init__(labelplus.common.get_resource(
      "blk_add_torrent_ext.glade"))

    self._plugin = plugin

    self._dialog = deluge.component.get("AddTorrentDialog")
    self._view = self._dialog.listview_torrents

    self._menu = None
    self._mappings = {}
    self._handlers = []

    self._setup_widgets()
    self._install_widgets()
    self._register_handlers()

    log.info("%s initialized", self.__class__.__name__)


  def _setup_widgets(self):

    log.info("Setting up widgets...")

    def on_click(widget):

      self._menu.popup(None, None, None, 1, gtk.gdk.CURRENT_TIME)


    def on_toggle(widget):

      id = self._get_selected_id()
      self._update_label_text(id)



    self.blk_add_torrent_ext.get_parent().remove(self.blk_add_torrent_ext)
    self.blk_add_torrent_ext.show_all()

    self.blk_add_torrent_ext.get_label_widget().set_markup("<b>%s</b>" %
      labelplus.common.DISPLAY_NAME)

    self.btn_select.connect("clicked", on_click)

    self.tgb_fullname.set_active(
      self._plugin.config["common"]["add_torrent_ext_fullname"])
    self.tgb_fullname.connect("toggled", on_toggle)

    self._update_label_text()
    self._update_sensitivity()


  def _install_widgets(self):

    log.info("Installing widgets...")

    widget = self._dialog.glade.get_widget("button_revert")

    box = widget.get_ancestor(gtk.VBox)
    box.pack_start(self.blk_add_torrent_ext, expand=False)
    box.child_set_property(self.blk_add_torrent_ext, "position",
      box.child_get_property(self.blk_add_torrent_ext, "position")-1)


  def _create_menu(self):

    log.info("Creating menu...")

    def on_activate(widget, label_id):

      id = self._get_selected_id()
      if id:
        self._set_torrent_label(id, label_id)
        self._update_label_text(id)


    item = gtk.MenuItem(_(labelplus.common.label.ID_NONE))
    item.connect("activate", on_activate, labelplus.common.label.ID_NONE)

    items = [item, gtk.SeparatorMenuItem()]

    self._menu = LabelSelectionMenu(self._plugin, on_activate, items)

    self._deinit.append(self._destroy_menu)

    RT.register(items[0], "AddTorrentExt:Menu:'None'")
    RT.register(items[1], "AddTorrentExt:Menu:Separator")
    RT.register(self._menu, "AddTorrentExt:Menu")


  def _register_handlers(self):

    log.info("Registering handlers...")

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


  # Section: Deinitialization

  def unload(self):

    log.info("Deinitializing %s...", self.__class__.__name__)

    self._deregister_handlers()
    self._uninstall_widgets()
    self._destroy_widgets()

    log.info("%s deinitialized", self.__class__.__name__)


  def _deregister_handlers(self):

    log.info("Deregistering handlers...")

    for widget, handle in self._handlers:
      widget.disconnect(handle)


  def _uninstall_widgets(self):

    log.info("Uninstalling widgets...")

    box = self.blk_add_torrent_ext.get_parent()
    box.remove(self.blk_add_torrent_ext)


  def _destroy_widgets(self):

    log.info("Destroying widgets...")

    self.destroy()

    self._menu.destroy()
    del self._menu


  # Section: General

  def _register_handler(self, obj, signal, func, *args, **kwargs):

    handle = obj.connect(signal, func, *args, **kwargs)
    self._handlers.append((obj, handle))


  def _get_selected_id(self):

    model, row = self._view.get_selection().get_selected()
    if row:
      return model[row][0]

    return None


  # Section: Extension Widgets

  def _update_sensitivity(self):

    id = self._get_selected_id()
    self.blk_add_torrent_ext.set_sensitive(id is not None)


  def _update_label_text(self, id=None):

    if id in self._mappings:
      fullname = self._mappings[id][LABEL_NAME]
    else:
      fullname = _(labelplus.common.label.ID_NONE)

    if self.tgb_fullname.get_active():
      self.lbl_name.set_text(fullname)
    else:
      self.lbl_name.set_text(labelplus.common.label.resolve_name_by_degree(
        fullname, degree=1))

    self.lbl_name.set_tooltip_text(fullname)


  def _set_torrent_label(self, torrent_id, label_id):

    assert(torrent_id)

    log.info("Setting label for %r to %r", torrent_id, label_id)

    if (label_id != labelplus.common.label.ID_NONE and
        label_id in self._plugin.data):
      name = self._plugin.data[label_id]["fullname"]
      self._mappings[torrent_id] = (label_id, name)
    else:
      if label_id not in self._plugin.data:
        log.info("Invalid label: %r", label_id)

      if torrent_id in self._mappings:
        del self._mappings[torrent_id]


  def _clear(self):

    self._mappings.clear()
    self._update_label_text()


  # Section: Dialog Handlers

  def _on_selection_changed(self, selection):

    id = self._get_selected_id()
    self._update_label_text(id)
    self._update_sensitivity()


  def _do_revert(self, widget):

    id = self._get_selected_id()
    if id in self._mappings:
      log.info("Resetting label setting for %r", id)
      del self._mappings[id]
      self._update_label_text(id)


  def _do_apply_to_all(self, widget):

    def set_mapping(model, path, row):

      id = model[row][0]
      self._mappings[id] = mapping


    id = self._get_selected_id()
    if id in self._mappings:
      mapping = self._mappings[id]
    else:
      mapping = None

    if mapping is None:
      self._mappings.clear()
    else:
      log.info("Applying label %r to all torrents", mapping[LABEL_ID])
      self._view.get_model().foreach(set_mapping)


  def _on_remove_torrent(self, widget):

    ids = self._dialog.files.keys()
    for key in self._mappings.keys():
      if key not in ids:
        del self._mappings[key]

    id = self._get_selected_id()
    self._update_label_text(id)


  def _on_add_torrent(self, widget):

    log.info("Applying labels to the torrents added")

    reverse_map = {}
    for torrent_id, mapping in self._mappings.iteritems():
      if not self._plugin.is_valid_label(*mapping):
        continue

      label_id = mapping[LABEL_ID]
      if label_id not in reverse_map:
        reverse_map[label_id] = []

      reverse_map[label_id].append(torrent_id)

    for label_id, torrent_ids in reverse_map.iteritems():
      client.labelplus.set_torrent_labels(torrent_ids, label_id)

    self._on_close(widget)


  def _on_close(self, widget):

    self._clear()

    self._plugin.config["common"]["add_torrent_ext_fullname"] = \
      self.tgb_fullname.get_active()
