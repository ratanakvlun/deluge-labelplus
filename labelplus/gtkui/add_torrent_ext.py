#
# add_torrent_ext.py
#
# Copyright (C) 2013 Ratanak Lun <ratanakvlun@gmail.com>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#


import pango
import gtk

from deluge import component
from deluge.ui.client import client

from labelplus.common.constant import DISPLAY_NAME
from labelplus.common.constant import RESERVED_IDS
from labelplus.common.constant import ID_NONE

from labelplus.common.debug import debug

from label_selection_menu import LabelSelectionMenu


class AddTorrentExt(object):


  def __init__(self):

    self.mappings = {}
    self.cur_label = None
    self.lv = component.get("AddTorrentDialog").listview_torrents
    self.handlers = []

    self.blk_ext = None
    self.lbl_name = None
    self.btn_select = None

    self._build_ext_block()
    self.blk_ext.show_all()

    self.menu = self._create_selection_menu()
    self.submenu = self.menu.get_submenu()

    self.handlers.append((
      self.lv.get_selection(),
      self.lv.get_selection().connect("changed", self._do_update_label_text),
    ))

    self.btn_select.connect("button-release-event", self._do_show_menu)

    self._install_ext_block()
    self._register_button_handlers()

    self._update_sensitivity()


  def unload(self):

    self._deregister_handlers()
    self.menu.destroy()
    self._uninstall_ext_block()
    self.blk_ext.destroy()


  def _update_sensitivity(self):

    model, row = self.lv.get_selection().get_selected()
    sensitive = row is not None
    self.btn_select.set_sensitive(sensitive)


  def _create_selection_menu(self):

    items = []

    menu_item = gtk.MenuItem(_(ID_NONE))
    menu_item.connect("activate", self._do_set_mapping, ID_NONE)
    items.append(menu_item)

    menu_item = gtk.SeparatorMenuItem()
    items.append(menu_item)

    return LabelSelectionMenu("AddTorrentDialog", self._do_set_mapping, items)


  def _build_ext_block(self):

    self.blk_ext = gtk.Frame()
    self.blk_ext.set_shadow_type(gtk.SHADOW_NONE)
    self.blk_ext.set_label_widget(gtk.Label())
    self.blk_ext.get_label_widget().set_markup("<b>%s</b>" % DISPLAY_NAME)

    blk_align = gtk.Alignment(0.5, 0.5, 1.0, 1.0)
    blk_align.set_padding(5, 0, 5, 5)

    box = gtk.HBox()
    box.set_spacing(3)

    frame = gtk.Frame()
    frame.set_shadow_type(gtk.SHADOW_ETCHED_IN)

    align = gtk.Alignment(0.5, 0.5, 1.0, 1.0)
    align.set_padding(0, 0, 3, 3)

    self.lbl_name = gtk.Label()
    self.lbl_name.set_alignment(0.0, 0.5)
    self.lbl_name.set_ellipsize(pango.ELLIPSIZE_END)
    self.lbl_name.set_text(_(ID_NONE))

    self.btn_select = gtk.Button()
    self.btn_select.set_label(_("Select"))

    self.blk_ext.add(blk_align)
    blk_align.add(box)
    box.pack_start(frame, expand=True)
    frame.add(align)
    align.add(self.lbl_name)
    box.pack_start(self.btn_select, expand=False)


  @debug()
  def _install_ext_block(self):

    dialog = component.get("AddTorrentDialog")
    widget = dialog.glade.get_widget("button_revert")
    vbox = widget.get_ancestor(gtk.VBox())

    vbox.pack_start(self.blk_ext, expand=False)
    pos = vbox.child_get(self.blk_ext, "position")[0] - 1
    vbox.child_set(self.blk_ext, "position", pos)


  @debug()
  def _uninstall_ext_block(self):

    dialog = component.get("AddTorrentDialog")
    widget = dialog.glade.get_widget("button_revert")
    vbox = widget.get_ancestor(gtk.VBox())

    vbox.remove(self.blk_ext)
    dialog.dialog.resize(1, 1)


  @debug(show_args=True)
  def _do_set_mapping(self, widget, label_id):

    self.cur_label = None

    model, row = self.lv.get_selection().get_selected()
    if row:
      id = model.get_value(row, 0)
      if not label_id or label_id in RESERVED_IDS:
        if id in self.mappings:
          del self.mappings[id]
      else:
        name = [widget.get_label()]

        parent = widget.get_parent()
        while parent is not self.submenu:
          item = parent.get_attach_widget()
          name.append(item.get_label())
          parent = item.get_parent()

        if len(name) > len(label_id.split(":"))-1:
          name.pop(0)

        self.mappings[id] = (label_id, "/".join(reversed(name)))
        self.cur_label = self.mappings[id]

    self._do_update_label_text(self.lv.get_selection())


  def _do_update_label_text(self, selection):

    self.cur_label = None

    model, row = selection.get_selected()
    if row:
      id = model.get_value(row, 0)
      if id in self.mappings:
        self.lbl_name.set_text(self.mappings[id][1])
        self.lbl_name.set_tooltip_text(self.mappings[id][1])

        self.cur_label = self.mappings[id]
        return

    self.lbl_name.set_text(_(ID_NONE))
    self.lbl_name.set_tooltip_text(None)

    self._update_sensitivity()


  def _do_show_menu(self, widget, event):

    self.menu.on_activate(self.menu)
    self.submenu.popup(None, None, None, event.button, event.time)


  def _register_button_handlers(self):

    dialog = component.get("AddTorrentDialog")

    btn = dialog.glade.get_widget("button_revert")
    self.handlers.append((btn, btn.connect("clicked", self._do_revert)))

    btn = dialog.glade.get_widget("button_apply")
    self.handlers.append((btn, btn.connect("clicked", self._do_apply_to_all)))

    btn = dialog.glade.get_widget("button_cancel")
    self.handlers.append((btn, btn.connect("clicked", self._do_clear)))

    btn = dialog.glade.get_widget("button_remove")
    self.handlers.append((btn, btn.connect("clicked", self._do_remove)))

    btn = dialog.glade.get_widget("button_add")
    self.handlers.append((btn, btn.connect("clicked", self._do_add)))


  def _deregister_handlers(self):

    for widget, handler in self.handlers:
      widget.disconnect(handler)


  @debug()
  def _do_revert(self, widget):

    self._do_set_mapping(None, None)


  @debug()
  def _do_apply_to_all(self, widget):


    def set_mapping(model, path, row):

      id = model.get_value(row, 0)
      self.mappings[id] = self.cur_label


    if self.cur_label is None:
      self.mappings.clear()
    else:
      self.lv.get_model().foreach(set_mapping)

    self._do_update_label_text(self.lv.get_selection())


  @debug()
  def _do_clear(self, widget):

    self.mappings.clear()
    self._do_update_label_text(self.lv.get_selection())


  @debug()
  def _do_remove(self, widget):

    dialog = component.get("AddTorrentDialog")

    ids = dialog.files.keys()
    for key in self.mappings.keys():
      if key not in ids:
        del self.mappings[key]

    self._do_update_label_text(self.lv.get_selection())


  @debug()
  def _do_add(self, widget):

    reverse_map = {}
    for torrent_id, label_tup in self.mappings.iteritems():
      label_id = label_tup[0]
      if label_id not in reverse_map:
        reverse_map[label_id] = []

      reverse_map[label_id].append(torrent_id)

    for label_id, torrent_ids in reverse_map.iteritems():
      client.labelplus.set_torrent_labels(label_id, torrent_ids)

    self._do_clear(widget)
