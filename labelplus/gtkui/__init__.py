#
# __init__.py
#
# Copyright (C) 2014 Ratanak Lun <ratanakvlun@gmail.com>
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
#
# Basic plugin template created by:
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
# Copyright (C) 2007-2009 Andrew Resch <andrewresch@gmail.com>
# Copyright (C) 2009 Damien Churchill <damoxc@gmail.com>
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


import copy
import logging

import gtk

from twisted.internet import reactor

from deluge import component
from deluge.plugins.pluginbase import GtkPluginBase
from deluge.ui.client import client
import deluge.configmanager

from labelplus.common.constant import DISPLAY_NAME, PLUGIN_NAME
from labelplus.common.constant import STATUS_NAME
from labelplus.common.constant import STATUS_ID
from labelplus.common.constant import RESERVED_IDS, ID_ALL, ID_NONE

from common.constant import GTKUI_CONFIG
from common.constant import GTKUI_DEFAULTS
from common.constant import DAEMON_DEFAULTS
from common.constant import GTKUI_MAPS

from labelplus.common.file import get_resource
from labelplus.common.config import get_version, convert
from labelplus.common.label import get_parent

from label_options_dialog import LabelOptionsDialog
from label_selection_menu import LabelSelectionMenu
from label_sidebar import LabelSidebar
from preferences import Preferences
from add_torrent_ext import AddTorrentExt

import dnd


STATUS_UPDATE_INTERVAL = 2.0

UNITS = [
  ("TiB", 1024.0**4),
  ("GiB", 1024.0**3),
  ("MiB", 1024.0**2),
  ("KiB", 1024.0),
  ("B", 1.0),
]

