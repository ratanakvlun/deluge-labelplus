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
from labelplus.common.constant import RESERVED_IDS, ID_ALL, ID_NONE

from common.constant import GTKUI_CONFIG
from common.constant import GTKUI_DEFAULTS
from common.constant import DAEMON_DEFAULTS
from common.constant import GTKUI_MAPS

from labelplus.common.file import get_resource
from labelplus.common.config import get_version, convert

from label_options_dialog import LabelOptionsDialog
from label_selection_menu import LabelSelectionMenu
from label_sidebar import LabelSidebar
from preferences import Preferences
from add_torrent_ext import AddTorrentExt

import dnd


MAX_RETRIES = 10
WAIT_TIME = 1.0

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
    self.retries = 0


  def enable(self):

    self.timestamp = None
    self.label_data = None
    self.dialog = None

    self._config = None

    info = client.connection_info()
    self._daemon = "%s@%s:%s" % (info[2], info[0], info[1])

    client.labelplus.is_initialized().addCallback(self.cb_check)


  def cb_check(self, result):

    if result == True:
      client.labelplus.get_label_data(self.timestamp).addCallback(
        self.cb_data_init)
    elif self.retries < MAX_RETRIES:
      reactor.callLater(WAIT_TIME, self.enable)
      self.retries += 1


  def cb_data_init(self, data):

    self.timestamp = data[0]
    self.label_data = data[1]

    self.label_data[ID_ALL]["name"] = _(ID_ALL)
    self.label_data[ID_NONE]["name"] = _(ID_NONE)

    self._do_load()


  def _do_load(self):

    self.load_config()

    component.get("TorrentView").add_text_column(DISPLAY_NAME,
        status_field=[STATUS_NAME])

    self.menu = self._create_menu()
    self.sep = component.get("MenuBar").add_torrentmenu_separator()
    component.get("MenuBar").torrentmenu.append(self.menu)

    self.label_sidebar = LabelSidebar()

    self.preferences = Preferences()

    self.add_torrent_ext = AddTorrentExt()

    self.enable_dnd()

    self.status_item = None

    self.initialized = True


  def disable(self):

    self.retries = MAX_RETRIES

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


  def _create_menu(self):

    menu = gtk.MenuItem(DISPLAY_NAME)
    menu.connect("activate", self._on_activate)
    submenu = gtk.Menu()

    self.label_selection_menu = LabelSelectionMenu(_("Set Label"))
    submenu.append(self.label_selection_menu)

    self.menu_jump_item = gtk.MenuItem(_("Go to Label"))
    self.menu_jump_item.connect("activate", self._do_go_to_label)
    submenu.append(self.menu_jump_item)

    menu.set_submenu(submenu)
    menu.show_all()

    return menu


  def _destroy_menu(self):

    self.label_selection_menu.destroy()
    del self.label_selection_menu

    self.menu.destroy()
    del self.menu


  def _on_activate(self, widget):

    if len(component.get("TorrentView").get_selected_torrents()) == 1:
      self.menu_jump_item.set_sensitive(True)
    else:
      self.menu_jump_item.set_sensitive(False)


  def _do_go_to_label(self, widget):

    id = component.get("TorrentView").get_selected_torrent()
    client.labelplus.get_torrent_label(id).addCallback(self.label_sidebar.select_label)


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

    if target >= 2:
      daemons = self._config["daemon"]
      if self._daemon not in daemons:
        daemons[self._daemon] = copy.deepcopy(DAEMON_DEFAULTS)

    return self._config


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
      callback=self._do_open_label_options,
      tooltip="Label Bandwidth Usage")

    self.status_item._ebox.hide_all()


  def _remove_status_bar_item(self):

    if self.status_item:
      component.get("StatusBar").remove_item(self.status_item)
      self.status_item = None


  def _do_open_label_options(self, widget, event):


    def on_close(widget):

      self.dialog = None


    if event.button == 1 and self.dialog == None:
      if self.label_sidebar.page_selected():
        id = self.label_sidebar.get_selected_label()

        if id not in RESERVED_IDS and id in self.label_data:
          name = self.label_data[id]["name"]
          self.dialog = LabelOptionsDialog(id, name, 1)
          self.dialog.register_close_func(on_close)


  def _status_bar_update(self):

    if self.status_item:
      id = None

      if self.label_sidebar.page_selected():
        id = self.label_sidebar.get_selected_label()

      if id == ID_NONE or (id not in RESERVED_IDS and id in self.label_data):
        self.status_item._ebox.show_all()
        client.labelplus.get_label_bandwidth_usage(id).addCallback(
          self._do_status_bar_update)
      else:
        self.status_item._ebox.hide_all()
        reactor.callLater(1, self._status_bar_update)


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

      reactor.callLater(1, self._status_bar_update)
