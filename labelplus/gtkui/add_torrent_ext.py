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

import pango
import gtk

import deluge.component

from deluge.ui.client import client

import labelplus.common
import labelplus.common.label

from labelplus.gtkui.label_selection_menu import LabelSelectionMenu


LABEL_ID = 0
LABEL_NAME = 1

log = logging.getLogger(__name__)
log.addFilter(labelplus.common.LOG_FILTER)


class AddTorrentExt(object):

  # Section: Initialization

  def __init__(self, plugin):

    log.debug("Initializing extension...")

    self._plugin = plugin

    self._dialog = deluge.component.get("AddTorrentDialog")
    self._view = self._dialog.listview_torrents

    self._mappings = {}
    self._handlers = []

    self._ext_block = None
    self._ext_label = None
    self._ext_menu = None
    self._build_ext_block()
    self._install_ext_block()

    self._update_sensitivity()
    self._ext_block.show_all()

    self._register_dialog_handlers()

    log.debug("Extension initialized")


  def _build_ext_block(self):

    log.debug("Building widgets...")

    def build_menu():

      def on_activate(widget, label_id):

        id = self._get_selected_id()
        if id:
          self._set_torrent_label(id, label_id)
          self._update_label_text(id)


      item = gtk.MenuItem(_(labelplus.common.label.ID_NONE))
      item.connect("activate", on_activate, labelplus.common.label.ID_NONE)

      items = [item, gtk.SeparatorMenuItem()]

      return LabelSelectionMenu("Select", self._plugin, on_activate, items)


    def on_button_press(widget, event):

      menu.activate()
      menu.get_submenu().popup(None, None, None, event.button, event.time)

      return True


    block = gtk.Frame()
    block.set_shadow_type(gtk.SHADOW_NONE)
    block.set_label_widget(gtk.Label())
    block.get_label_widget().set_markup("<b>%s</b>" %
      labelplus.common.DISPLAY_NAME)

    box_align = gtk.Alignment(0.5, 0.5, 1.0, 1.0)
    box_align.set_padding(5, 0, 5, 5)
    box = gtk.HBox(spacing=3)

    frame = gtk.Frame()
    frame.set_shadow_type(gtk.SHADOW_ETCHED_IN)

    label_align = gtk.Alignment(0.5, 0.5, 1.0, 1.0)
    label_align.set_padding(0, 0, 3, 3)
    label = gtk.Label(_(labelplus.common.label.ID_NONE))
    label.set_alignment(0.0, 0.5)
    label.set_ellipsize(pango.ELLIPSIZE_END)

    menu = build_menu()

    button = gtk.Button(_("Select"))
    button.connect("button-press-event", on_button_press)

    block.add(box_align)
    box_align.add(box)
    box.pack_start(frame, expand=True)
    box.pack_start(button, expand=False)
    frame.add(label_align)
    label_align.add(label)

    self._ext_block = block
    self._ext_label = label
    self._ext_menu = menu


  def _install_ext_block(self):

    log.debug("Adding widgets to Add Torrent dialog...")

    widget = self._dialog.glade.get_widget("button_revert")
    box = widget.get_ancestor(gtk.VBox)

    box.pack_start(self._ext_block, expand=False)
    pos = box.child_get_property(self._ext_block, "position")-1
    box.child_set_property(self._ext_block, "position", pos)


  def _register_dialog_handlers(self):

    log.debug("Registering handlers...")

    self._register_handler(self._view.get_selection(), "changed",
      self._on_selection_changed)

    btn = self._dialog.glade.get_widget("button_revert")
    self._register_handler(btn, "clicked", self._do_revert)

    btn = self._dialog.glade.get_widget("button_apply")
    self._register_handler(btn, "clicked", self._do_apply_to_all)

    btn = self._dialog.glade.get_widget("button_remove")
    self._register_handler(btn, "clicked", self._on_remove_torrent)

    btn = self._dialog.glade.get_widget("button_cancel")
    self._register_handler(btn, "clicked", self._do_clear)

    btn = self._dialog.glade.get_widget("button_add")
    self._register_handler(btn, "clicked", self._on_add_torrent)


  # Section: Deinitialization

  def unload(self):

    log.debug("Deinitializing extension...")

    self._deregister_handlers()
    self._uninstall_ext_block()

    self._ext_menu.destroy()

    del self._ext_menu
    del self._ext_label
    del self._ext_block

    log.debug("Extension deinitialized")


  def _deregister_handlers(self):

    log.debug("Deregistering handlers...")

    for widget, handle in self._handlers:
      widget.disconnect(handle)


  def _uninstall_ext_block(self):

    log.debug("Removing widgets from Add Torrent dialog...")

    box = self._ext_block.get_parent()
    box.remove(self._ext_block)
    self._dialog.dialog.resize(1, 1)


  # Section: General

  def _register_handler(self, obj, signal, func, *args, **kwargs):

    handle = obj.connect(signal, func, *args, **kwargs)
    self._handlers.append((obj, handle))


  def _get_selected_id(self):

    model, row = self._view.get_selection().get_selected()
    if row:
      return model[row][LABEL_ID]

    return None


  # Section: Extension

  def _update_sensitivity(self):

    id = self._get_selected_id()
    self._ext_block.set_sensitive(id is not None)


  def _set_torrent_label(self, torrent_id, label_id):

    log.debug("Setting label for %r to %r", torrent_id, label_id)

    if (label_id != labelplus.common.label.ID_NONE and
        label_id in self._plugin.data):
      name = self._plugin.data[label_id]["fullname"]
      self._mappings[torrent_id] = (label_id, name)
    else:
      if label_id not in self._plugin.data:
        log.debug("Invalid label: %r", label_id)

      if torrent_id in self._mappings:
        del self._mappings[torrent_id]


  def _update_label_text(self, id=None):

    if id and id in self._mappings:
      name = self._mappings[id][LABEL_NAME]
    else:
      name = _(labelplus.common.label.ID_NONE)

    self._ext_label.set_text(name)
    self._ext_label.set_tooltip_text(name)


  # Section: Dialog Handlers

  def _on_selection_changed(self, selection):

    id = self._get_selected_id()
    self._update_label_text(id)
    self._update_sensitivity()


  def _do_revert(self, widget):

    id = self._get_selected_id()
    if id in self._mappings:
      log.debug("Resetting label setting for %r", id)
      del self._mappings[id]
      self._update_label_text(id)


  def _do_apply_to_all(self, widget):

    def set_mapping(model, path, row):

      id = model[row][LABEL_ID]
      self._mappings[id] = mapping


    id = self._get_selected_id()
    if id in self._mappings:
      mapping = self._mappings[id]
    else:
      mapping = (labelplus.common.label.ID_NONE,)

    if mapping[LABEL_ID] == labelplus.common.label.ID_NONE:
      self._mappings.clear()
    else:
      log.debug("Applying label %r to all torrents", mapping[LABEL_ID])
      self._view.get_model().foreach(set_mapping)


  def _on_remove_torrent(self, widget):

    ids = self._dialog.files.keys()
    for key in self._mappings.keys():
      if key not in ids:
        del self._mappings[key]

    id = self._get_selected_id()
    self._update_label_text(id)


  def _do_clear(self, widget):

    self._mappings.clear()
    self._update_label_text()


  def _on_add_torrent(self, widget):

    log.debug("Setting labels on added torrents")

    reverse_map = {}
    for torrent_id, mapping in self._mappings.iteritems():
      label_id = mapping[LABEL_ID]

      if label_id not in reverse_map:
        reverse_map[label_id] = []

      reverse_map[label_id].append(torrent_id)

    for label_id, torrent_ids in reverse_map.iteritems():
      client.labelplus.set_torrent_labels(torrent_ids, label_id)

    self._do_clear(widget)