class GtkUI(GtkPluginBase):


  def __init__(self, plugin_name):

    super(GtkUI, self).__init__(plugin_name)
    self.initialized = False


  def enable(self):

    client.labelplus.is_initialized().addCallback(self.cb_check)


  def cb_check(self, result):

    if result == True:
      client.labelplus.get_label_data(None).addCallback(self.cb_data_init)
    else:
      reactor.callLater(1, self.enable)


  def cb_data_init(self, data):

    self.dialog = None
    self._config = None

    info = client.connection_info()
    self._daemon = "%s@%s:%s" % (info[2], info[0], info[1])

    self.timestamp = data[0]
    self.label_data = data[1]

    self.label_data[ID_ALL]["name"] = _(ID_ALL)
    self.label_data[ID_NONE]["name"] = _(ID_NONE)

    self._do_load()


  def _do_load(self):

    self.load_config()

    component.get("TorrentView").add_text_column(DISPLAY_NAME,
        col_type=[str, str], status_field=[STATUS_NAME, STATUS_ID])

    component.get("TorrentView").treeview.connect(
      "button-press-event", self.on_tv_button_press)

    self.menu = self._create_context_menu()
    self.sep = component.get("MenuBar").add_torrentmenu_separator()
    component.get("MenuBar").torrentmenu.append(self.menu)

    self.label_sidebar = LabelSidebar()

    self.preferences = Preferences()

    self.add_torrent_ext = AddTorrentExt()

    self.enable_dnd()

    self.status_item = None

    self.initialized = True


  def on_tv_button_press(self, widget, event):

    x, y = event.get_coords()
    path_info = widget.get_path_at_pos(int(x), int(y))
    if not path_info:
      if event.button == 3:
        self._popup_jump_menu(widget, event)
      else:
        return

    if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
      if path_info[1] and path_info[1].get_title() == DISPLAY_NAME:
        id = self.get_selected_torrent_label()
        if (self.label_sidebar.page_selected() and
           id == self.label_sidebar.get_selected_label()):
          self._do_open_label_options(widget, event)
        else:
          self._do_go_to_label(widget)


  def disable(self):

    if self.initialized:
      self.initialized = False

      self._config.save()
      deluge.configmanager.close(GTKUI_CONFIG)

      self._remove_status_bar_item()

      self.disable_dnd()

      component.get("MenuBar").torrentmenu.remove(self.sep)
      component.get("MenuBar").torrentmenu.remove(self.menu)
      self._destroy_menu()

      self.label_sidebar.unload()
      del self.label_sidebar

      self.preferences.unload()

      self.add_torrent_ext.unload()

      component.get("TorrentView").remove_column(DISPLAY_NAME)


  def _create_context_menu(self):

    menu = gtk.MenuItem(DISPLAY_NAME)
    submenu = gtk.Menu()

    set_label_menu = self._create_set_label_menu()
    submenu.append(set_label_menu)

    jump_menu = self._create_jump_menu()
    submenu.append(jump_menu)

    menu.set_submenu(submenu)
    menu.show_all()

    return menu


  def _create_set_label_menu(self):


    def on_select_label(widget, label_id):

      torrents = component.get("TorrentView").get_selected_torrents()
      client.labelplus.set_torrent_labels(label_id, torrents)


    def hide_unavailable(widget):

      parent_item.hide()

      id = self.get_selected_torrent_label()
      if id:
        parent = get_parent(id)
        if parent and parent not in RESERVED_IDS:
          parent_item.connect("activate", on_select_label, parent)
          parent_item.show()


    items = []

    parent_item = gtk.MenuItem(_("Parent"))
    items.append(parent_item)

    menu_item = gtk.MenuItem(_(ID_NONE))
    menu_item.connect("activate", on_select_label, ID_NONE)
    items.append(menu_item)

    menu_item = gtk.SeparatorMenuItem()
    items.append(menu_item)

    menu = LabelSelectionMenu(_("Set Label"), on_select_label, items)
    menu.connect("activate", hide_unavailable)

    return menu


  def _create_jump_menu(self):


    def on_select_label(widget, label_id):

      self._do_go_to_label(widget, label_id)


    def hide_unavailable(widget):

      parent_item.hide()

      id = self.get_selected_torrent_label()
      if not id and self.label_sidebar.page_selected():
        id = self.label_sidebar.get_selected_label()

      if id:
        parent = get_parent(id)
        if parent and parent not in RESERVED_IDS:
          parent_item.connect("activate", on_select_label, parent)
          parent_item.show()


    items = []

    parent_item = gtk.MenuItem(_("Parent"))
    items.append(parent_item)

    menu_item = gtk.MenuItem(_(ID_ALL))
    menu_item.connect("activate", on_select_label, ID_ALL)
    items.append(menu_item)

    menu_item = gtk.MenuItem(_(ID_NONE))
    menu_item.connect("activate", on_select_label, ID_NONE)
    items.append(menu_item)

    menu_item = gtk.SeparatorMenuItem()
    items.append(menu_item)

    menu = LabelSelectionMenu(_("Jump To"), on_select_label, items)
    menu.connect("activate", hide_unavailable)

    return menu


  def _popup_jump_menu(self, widget, event):

    top = gtk.Menu()
    menu = gtk.MenuItem(DISPLAY_NAME)
    submenu = gtk.Menu()

    submenu.append(self._create_jump_menu())
    menu.set_submenu(submenu)
    top.append(menu)

    top.show_all()
    top.popup(None, None, None, event.button, event.time)


  def _destroy_menu(self):

    self.menu.destroy()
    del self.menu


  def _do_go_to_label(self, widget, id=None):

    if not id:
      id = self.get_selected_torrent_label()

    if id is not None:
      self.label_sidebar.select_label(id)


  def load_config(self):

    self._config = deluge.configmanager.ConfigManager(GTKUI_CONFIG)

    source = get_version(self._config.config)
    target = get_version(GTKUI_DEFAULTS)

    if len(self._config.config) == 0:
      self._config._Config__config = copy.deepcopy(GTKUI_DEFAULTS)
    else:
      if source != target:
        map = GTKUI_MAPS.get((source, target), None)
        if map:
          self._config._Config__config = convert(self._config.config, map)
        else:
          self._config._Config__config = copy.deepcopy(GTKUI_DEFAULTS)
      else:
        self.normalize_config()

    if target >= 2:
      daemons = self._config["daemon"]
      if self._daemon not in daemons:
        daemons[self._daemon] = copy.deepcopy(DAEMON_DEFAULTS)


  def normalize_config(self):

    commons = dict(GTKUI_DEFAULTS["common"])
    commons.update(self._config.config["common"])
    self._config.config["common"] = commons

    saved_daemons = component.get("ConnectionManager").config["hosts"]
    if not saved_daemons:
      self._config["daemon"] = {}
    else:
      daemons = ["%s@%s:%s" % (x[3], x[1], x[2]) for x in saved_daemons]

      for daemon in self._config["daemon"].keys():
        if daemon != self._daemon and daemon not in daemons:
          del self._config["daemon"][daemon]


  def update(self):

    if self.initialized:
      client.labelplus.get_label_data(self.timestamp).addCallback(
        self.cb_update_data)

      if self._config["common"]["show_label_bandwidth"]:
        if not self.status_item:
          self._add_status_bar_item()
          reactor.callLater(1, self._status_bar_update)
      else:
        self._remove_status_bar_item()


  def cb_update_data(self, data):

    if data is not None:
      self.timestamp = data[0]
      self.label_data = data[1]

      self.label_data[ID_ALL]["name"] = _(ID_ALL)
      self.label_data[ID_NONE]["name"] = _(ID_NONE)

      self.label_sidebar.update_counts(self.label_data)


  def get_labels(self):

    data = self.label_data
    labels = []
    for id in data:
      if id not in RESERVED_IDS:
        labels.append((id, data[id]["name"]))

    return labels


  def get_label_counts(self):

    return self.label_data


  def enable_dnd(self):


    def get_drag_icon(widget, x, y):

      num = widget.get_selection().count_selected_rows()

      if num > 1:
        pixbuf = self.icon_multiple
      else:
        pixbuf = self.icon_single

      return (pixbuf, 0, 0)


    def on_drag_end(widget, context):

      if self.label_sidebar.page_selected():
        self.label_sidebar.label_tree.get_selection().emit("changed")


    def get_ids(widget, path, col, selection, *args):

      selection.set("TEXT", 8, "OK")

      return True


    def receive_ids(widget, path, col, pos, selection, *args):

      if selection.data == "OK":
        model = widget.get_model()
        id = model[path][0]

        if id == ID_NONE:
          id = None

        if id not in RESERVED_IDS:
          torrents = component.get("TorrentView").get_selected_torrents()
          client.labelplus.set_torrent_labels(id, torrents)

          return True


    def peek_ids(widget, path, col, pos, selection, *args):

      if selection.data == "OK":
        model = widget.get_model()
        id = model[path][0]

        if id == ID_NONE:
          id = None

        if id not in RESERVED_IDS:
          return True


    class ModuleFilter(object):


      def filter(self, record):

        record.msg = "[%s] %s" % (PLUGIN_NAME, record.msg)

        return True


    dnd.log.setLevel(logging.INFO)
    dnd.log.addFilter(ModuleFilter())

    src_target = dnd.DragTarget(
      name="torrent_ids",
      scope=gtk.TARGET_SAME_APP,
      action=gtk.gdk.ACTION_MOVE,
      data_func=get_ids,
    )

    src_treeview = component.get("TorrentView").treeview

    self.icon_single = \
        src_treeview.render_icon(gtk.STOCK_DND, gtk.ICON_SIZE_DND)
    self.icon_multiple = \
        src_treeview.render_icon(gtk.STOCK_DND_MULTIPLE, gtk.ICON_SIZE_DND)

    self.src_proxy = dnd.TreeViewDragSourceProxy(src_treeview,
      get_drag_icon, on_drag_end)
    self.src_proxy.add_target(src_target)

    dest_target = dnd.DragTarget(
      name="torrent_ids",
      scope=gtk.TARGET_SAME_APP,
      action=gtk.gdk.ACTION_MOVE,
      pos=gtk.TREE_VIEW_DROP_INTO_OR_BEFORE,
      data_func=receive_ids,
      aux_func=peek_ids,
    )

    dest_treeview = self.label_sidebar.label_tree
    self.dest_proxy = dnd.TreeViewDragDestProxy(dest_treeview)
    self.dest_proxy.add_target(dest_target)


  def disable_dnd(self):

    self.dest_proxy.unload()
    self.src_proxy.unload()


  def _add_status_bar_item(self):

    self.status_item = component.get("StatusBar").add_item(
      image=get_resource("labelplus_icon.png"),
      text="",
      callback=self._do_open_label_options_bandwidth,
      tooltip="")

    self.status_item._ebox.hide_all()


  def _remove_status_bar_item(self):

    if self.status_item:
      component.get("StatusBar").remove_item(self.status_item)
      self.status_item = None


  def get_selected_torrent_label(self):

    label_id = None
    tv = component.get("TorrentView")
    torrents = tv.get_selected_torrents()

    if len(torrents) == 1:
      id = torrents[0]
      status = tv.get_torrent_status(id)

      if STATUS_ID in status:
        label_id = status[STATUS_ID] or ID_NONE

    return label_id


  def _do_open_label_options_bandwidth(self, widget, event):

    self._do_open_label_options(widget, event, 1)


  def _do_open_label_options(self, widget, event, page=0):


    def on_close(widget):

      self.dialog = None


    if self.dialog == None:
      id = self.label_sidebar.get_selected_label()

      if id == ID_ALL or not self.label_sidebar.page_selected():
        id = self.get_selected_torrent_label()

      if id not in RESERVED_IDS and id in self.label_data:
        name = self.label_data[id]["full_name"]
        self.dialog = LabelOptionsDialog(id, name, page)
        self.dialog.register_close_func(on_close)


  def _status_bar_update(self):

    if self.status_item:
      id = self.label_sidebar.get_selected_label()

      if id == ID_ALL or not self.label_sidebar.page_selected():
        id = self.get_selected_torrent_label()

      if id == ID_NONE or (id not in RESERVED_IDS and id in self.label_data):
        self.status_item._ebox.show_all()
        self.status_item.set_tooltip(
          "Bandwidth Used By: %s" % self.label_data[id]["full_name"])

        include_sublabels = self._config["common"]["status_include_sublabel"]

        client.labelplus.get_label_bandwidth_usage(
          id, include_sublabels).addCallback(self._do_status_bar_update)
      else:
        self.status_item._ebox.hide_all()
        reactor.callLater(STATUS_UPDATE_INTERVAL, self._status_bar_update)


  def _do_status_bar_update(self, result):

    if self.status_item:
      download_rate = result[0]
      download_unit = "B"

      upload_rate = result[1]
      upload_unit = "B"

      for (unit, bytes) in UNITS:
        if download_rate >= bytes:
          download_rate /= bytes
          download_unit = unit
          break

      for (unit, bytes) in UNITS:
        if upload_rate >= bytes:
          upload_rate /= bytes
          upload_unit = unit
          break

      self.status_item.set_text(
        "%.1f %s/s | %.1f %s/s" % (
          download_rate, download_unit, upload_rate, upload_unit))

      reactor.callLater(STATUS_UPDATE_INTERVAL, self._status_bar_update)
