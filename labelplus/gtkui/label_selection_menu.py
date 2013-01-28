#
# label_selection_menu.py
#
# Copyright (C) 2013 Ratanak Lun <ratanakvlun@gmail.com>
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
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
from deluge.ui.client import client

from labelplus.common.constant import DISPLAY_NAME, PLUGIN_NAME
from labelplus.common.constant import ID_NONE

import labelplus.common.label as Label
from labelplus.common.debug import debug


MENU_ITEM = 0
HANDLER = 1


class LabelSelectionMenu(gtk.MenuItem):


  def __init__(self):

    gtk.MenuItem.__init__(self, DISPLAY_NAME)

    self.plugin = component.get("GtkPlugin.%s" % PLUGIN_NAME)

    self.submenu = gtk.Menu()
    self.set_submenu(self.submenu)

    self.connect("activate", self.on_activate)
    self.on_activate(self)

    self.show_all()


  @debug()
  def on_activate(self, widget):

    self.handler_block_by_func(self.on_activate)

    for child in self.submenu.get_children():
      self.submenu.remove(child)

    item = gtk.MenuItem(_(ID_NONE))
    item.connect("activate", self.on_select_label, None)
    self.submenu.append(item)

    labels = self.plugin.get_labels()
    self._load_labels(labels)


  @debug()
  def _load_labels(self, labels):

    if labels:
      self.submenu.append(gtk.SeparatorMenuItem())
      labels = sorted(labels, key=lambda x: (Label.get_parent(x[0]), x[1]))

    items = {}
    for id, name in labels:
      item = gtk.MenuItem(name)
      handler = item.connect("activate", self.on_select_label, id)
      items[id] = (item, handler)

      parent_id = Label.get_parent(id)
      parent = items.get(parent_id)
      if parent:
        if parent[MENU_ITEM].get_submenu() is None:
          parent[MENU_ITEM].handler_disconnect(parent[HANDLER])
          parent[MENU_ITEM].set_submenu(gtk.Menu())

          # Create subitem for selecting items with submenus
          parent_item = gtk.MenuItem(parent[MENU_ITEM].get_label())
          parent_item.connect("activate", self.on_select_label, parent_id)
          parent[MENU_ITEM].get_submenu().append(parent_item)
          parent[MENU_ITEM].get_submenu().append(gtk.SeparatorMenuItem())

        parent[MENU_ITEM].get_submenu().append(item)
      else:
        self.submenu.append(item)

    self.show_all()

    self.handler_unblock_by_func(self.on_activate)


  @debug()
  def on_select_label(self, widget, label_id):

    torrents = component.get("TorrentView").get_selected_torrents()
    client.labelplus.set_torrent_labels(label_id, torrents)
