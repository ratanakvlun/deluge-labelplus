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

import twisted.internet

import deluge.component
import deluge.configmanager

import labelplus.common
import labelplus.common.config
import labelplus.common.label
import labelplus.gtkui.config
import labelplus.gtkui.config.convert


from twisted.python.failure import Failure

from deluge.ui.client import client
from deluge.ui.client import DelugeRPCError
from deluge.plugins.pluginbase import GtkPluginBase

from labelplus.common import LabelPlusError
from labelplus.gtkui.label_store import LabelStore
from labelplus.gtkui.add_torrent_ext import AddTorrentExt
#from labelplus.gtkui.torrent_view_ext import TorrentViewExt
#from labelplus.gtkui.side_bar_ext import SideBarExt
#from labelplus.gtkui.status_bar_ext import StatusBarExt

from labelplus.gtkui import RT


from labelplus.common.literals import (
  STR_UPDATE, ERR_TIMED_OUT,
)

GTKUI_CONFIG = "%s_ui.conf" % labelplus.common.MODULE_NAME

INIT_POLLING_INTERVAL = 3.0
UPDATE_INTERVAL = 1.0

THROTTLED_INTERVAL = 5.0
MAX_TRIES = 10

REQUEST_TIMEOUT = 10


log = logging.getLogger(__name__)


class GtkUI(GtkPluginBase):

  # Section: Initialization

  def __init__(self, plugin_name):#

    RT.register(self)
    RT.logger = logging.getLogger(__name__ + ".rt")
    RT.logger.setLevel(logging.INFO)

    super(GtkUI, self).__init__(plugin_name)

    self.initialized = False

    self.config = None

    self.store = LabelStore()
    self.last_updated = None
    self._tries = 0

    self._extensions = []

    self._calls = []

    self._update_funcs = []
    self._cleanup_funcs = []

  def enable(self):#

    log.info("Initializing %s...", self.__class__.__name__)

    self._poll_init()


  def _poll_init(self):#

    client.labelplus.is_initialized().addCallback(self._check_init)


  def _check_init(self, result):#

    log.info("Waiting for core to be initialized...")

    if result == True:
      client.labelplus.get_labels_data().addCallback(self._finish_init)
    else:
      twisted.internet.reactor.callLater(INIT_POLLING_INTERVAL,
        self._poll_init)


  def _finish_init(self, result):

    log.info("Resuming initialization...")

    try:
      info = client.connection_info()
      self.daemon = "%s@%s:%s" % (info[2], info[0], info[1])

      self.config = self._load_config()

      self._update_store(result)

      self._load_extensions()

      self.initialized = True

      log.info("%s initialized", self.__class__.__name__)
    except:
      log.error("Error initializing %s", self.__class__.__name__)
      raise

    self._update_loop()
    self.testing()


  def _load_extensions(self):#

    extensions = [
      #(AddTorrentExt, (self,)),
    ]

    for ext in extensions:
      try:
        instance = ext[0](*ext[1])

        RT.register(instance, ext[0].__name__)

        self._extensions.append(instance)
      except:
        pass


  def testing(self):

    log.debug("Testing Start")

    from labelplus.gtkui.name_input_dialog import AddLabelDialog
    from labelplus.gtkui.name_input_dialog import RenameLabelDialog
    from labelplus.gtkui.label_selection_menu import LabelSelectionMenu
    from labelplus.gtkui.label_options_dialog import LabelOptionsDialog

    a = AddLabelDialog(self, self.store)
    RT.register(a)
    a.show()
    del a

    #a = RenameLabelDialog(self, self.store, "0")
    #RT.register(a)
    #a.show()
    #del a

    a = LabelOptionsDialog(self, self.store, "0")
    RT.register(a)
    a.show()
    del a
    #for x in self.store:
    #  log.debug("ID: %r", x)

    #for x in self.store:
    #  log.debug("Name: %r", self.store[x]["name"])

    RT.report()

    log.debug("Testing End")


  # Section: Deinitialization

  def disable(self):#

    log.info("Deinitializing %s...", self.__class__.__name__)

    labelplus.common.cancel_calls(self._calls)

    if self.config:
      if self.initialized:
        self.config.save()

      deluge.configmanager.close(GTKUI_CONFIG)

    self.initialized = False

    self._run_cleanup_funcs()

    self._unload_extensions()

    self._destroy_store()

    RT.report()

    log.info("%s deinitialized", self.__class__.__name__)


  def _run_cleanup_funcs(self):

    log.debug("Cleaning up...")

    while self._cleanup_funcs:
      func = self._cleanup_funcs.pop()

      try:
        func()
      except:
        pass


  def _unload_extensions(self):

    while self._extensions:
      ext = self._extensions.pop()

      try:
        ext.unload()
      except:
        pass


  def _destroy_store(self):

    log.debug("Destroying store...")

    self.store.destroy()
    self.store = None


  # Section: Public

  def get_extension(self, name):#

    for ext in self._extensions:
      if ext.__class__.__name__ == name:
        return ext

    return None


  def register_update_func(self, func):

    if func not in self._update_funcs:
      self._update_funcs.append(func)


  def deregister_update_func(self, func):

    if func in self._update_funcs:
      self._update_funcs.remove(func)


  def register_cleanup_func(self, func):

    if func not in self._cleanup_funcs:
      self._cleanup_funcs.append(func)


  def deregister_cleanup_func(self, func):

    if func in self._cleanup_funcs:
      self._cleanup_funcs.remove(func)


  # Section: Config

  def _load_config(self):#

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


  def _update_daemon_config(self, config):#

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


  def _normalize_config(self, config):#

    labelplus.common.normalize_dict(config.config,
      labelplus.gtkui.config.CONFIG_DEFAULTS)

    labelplus.common.normalize_dict(config["common"],
      labelplus.gtkui.config.CONFIG_DEFAULTS["common"])

    for daemon in config["daemon"]:
      labelplus.common.normalize_dict(config["daemon"][daemon],
        labelplus.gtkui.config.DAEMON_DEFAULTS)


  # Section: Update

  def _update_loop(self):

    def on_timeout():

      log.error("%s: %s", STR_UPDATE, LabelPlusError(ERR_TIMED_OUT))

      if self.initialized:
        self._tries += 1
        if self._tries < MAX_TRIES:
          twisted.internet.reactor.callLater(THROTTLED_INTERVAL,
            self._update_loop)
        else:
          log.error("%s: %s", STR_UPDATE,
            LabelPlusError("Max update retries reached"))


    def process_result(result):

      if isinstance(result, Failure):
        if (isinstance(result.value, DelugeRPCError) and
            result.value.exception_type == "LabelPlusError"):
          log.error("%s: %s", STR_UPDATE,
            LabelPlusError(result.value.exception_msg))
      else:
        self._tries = 0
        self._update_store(result)

      if self.initialized:
        twisted.internet.reactor.callLater(UPDATE_INTERVAL, self._update_loop)


    if self.initialized:
      pickled_time = cPickle.dumps(self.last_updated)
      deferred = client.labelplus.get_labels_data(pickled_time)
      labelplus.common.deferred_timeout(deferred, REQUEST_TIMEOUT, on_timeout,
        process_result, process_result)


  def _update_store(self, result):#

    if not result:
      return

    self.last_updated = datetime.datetime.now()
    self.store.update(result)

    for func in self._update_funcs:
      func(self.store)
