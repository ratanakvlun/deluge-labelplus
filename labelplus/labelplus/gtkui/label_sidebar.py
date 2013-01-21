#
# label_sidebar.py
#
# Copyright (C) 2013 Ratanak Lun <ratanakvlun@gmail.com>
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
# Copyright (C) 2007 Andrew Resch <andrewresch@gmail.com>
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


import gtk

from deluge import component
from deluge.log import LOG as log
from deluge.ui.client import client
import deluge.configmanager

from labelplus.common.constant import PLUGIN_NAME, DISPLAY_NAME
from labelplus.common.constant import RESERVED_IDS
from labelplus.common.constant import NULL_PARENT, ID_ALL, ID_NONE
from labelplus.common.constant import STATUS_ID
from labelplus.common.constant import GTKUI_CONFIG

import labelplus.common.label as Label
from labelplus.common.debug import debug
from labelplus.common.validation import require

from util import treemodel_subtree_op
from name_input_dialog import NameInputDialog
from label_options_dialog import LabelOptionsDialog


class LabelSidebarMenu(gtk.Menu):


  LEVEL1 = 0
  LEVEL2 = 50
  LEVEL3 = 100


  def __init__(self, owner):

    super(LabelSidebarMenu, self).__init__()

    self._owner = owner
    self._items = []
    self.target_id = None
    self.dialog = None

    self._add_item(
        "add", _("_Add Label"), gtk.STOCK_ADD, self.LEVEL1)

    self.append(gtk.SeparatorMenuItem())
    self._add_item(
        "sublabel", _("Add Sub_Label"), gtk.STOCK_ADD, self.LEVEL3)
    self._add_item("rename", _("Re_name Label"), gtk.STOCK_EDIT, self.LEVEL3)
    self._add_item(
        "remove", _("_Remove Label"), gtk.STOCK_REMOVE, self.LEVEL3)

    self.append(gtk.SeparatorMenuItem())
    self._add_item(
        "options", _("Label _Options"), gtk.STOCK_PREFERENCES, self.LEVEL3)

    self.append(gtk.SeparatorMenuItem())
    self._add_item(
        "select_all", _("_Select All"), gtk.STOCK_SELECT_ALL, self.LEVEL2)
    self._add_item(
        "pause_all", _("_Pause All"), gtk.STOCK_MEDIA_PAUSE, self.LEVEL2)
    self._add_item(
        "resume_all", _("Resu_me All"), gtk.STOCK_MEDIA_PLAY, self.LEVEL2)


  def set_sensitivity(self, level):

    for item, sensitivity in self._items:
      item.set_sensitive(sensitivity <= level)


  def _add_item(self, id, label, stock, level):

    item = gtk.ImageMenuItem(stock)
    item.get_children()[0].set_label(label)

    func = getattr(self, "on_%s" % id)
    item.connect("activate", func)

    self._items.append((item, level))
    self.append(item)


  @debug()
  def on_add(self, widget):

    self.dialog = NameInputDialog("add")


  @debug()
  def on_remove(self, widget):

    if self.target_id not in RESERVED_IDS:
      self._owner._remove_label_subtree(self.target_id)


  @debug()
  def on_options(self, widget):

    if self.target_id not in RESERVED_IDS:
      name = self._owner._get_label_name(self.target_id)
      self.dialog = LabelOptionsDialog(self.target_id, name)


  @debug()
  def on_sublabel(self, widget):

    if self.target_id not in RESERVED_IDS:
      name = self._owner._get_label_name(self.target_id)
      self.dialog = NameInputDialog("sublabel", self.target_id, name)


  @debug()
  def on_rename(self, widget):

    if self.target_id not in RESERVED_IDS:
      name = self._owner._get_label_name(self.target_id)
      self.dialog = NameInputDialog("rename", self.target_id, name)


  @debug()
  def on_select_all(self, widget):

    component.get("FilterTreeView").on_select_all(widget)


  @debug()
  def on_pause_all(self, widget):

    component.get("FilterTreeView").on_pause_all(widget)


  @debug()
  def on_resume_all(self, widget):

    component.get("FilterTreeView").on_resume_all(widget)


