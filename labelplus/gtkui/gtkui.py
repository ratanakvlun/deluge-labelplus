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

import gtk
import gobject
import twisted.internet.reactor

import deluge.configmanager
import deluge.component
import deluge.plugins.pluginbase
from deluge.ui.client import client

import labelplus.common
import labelplus.common.label
import labelplus.common.config
import labelplus.common.config.convert

import labelplus.gtkui.config
import labelplus.gtkui.config.convert
import labelplus.gtkui.util


GTKUI_CONFIG = "%s_ui.conf" % labelplus.common.MODULE_NAME

INIT_POLLING_INTERVAL = 3.0

log = logging.getLogger(__name__)
log.addFilter(labelplus.common.LOG_FILTER)


class GtkUI(deluge.plugins.pluginbase.GtkPluginBase):

  # Section: Initialization

  def __init__(self, plugin_name):

    super(GtkUI, self).__init__(plugin_name)
    self._initialized = False
    self._config = None


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
    self._daemon = "%s@%s:%s" % (info[2], info[0], info[1])

    self._config = self._load_config()

    self._store = None
    self._store_map = None
    self._sorted_store = None

    self._last_updated = None
    self._update_labels(result)

    self._initialized = True

    log.debug("GtkUI enabled")


  # Section: Deinitialization

  def disable(self):

    log.debug("Disabling GtkUI...")

    if self._config:
      if self._initialized:
        self._config.save()

      deluge.configmanager.close(GTKUI_CONFIG)

    self._initialized = False

    log.debug("GtkUI disabled")


  # Section: Update Loops

  def update(self):

    if self._initialized:
      client.labelplus.get_labels_data(self._last_updated).addCallback(
        self._update_labels)


  # Section: Config

  def _load_config(self):

    config = deluge.configmanager.ConfigManager(GTKUI_CONFIG)

    # Workaround for versions that didn't use header
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

      for daemon in config["daemon"].keys():
        if "@localhost:" in daemon or "@127.0.0.1:" in daemon:
          continue

        if daemon != self._daemon and daemon not in daemons:
          del config["daemon"][daemon]

    if self._daemon not in config["daemon"]:
      config["daemon"][self._daemon] = copy.deepcopy(
        labelplus.gtkui.config.DAEMON_DEFAULTS)


  # Section: Label

  def _label_sort_asc(self, store, iter_a, iter_b):

    id_a, data_a = store.get(iter_a, 0, 1)
    id_b, data_b = store.get(iter_b, 0, 1)

    a_is_reserved = id_a in labelplus.common.label.RESERVED_IDS
    b_is_reserved = id_b in labelplus.common.label.RESERVED_IDS

    if a_is_reserved and b_is_reserved:
      return cmp(id_a, id_b)
    elif a_is_reserved:
      return -1
    elif b_is_reserved:
      return 1

    return cmp(data_a["name"], data_b["name"])


  def _update_labels(self, result):

    if not result:
      return

    self._last_updated = cPickle.dumps(datetime.datetime.now())
    self._labels_data = result

    name = self._labels_data[labelplus.common.label.ID_ALL]["name"]
    self._labels_data[labelplus.common.label.ID_ALL]["name"] = _(name)

    name = self._labels_data[labelplus.common.label.ID_NONE]["name"]
    self._labels_data[labelplus.common.label.ID_NONE]["name"] = _(name)

    store = gtk.TreeStore(str, gobject.TYPE_PYOBJECT)
    store_map = {}

    for id in sorted(self._labels_data):
      if id in labelplus.common.label.RESERVED_IDS:
        parent_id = labelplus.common.label.NULL_PARENT
      else:
        parent_id = labelplus.common.label.get_parent_id(id)

      parent_iter = store_map.get(parent_id)
      iter = store.append(parent_iter, [id, self._labels_data[id]])
      store_map[id] = iter

    sorted_store = gtk.TreeModelSort(store)
    sorted_store.set_sort_func(1, self._label_sort_asc)
    sorted_store.set_sort_column_id(1, gtk.SORT_ASCENDING)

    self._store = store
    self._store_map = store_map
    self._sorted_store = sorted_store
