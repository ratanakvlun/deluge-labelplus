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

from labelplus.common.constant import PLUGIN_NAME, DISPLAY_NAME, MODULE_NAME
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

    self.plugin = component.get("GtkPlugin.%s" % PLUGIN_NAME)

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

    self.row_map = {
      NULL_PARENT: None,
    }

    self._install_label_tree()

    counts = self.plugin.get_label_counts()
    self.update_counts(counts)

    self._complete_init()


  @debug()
  def unload(self):

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


  @debug()
  def _complete_init(self):

    self.label_tree.set_model(self.sorted_store)
    self._load_tree_state()

    self.label_tree.set_cursor(self.filter_path)

    self.label_tree.get_selection().connect(
        "changed", self.on_selection_changed)

    self.label_tree.connect("button-press-event", self.on_button_pressed)
    self.label_tree.connect("button-release-event", self.on_button_released)
    self.label_tree.connect("row-collapsed", self.on_row_collapsed)
    self.label_tree.connect("row-expanded", self.on_row_expanded)
    self.label_tree.connect("cursor-changed", self.on_cursor_changed)
    self.label_tree.connect("focus-in-event", self.on_focus_in)

    self.label_tree.show_all()
    self.menu.show_all()


  def update_counts(self, counts):

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

        if parent_id in self.row_map:
          parent = self.row_map.get(parent_id)
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

    # Ensure tree view reflects the row at the event
    model, row = widget.get_selection().get_selected()
    selected_path = model.get_path(row) if row else None
    if path != selected_path:
      widget.set_cursor(path)

    if event.button == 1:
      # Double click shows the options dialog
      if event.type == gtk.gdk._2BUTTON_PRESS:
        if id not in RESERVED_IDS:
          self.menu.target_id = id
          self.menu.on_options(None)
    elif event.button == 3:
      # Determine sensitivity for popup menu
      level = self.menu.LEVEL3
      if id in RESERVED_IDS:
        level = self.menu.LEVEL2

      self.menu.set_sensitivity(level)
      self.menu.target_id = id


  def on_button_released(self, widget, event):

    if event.button == 3:
      self.menu.popup(None, None, None, event.button, event.time)


  def on_row_expanded(self, widget, row, path):

    id = widget.get_model()[path][0]

    if id not in self.state["expanded"]:
      self.state["expanded"].append(id)
      self.config.save()


  def on_row_collapsed(self, widget, row, path):

    id = widget.get_model()[path][0]

    for item in list(self.state["expanded"]):
      if Label.is_ancestor(id, item):
        self.state["expanded"].remove(item)

      if id in self.state["expanded"]:
        self.state["expanded"].remove(id)

    self.config.save()

    # Select the collapsed row if the filter row is its descendent
    if path == self.filter_path[:len(path)]:
      id = widget.get_model().get_value(row, 0)
      widget.get_selection().select_path(path)


  def on_focus_in(self, widget, event):

    # Make sure cursor and selection are consistent on focus in
    path, column = widget.get_cursor()
    model, row = widget.get_selection().get_selected()
    selected_path = model.get_path(row) if row else None
    if path and selected_path:
      widget.scroll_to_cell(selected_path)
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


  def on_selection_changed(self, widget):

    model, row = widget.get_selected()
    if row:
      id, name = model.get(row, 0, 1)
      if id == ID_ALL:
        filter_data = {}
      elif id == ID_NONE:
        filter_data = {STATUS_ID: [ID_NONE]}
      else:
        filter_data = {STATUS_ID: [id]}

      component.get("TorrentView").set_filter(filter_data)
      self.filter_path = model.get_path(row)

      self.state["selected"] = id


  def _install_label_tree(self):

    filter_view = component.get("FilterTreeView")
    view = filter_view.label_view
    sidebar = filter_view.sidebar

    sidebar.add_tab(self.label_tree, MODULE_NAME, DISPLAY_NAME)

    self.external_handlers.append(
        (view, view.connect("cursor-changed", self.on_cursor_changed)))
    self.external_handlers.append(
        (view, view.connect("focus-in-event", self.on_focus_in)))


    def on_hide(widget):

      row = self.row_map[ID_ALL]

      path = self.store.get_path(row)
      path = self.sorted_store.convert_child_path_to_path(path)

      self.label_tree.set_cursor(path)


    def on_switch_page(widget, page, page_num, treeview):

      if widget.has_focus():
        child = widget.get_nth_page(page_num)
        if treeview.is_ancestor(child):
          treeview.get_selection().emit("changed")


    notebook = sidebar.notebook

    self.external_handlers.append(
      (notebook, notebook.connect("hide", on_hide)))

    self.external_handlers.append((notebook,
      notebook.connect("switch-page", on_switch_page, view)))
    self.external_handlers.append((notebook,
      notebook.connect("switch-page", on_switch_page, self.label_tree)))

    # Hack to make initial drag and drop work properly between tabs
    page = notebook.get_current_page()
    parent_page = notebook.page_num(self.label_tree.parent)
    notebook.set_current_page(parent_page)
    notebook.set_current_page(page)

    # Make sure expanders are indented by overriding default style
    name = self.label_tree.get_name()
    path = self.label_tree.path()

    rc_string = """
        style '%s' { GtkTreeView::indent-expanders = 1 }
        widget '%s' style '%s'
    """ % (name, path, name)

    gtk.rc_parse_string(rc_string)
    gtk.rc_reset_styles(self.label_tree.get_toplevel().get_settings())


  def _uninstall_label_tree(self):

    filter_view = component.get("FilterTreeView")
    view = filter_view.label_view
    sidebar = filter_view.sidebar

    sidebar.remove_tab(MODULE_NAME)

    for obj, handler in self.external_handlers:
      if obj.handler_is_connected(handler):
        obj.disconnect(handler)


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

    name = "%s_tree_view" % MODULE_NAME
    tree_view.set_name(name)

    return tree_view


  def _render_cell_data(self, column, cell, model, row):

    id, name, count = model.get(row, 0, 1, 2)

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

    parent_path = path[:-1]
    if parent_path:
      self.label_tree.expand_to_path(parent_path)

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


    self.label_tree.freeze_notify()
    row = self.row_map[label_id]
    treemodel_subtree_op(self.store, row, post_func=remove)
    self.label_tree.thaw_notify()

    self._load_tree_state()


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
