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


import copy
import logging
import datetime
import cPickle

import twisted.internet.reactor
import gobject
import gtk

import deluge.configmanager
import deluge.component
import deluge.plugins.pluginbase
from deluge.ui.client import client

import labelplus.common
import labelplus.common.label
import labelplus.common.config

import labelplus.gtkui.config
import labelplus.gtkui.config.convert


GTKUI_CONFIG = "%s_ui.conf" % labelplus.common.MODULE_NAME

INIT_POLLING_INTERVAL = 3.0

log = logging.getLogger(__name__)
log.addFilter(labelplus.common.LOG_FILTER)


class GtkUI(deluge.plugins.pluginbase.GtkPluginBase):

  # Section: Initialization

  def __init__(self, plugin_name):

    super(GtkUI, self).__init__(plugin_name)

    self.initialized = False
    self.config = None
    self.data = None
    self.store = None
    self.last_updated = None


  def enable(self):

    log.debug("Enabling GtkUI...")

    self._poll_init()


  def _poll_init(self):

    client.labelplus.is_initialized().addCallback(self._check_init)


  def _check_init(self, result):

    log.debug("Waiting for Core to be initialized...")

    if result == True:
      client.labelplus.get_labels_data().addCallback(self._finish_init)
    else:
      twisted.internet.reactor.callLater(INIT_POLLING_INTERVAL,
        self._poll_init)


  def _finish_init(self, result):

    log.debug("Resuming initialization...")

    info = client.connection_info()
    self.daemon = "%s@%s:%s" % (info[2], info[0], info[1])

    self.config = self._load_config()
    self._update_labels(result)

    self.initialized = True

    log.debug("GtkUI enabled")


  # Section: Deinitialization

  def disable(self):

    log.debug("Disabling GtkUI...")

    if self.config:
      if self.initialized:
        self.config.save()

      deluge.configmanager.close(GTKUI_CONFIG)

    self.initialized = False

    log.debug("GtkUI disabled")


  # Section: Update Loops

  def update(self):

    if self.initialized:
      pickled_time = cPickle.dumps(self.last_updated)
      client.labelplus.get_labels_data(pickled_time).addCallback(
        self._update_labels)


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


  # Section: Label: Updates

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
