#
# gtkui.py
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


import cPickle
import copy
import datetime
import logging
import traceback

import gobject
import gtk
import twisted.internet
import twisted.python.failure

import deluge.component
import deluge.configmanager

from deluge.plugins.pluginbase import GtkPluginBase
from deluge.ui.client import client

import labelplus.common
import labelplus.common.config
import labelplus.common.label

import labelplus.gtkui.config
import labelplus.gtkui.config.convert

from labelplus.gtkui.add_torrent_ext import AddTorrentExt
from labelplus.gtkui.torrent_view_ext import TorrentViewExt

from labelplus.gtkui import RT


GTKUI_CONFIG = "%s_ui.conf" % labelplus.common.MODULE_NAME

INIT_POLLING_INTERVAL = 1.0
LABELS_UPDATE_INTERVAL = 1.0


log = logging.getLogger(__name__)


class GtkUI(GtkPluginBase):

  # Section: Initialization

  def __init__(self, plugin_name):

    super(GtkUI, self).__init__(plugin_name)

    self.initialized = False

    self.config = None
    self.data = None
    self.store = None
    self.last_updated = None

    self._ext = []


  def enable(self):

    log.info("Initializing %s...", self.__class__.__name__)

    self._poll_init()


  def _poll_init(self):

    client.labelplus.is_initialized().addCallback(self._check_init)


  def _check_init(self, result):

    log.info("Waiting for core to be initialized...")

    if result == True:
      client.labelplus.get_labels_data().addCallback(self._finish_init)
    else:
      twisted.internet.reactor.callLater(INIT_POLLING_INTERVAL,
        self._poll_init)


  def _finish_init(self, result):

    log.info("Resuming initialization...")

    info = client.connection_info()
    self.daemon = "%s@%s:%s" % (info[2], info[0], info[1])

    self.config = self._load_config()
    self._update_labels(result)

    self._load_extensions()

    self.initialized = True

    log.info("%s initialized", self.__class__.__name__)

    self._labels_update_loop()


  def _load_extensions(self):

    extensions = [
      (AddTorrentExt, (self,)),
      (TorrentViewExt, (self,)),
    ]

    while len(extensions):
      ext = extensions.pop()

      try:
        instance = ext[0](*ext[1])

        if __debug__: RT.register(instance, ext[0].__name__)

        self._ext.append(instance)
      except:
        traceback.print_exc()


  # Section: Deinitialization

  def disable(self):

    log.info("Deinitializing %s...", self.__class__.__name__)

    if self.config:
      if self.initialized:
        self.config.save()

      deluge.configmanager.close(GTKUI_CONFIG)

    self.initialized = False

    self._unload_extensions()

    if __debug__: RT.report()

    log.info("%s deinitialized", self.__class__.__name__)


  def _unload_extensions(self):

    while len(self._ext):
      ext = self._ext.pop()

      try:
        ext.unload()
      except:
        traceback.print_exc()


  # Section: Update Loops

  def _labels_update_loop(self):

    def callback(result):

      if not isinstance(result, twisted.python.failure.Failure):
        self._update_labels(result)

      twisted.internet.reactor.callLater(LABELS_UPDATE_INTERVAL,
        self._labels_update_loop)


    if self.initialized:
      pickled_time = cPickle.dumps(self.last_updated)
      client.labelplus.get_labels_data(pickled_time).addCallbacks(
        callback, callback)


  # Section: General

  def get_extension(self, name):

    for ext in self._ext:
      if ext.__class__.__name__ == name:
        return ext

    return None


  def is_valid_label(self, id, name):

    basename = labelplus.common.label.resolve_name_by_degree(name, degree=1)

    return (id not in labelplus.common.label.RESERVED_IDS and
      id in self.data and self.data[id]["name"] == basename)


  # Section: Config

  def _load_config(self):

    config = deluge.configmanager.ConfigManager(GTKUI_CONFIG)

    # Workaround for version that didn't use header
    if config.config.get("version") == 2:
      labelplus.common.config.set_version(config, 2)

    labelplus.common.config.init_config(config,
      labelplus.gtkui.config.CONFIG_DEFAULTS,
      labelplus.gtkui.config.CONFIG_VERSION,
      labelplus.gtkui.config.convert.CONFIG_SPECS)

    self._update_daemon_config(config)
    self._normalize_config(config)

    return config


  def _update_daemon_config(self, config):

    saved_daemons = deluge.component.get("ConnectionManager").config["hosts"]
    if not saved_daemons:
      config["daemon"] = {}
    else:
      daemons = ["%s@%s:%s" % (x[3], x[1], x[2]) for x in saved_daemons]

      # Remove daemons from config if not in ConnectionManager hosts
      for daemon in config["daemon"].keys():
        if "@localhost:" in daemon or "@127.0.0.1:" in daemon:
          continue

        if daemon not in daemons and daemon != self.daemon:
          del config["daemon"][daemon]

    if self.daemon not in config["daemon"]:
      config["daemon"][self.daemon] = copy.deepcopy(
        labelplus.gtkui.config.DAEMON_DEFAULTS)


  def _normalize_config(self, config):

    labelplus.common.normalize_dict(config.config,
      labelplus.gtkui.config.CONFIG_DEFAULTS)

    labelplus.common.normalize_dict(config.config["common"],
      labelplus.gtkui.config.CONFIG_DEFAULTS["common"])

    for daemon in config.config["daemon"]:
      labelplus.common.normalize_dict(config.config["daemon"][daemon],
        labelplus.gtkui.config.DAEMON_DEFAULTS)


  # Section: Label: Update

  def _update_labels(self, result):

    if not result:
      return

    self.last_updated = datetime.datetime.now()
    self.data = result

    id = labelplus.common.label.ID_ALL
    self.data[id]["name"] = _(id)

    id = labelplus.common.label.ID_NONE
    self.data[id]["name"] = _(id)

    self._build_store()
    self._build_fullname_index()


  def _build_store(self):

    def label_sort_asc(model, iter1, iter2):

      id1, data1 = model[iter1]
      id2, data2 = model[iter2]

      is_reserved1 = id1 in labelplus.common.label.RESERVED_IDS
      is_reserved2 = id2 in labelplus.common.label.RESERVED_IDS

      if is_reserved1 and is_reserved2:
        return cmp(id1, id2)
      elif is_reserved1:
        return -1
      elif is_reserved2:
        return 1

      return cmp(data1["name"], data2["name"])


    store = gtk.TreeStore(str, gobject.TYPE_PYOBJECT)
    store_map = {}

    for id in sorted(self.data):
      if id in labelplus.common.label.RESERVED_IDS:
        parent_id = labelplus.common.label.ID_NULL
      else:
        parent_id = labelplus.common.label.get_parent_id(id)

      parent_iter = store_map.get(parent_id)
      iter = store.append(parent_iter, [id, self.data[id]])
      store_map[id] = iter

    sorted_store = gtk.TreeModelSort(store)
    sorted_store.set_sort_func(1, label_sort_asc)
    sorted_store.set_sort_column_id(1, gtk.SORT_ASCENDING)

    self.store = sorted_store


  def _build_fullname_index(self):

    def resolve_fullname(id):

      parts = []

      while id:
        parts.append(self.data[id]["name"])
        id = labelplus.common.label.get_parent_id(id)

      return "/".join(reversed(parts))


    for id in self.data:
      self.data[id]["fullname"] = resolve_fullname(id)
