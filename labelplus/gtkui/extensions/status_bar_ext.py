#
# status_bar_ext.py
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

import twisted.internet.reactor

import deluge.common
import deluge.component

import labelplus.common


from twisted.python.failure import Failure

from deluge.ui.client import client
from deluge.ui.client import DelugeRPCError

from labelplus.common import LabelPlusError


from labelplus.common.label import (
  ID_ALL, ID_NONE,
)

from labelplus.common.literals import (
  STR_UPDATE, ERR_TIMED_OUT, ERR_MAX_RETRY,
)

STATUS_ICON_FILE = labelplus.common.get_resource("labelplus_icon.png")

UPDATE_INTERVAL = 1.0

THROTTLED_INTERVAL = 6.0
MAX_TRIES = 10

REQUEST_TIMEOUT = 10.0

DOWNLOAD_RATE = 0
UPLOAD_RATE = 1


log = logging.getLogger(__name__)

from labelplus.gtkui import RT


class StatusBarExt(object):

  # Section: Initialization

  def __init__(self, plugin):

    self._plugin = plugin
    self._status_bar = deluge.component.get("StatusBar")

    self._store = None
    self._status_item = None

    self._tries = 0
    self._calls = []

    try:
      self._store = plugin.store.copy()
      if __debug__: RT.register(self._store, __name__)

      self._install_status_item()

      self._plugin.register_update_func(self.update_store)
    except:
      self.unload()
      raise

    twisted.internet.reactor.callLater(0, self._update_loop)


  # Section: Deinitialization

  def unload(self):

    labelplus.common.cancel_calls(self._calls)

    self._plugin.deregister_update_func(self.update_store)

    self._uninstall_status_item()

    self._destroy_store()


  def _destroy_store(self):

    if self._store:
      self._store.destroy()
      self._store = None


  # Section: Public: Update

  def update_store(self, store):

    self._store.destroy()
    self._store = store.copy()
    if __debug__: RT.register(self._store, __name__)


  # Section: Status Bar

  def _install_status_item(self):

    self._status_item = self._status_bar.add_item(image=STATUS_ICON_FILE)
    self._status_item._ebox.hide_all()


  def _uninstall_status_item(self):

    if self._status_item:
      self._status_bar.remove_item(self._status_item)
      self._status_item = None


  # Section: Status Bar: Update

  def _update_loop(self):

    def on_timeout():

      log.error("%s: %s", STR_UPDATE, LabelPlusError(ERR_TIMED_OUT))

      if self._status_item:
        self._tries += 1
        if self._tries < MAX_TRIES:
          self._calls.append(twisted.internet.reactor.callLater(
            THROTTLED_INTERVAL, self._update_loop))
        else:
          log.error("%s: %s", STR_UPDATE, LabelPlusError(ERR_MAX_RETRY))


    def process_result(result):

      if isinstance(result, Failure):
        if (isinstance(result.value, DelugeRPCError) and
            result.value.exception_type == "LabelPlusError"):
          log.error("%s: %s", STR_UPDATE,
            LabelPlusError(result.value.exception_msg))
          interval = THROTTLED_INTERVAL
        else:
          return result
      else:
        self._tries = 0
        interval = UPDATE_INTERVAL
        self._update_status_bar(result)

      if self._status_item:
        self._calls.append(twisted.internet.reactor.callLater(interval,
          self._update_loop))


    labelplus.common.clean_calls(self._calls)

    if not self._status_item:
      return

    ext = self._plugin.get_extension("SidebarExt")
    ids = ext.get_selected_labels() if ext else None
    if not ids or (len(ids) == 1 and ID_ALL in ids):
      ext = self._plugin.get_extension("TorrentViewExt")
      ids = ext.get_selected_torrent_labels() if ext else None

    if (ids and self._plugin.config["common"]["status_bar"] and
        ID_ALL not in ids):
      tooltip = "Bandwidth Used By: %s" % (self._store[ids[0]]["fullname"] if
        len(ids) == 1 else "*Multiple*")

      include = self._plugin.config["common"]["status_bar_include_sublabels"]
      if include:
        if ids[0] != ID_NONE:
          tooltip += "/*"

        for id in list(ids):
          if self._store.is_user_label(id):
            ids += self._store[id]["descendents"]["ids"]

      self._status_item.set_tooltip(tooltip)

      deferred = client.labelplus.get_label_bandwidth_usages(list(set(ids)))
      labelplus.common.deferred_timeout(deferred, REQUEST_TIMEOUT, on_timeout,
        process_result, process_result)
    else:
      self._status_item._ebox.hide_all()
      self._calls.append(twisted.internet.reactor.callLater(THROTTLED_INTERVAL,
        self._update_loop))


  def _update_status_bar(self, result):

    if not self._status_item:
      return

    down_rate = sum(result[x][DOWNLOAD_RATE] for x in result)
    down_str = deluge.common.fspeed(down_rate)

    up_rate = sum(result[x][UPLOAD_RATE] for x in result)
    up_str = deluge.common.fspeed(up_rate)

    self._status_item.set_text("%s | %s" % (down_str, up_str))
    self._status_item._ebox.show_all()