class LabelSidebar(object):


  def __init__(self):

    self.config = deluge.configmanager.ConfigManager(GTKUI_CONFIG)
    self.state = self.config["sidebar_state"]

    self.label_tree = self._build_label_tree()
    self.menu = LabelSidebarMenu(self)
    self.store = gtk.TreeStore(str, str, int)

    self.sorted_store = gtk.TreeModelSort(self.store)
    self.sorted_store.set_default_sort_func(lambda *args: 0)
    self.sorted_store.set_sort_func(1, self._label_sort_asc)

    self.filter_path = None
    self.external_handlers = []

    root = self.store.append(None, [NULL_PARENT, DISPLAY_NAME, 0])
    self.row_map = {
      NULL_PARENT: root,
    }

    self._install_label_tree()
    self._loaded = True

    client.labelplus.get_label_counts().addCallback(self.cb_complete_init)


  @debug()
  def unload(self):

    self._loaded = False

    self.config.save()

    filter = component.get("TorrentView").filter
    if filter and filter.get(STATUS_ID) is not None:
      component.get("TorrentView").set_filter({})

    self._uninstall_label_tree()

    self.sorted_store.clear_cache()
    self.store.clear()

    self.menu.destroy()
    del self.menu

    self.label_tree.destroy()
    del self.label_tree


  def update_counts(self):

    client.labelplus.get_label_counts().addCallback(
        self.cb_get_label_counts_ok)


  @debug()
  def cb_complete_init(self, counts):

    require(self._loaded, "Plugin not loaded")

    self.cb_get_label_counts_ok(counts)

    self.label_tree.set_model(self.sorted_store)
    self._load_tree_state()

    self.label_tree.set_cursor(self.filter_path)

    self.label_tree.get_selection().connect(
        "changed", self.on_selection_changed)

    self.label_tree.connect("button-press-event", self.on_button_pressed)
    self.label_tree.connect("button-release-event", self.on_button_released)
    self.label_tree.connect("row-collapsed", self.on_row_collapsed)
    self.label_tree.connect("cursor-changed", self.on_cursor_changed)
    self.label_tree.connect("focus-in-event", self.on_focus_in)

    self.label_tree.show_all()
    self.menu.show_all()


  def cb_get_label_counts_ok(self, counts):

    require(self._loaded, "Plugin not loaded")

    counts[ID_ALL]["name"] = _(ID_ALL)
    counts[ID_NONE]["name"] = _(ID_NONE)

    self.sorted_store.set_sort_column_id(-1, gtk.SORT_ASCENDING)
    self.label_tree.freeze_child_notify()

    self._remove_invalid_labels(counts)

    for id in sorted(counts):
      if id == NULL_PARENT: continue

      row = self.row_map.get(id)
      if row:
        self.store.set_value(row, 1, counts[id]["name"])
        self.store.set_value(row, 2, counts[id]["count"])
      else:
        if id in RESERVED_IDS:
          parent_id = NULL_PARENT
        else:
          parent_id = Label.get_parent(id)

        parent = self.row_map.get(parent_id)
        if parent:
          data = [id, counts[id]["name"], counts[id]["count"]]
          row = self.store.append(parent, data)
          self.row_map[id] = row
        else:
          log.debug("[%s] Label counts contained orphan: %s",
              PLUGIN_NAME, id)

    self.label_tree.thaw_child_notify()
    self.sorted_store.set_sort_column_id(1, gtk.SORT_ASCENDING)


  def on_button_pressed(self, widget, event):

    x, y = event.get_coords()
    path_info = widget.get_path_at_pos(int(x), int(y))
    if not path_info: return

    path, column, cell_x, cell_y = path_info
    id, name, count = widget.get_model()[path]

    if event.button == 1:
      # Toggle expander of "header" row
      if id == NULL_PARENT:
        if widget.row_expanded(path):
          widget.collapse_row(path)
        else:
          # Only allow selection handler if focused (sets filter)
          if widget.has_focus():
            self._load_tree_state()
          else:
            widget.get_selection().handler_block_by_func(
                self.on_selection_changed)
            self._load_tree_state()
            widget.get_selection().handler_unblock_by_func(
                self.on_selection_changed)
      else:
        # Workaround for expanders not toggling
        size = widget.style_get_property("expander-size")
        pad = widget.style_get_property("horizontal-separator")
        cell_area = widget.get_cell_area(path, column)

        expander_left = cell_area[0]-size-(2*pad)-1
        expander_right = cell_area[0]-pad+1
        if cell_x >= expander_left and cell_x <= expander_right:
          if widget.row_expanded(path):
            widget.collapse_row(path)

            for item in list(self.state["expanded"]):
              if Label.is_ancestor(id, item):
                self.state["expanded"].remove(item)

            if id in self.state["expanded"]:
              self.state["expanded"].remove(id)

            self.config.save()

            return True
          else:
            widget.expand_row(path, False)
            if widget.row_expanded(path):

              if id not in self.state["expanded"]:
                self.state["expanded"].append(id)
                self.config.save()

              return True
            # Else no expander at that position

        # Double click shows the options dialog
        if event.type == gtk.gdk._2BUTTON_PRESS:
          if id not in RESERVED_IDS:
            self.menu.target_id = id
            self.menu.on_options(None)
    elif event.button == 3:
      # Ensure tree view reflects the row at the event
      if id != NULL_PARENT:
        model, row = widget.get_selection().get_selected()
        selected_path = model.get_path(row) if row else None
        if path != selected_path:
          widget.get_selection().select_path(path)

      # Determine sensitivity for popup menu
      level = self.menu.LEVEL3
      if id == NULL_PARENT:
        level = self.menu.LEVEL1
      elif id in RESERVED_IDS:
        level = self.menu.LEVEL2

      self.menu.set_sensitivity(level)
      self.menu.target_id = id

    if id == NULL_PARENT:
      return True


  def on_button_released(self, widget, event):

    if event.button == 3:
      self.menu.popup(None, None, None, event.button, event.time)


  def on_row_collapsed(self, widget, row, path):

    # Select the collapsed row if the filter row is its descendent
    if path == self.filter_path[:len(path)]:
      id = widget.get_model().get_value(row, 0)
      if id != NULL_PARENT:
        widget.get_selection().select_path(path)


  def on_focus_in(self, widget, event):

    # Make sure cursor and selection are consistent on focus in
    path, column = widget.get_cursor()
    model, row = widget.get_selection().get_selected()
    selected_path = model.get_path(row) if row else None
    if path and selected_path:
      if path != selected_path:
        widget.set_cursor(selected_path)
      else:
        widget.emit("cursor-changed")


  def on_cursor_changed(self, widget):

    # Ensure selection handler runs if row is clicked from out of focus
    path, column = widget.get_cursor()
    if path:
      model, row = widget.get_selection().get_selected()
      log.debug("[%s] Cursor: %s '%s'", PLUGIN_NAME,
          *model.get(row, 0, 1))

      widget.get_selection().emit("changed")

      # Autoscroll
      if not column:
        column = widget.get_column(0)

      window = widget.get_ancestor(gtk.ScrolledWindow)
      vadjustment = window.get_vadjustment()
      row_area = widget.get_background_area(path, column)
      offset = widget.translate_coordinates(widget.get_parent(), 0, 0)

      top_y = row_area[1] + offset[1]
      bottom_y = top_y + row_area[3]
      if top_y < vadjustment.value:
        vadjustment.clamp_page(top_y, top_y + vadjustment.page_size)
      elif bottom_y - vadjustment.page_size > vadjustment.value:
        vadjustment.clamp_page(bottom_y - vadjustment.page_size, bottom_y)


  def on_selection_changed(self, widget):

    model, row = widget.get_selected()
    if row:
      id, name = model.get(row, 0, 1)
      if id != NULL_PARENT:
        if id == ID_ALL:
          filter_data = {}
        elif id == ID_NONE:
          filter_data = {STATUS_ID: ID_NONE}
        else:
          filter_data = {STATUS_ID: id}

        component.get("TorrentView").set_filter(filter_data)
        self.filter_path = model.get_path(row)

        self.state["selected"] = id


  def _install_label_tree(self):

    filter_view = component.get("FilterTreeView")
    view = filter_view.label_view
    sidebar = filter_view.sidebar

    for tab_child in sidebar.notebook.get_children():
      if sidebar.notebook.get_tab_label_text(tab_child) == "Filters":
        tab_child.remove(view)

        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)

        vbox = gtk.VBox()
        vbox.pack_start(view, False)
        vbox.pack_start(self.label_tree, True)
        viewport.add(vbox)

        tab_child.add(viewport)
        tab_child.show_all()


        def on_row_expanded(widget, row, path):

          if not widget.has_focus():
            # Block next call to the handler that sets the filter
            selection = widget.get_selection()
            selection.handler_block_by_func(filter_view.on_selection_changed)


            def unblock_handler(widget):

              widget.disconnect(handler)
              widget.handler_unblock_by_func(filter_view.on_selection_changed)


            handler = selection.connect("changed", unblock_handler)


        self.external_handlers.append(
            view.connect("row-expanded", on_row_expanded))
        self.external_handlers.append(
            view.connect("cursor-changed", self.on_cursor_changed))
        self.external_handlers.append(
            view.connect("focus-in-event", self.on_focus_in))

        return


  def _uninstall_label_tree(self):

    filter_view = component.get("FilterTreeView")
    view = filter_view.label_view
    sidebar = filter_view.sidebar

    for tab_child in sidebar.notebook.get_children():
      if sidebar.notebook.get_tab_label_text(tab_child) == "Filters":
        viewport = tab_child.get_child()

        vbox = viewport.get_child()
        vbox.remove(view)
        vbox.remove(self.label_tree)

        tab_child.remove(viewport)
        tab_child.add(view)
        tab_child.show_all()

        for handler in self.external_handlers:
          view.disconnect(handler)

        return


  def _build_label_tree(self):

    tree_view = gtk.TreeView()
    column = gtk.TreeViewColumn(DISPLAY_NAME)
    renderer = gtk.CellRendererText()

    column.pack_start(renderer, False)
    column.set_cell_data_func(renderer, self._render_cell_data)

    tree_view.append_column(column)
    tree_view.set_headers_visible(False)
    tree_view.set_search_column(1)
    tree_view.set_enable_tree_lines(True)

    return tree_view


  def _render_cell_data(self, column, cell, model, row):

    id, name, count = model.get(row, 0, 1, 2)

    if id == NULL_PARENT:
      bg = component.get("FilterTreeView").colour_background
      fg = component.get("FilterTreeView").colour_foreground

      cell.set_property("cell-background-gdk", bg)
      cell.set_property("foreground-gdk", fg)
      label_str = name
    else:
      cell.set_property("cell-background", None)
      cell.set_property("foreground", None)

      if self._has_descendent_counts(id):
        label_str = "%s (%s) ..." % (name, count)
      else:
        label_str = "%s (%s)" % (name, count)

    cell.set_property("text", label_str)


  def _get_label_name(self, id):

    return self.store.get_value(self.row_map[id], 1)


  def _remove_invalid_labels(self, counts):

    removals = []
    for id in self.row_map:
      if id not in counts and id != NULL_PARENT:
        removals.append(id)

    for id in sorted(removals, reverse=True):
      row = self.row_map[id]
      self.store.remove(row)
      del self.row_map[id]


  def _load_tree_state(self):

    for id in sorted(self.state["expanded"], reverse=True):
      row = self.row_map.get(id)
      if not row or not self.store.iter_has_child(row):
        self.state["expanded"].remove(id)
        continue

      path = self.store.get_path(row)
      path = self.sorted_store.convert_child_path_to_path(path)
      self.label_tree.expand_to_path(path)

    row = self.row_map.get(self.state["selected"])
    if not row:
      self.state["selected"] = ID_ALL
      row = self.row_map[ID_ALL]

    path = self.store.get_path(row)
    path = self.sorted_store.convert_child_path_to_path(path)
    self.label_tree.expand_to_path(path[:-1])

    self.label_tree.get_selection().select_path(path)
    self.filter_path = path

    self.config.save()


  def _remove_label_subtree(self, label_id):


    def remove(model, path, row):
      id = model.get_value(row, 0)
      log.debug("[%s] Removing: %s", PLUGIN_NAME, id)
      model.remove(row)
      del self.row_map[id]
      client.labelplus.remove_label(id)


    self.label_tree.freeze_child_notify()
    row = self.row_map[label_id]
    treemodel_subtree_op(self.store, row, post_func=remove)
    self.label_tree.thaw_child_notify()

    self._load_tree_state()


  def _has_descendent_counts(self, label_id):


    def check(model, path, row):
      id, count = model.get(row, 0, 2)
      return id != label_id and count > 0


    row = self.row_map[label_id]
    return treemodel_subtree_op(self.store, row, pre_func=check)


  def _label_sort_asc(self, store, iter1, iter2):

    id1, name1 = store.get(iter1, 0, 1)
    id2, name2 = store.get(iter2, 0, 1)

    test1 = id1 in RESERVED_IDS
    test2 = id2 in RESERVED_IDS

    if test1 and test2:
      return cmp(id1, id2)
    elif test1:
      return -1
    elif test2:
      return 1

    return cmp(name1, name2)
