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
#   The Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor
#   Boston, MA  02110-1301, USA.
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


import logging
import copy
import os.path
import cPickle
import datetime
import re

from twisted.internet import reactor

import deluge.common
import deluge.configmanager
from deluge import component
from deluge.core.rpcserver import export
from deluge.plugins.pluginbase import CorePluginBase

import labelplus.common
import labelplus.common.config
import labelplus.core.config

from labelplus.common import (
  PLUGIN_NAME, MODULE_NAME,
  STATUS_ID, STATUS_NAME,
  NULL_PARENT, ID_ALL, ID_NONE, RESERVED_IDS,
)

from labelplus.core.config import (
  CONFIG_DEFAULTS,
  OPTION_DEFAULTS,
  LABEL_DEFAULTS,
)


CORE_CONFIG = "%s.conf" % MODULE_NAME

log = logging.getLogger(__name__)
log.addFilter(labelplus.common.LOG_FILTER)


def init_check(func):

  def wrap(*args, **kwargs):

    if len(args) > 0 and isinstance(args[0], Core):
      if not args[0]._initialized:
        raise RuntimeError("Plugin %r not initialized" % PLUGIN_NAME)

    return func(*args, **kwargs)


  return wrap


class Core(CorePluginBase):

  # Section: Initialization

  def __init__(self, plugin_name):

    super(Core, self).__init__(plugin_name)
    self._initialized = False


  def enable(self):

    log.debug("Initializing Core...")

    self._core = deluge.configmanager.ConfigManager("core.conf")
    self._config = self._load_config()

    self._prefs = self._config["prefs"]
    self._labels = self._config["labels"]
    self._mappings = self._config["mappings"]

    self._sorted_labels = {}

    self._timestamp = {
      "labels_changed": datetime.datetime.now(),
      "mappings_changed": datetime.datetime.now(),
      "labels_sorted": datetime.datetime(1, 1, 1),
    }

    if not component.get("TorrentManager").session_started:
      component.get("EventManager").register_event_handler(
          "SessionStartedEvent", self._initialize)
      log.debug("Waiting for session to start...")
    else:
      self._initialize()


  def _load_config(self):

    config = deluge.configmanager.ConfigManager(CORE_CONFIG,
      defaults=copy.deepcopy(CONFIG_DEFAULTS))

    ver = labelplus.common.config.get_version(config)
    while ver != labelplus.core.config.CONFIG_VERSION:
      if ver < labelplus.core.config.CONFIG_VERSION:
        key = (ver, ver+1)
      else:
        key = (ver, ver-1)

      spec = labelplus.core.config.CONFIG_SPECS.get(key)
      if spec:
        labelplus.common.config.convert(spec, config)
        ver = labelplus.common.config.get_version(config)
      else:
        raise ValueError("Config file conversion v%s->v%s unsupported" % key)

    for key in config.config.keys():
      if key not in CONFIG_DEFAULTS:
        del config.config[key]

    return config


  def _initialize(self):

    component.get("EventManager").deregister_event_handler(
        "SessionStartedEvent", self._initialize)

    self._torrents = component.get("TorrentManager").torrents

    self._remove_reserved_ids()
    self._build_index()
    self._initialize_data()
    self._remove_orphans()

    component.get("FilterManager").register_filter(
        STATUS_ID, self._filter_by_label)

    component.get("CorePluginManager").register_status_field(
        STATUS_NAME, self._get_torrent_label_name)
    component.get("CorePluginManager").register_status_field(
        STATUS_ID, self._get_torrent_label)

    component.get("EventManager").register_event_handler(
        "TorrentAddedEvent", self.on_torrent_added)
    component.get("EventManager").register_event_handler(
        "PreTorrentRemovedEvent", self.on_torrent_removed)

    component.get("AlertManager").register_handler(
        "torrent_finished_alert", self.on_torrent_finished)

    self._last_modified = datetime.datetime.now()
    self._initialized = True

    reactor.callLater(1, self._shared_limit_update)

    log.debug("Core initialized")


  def _remove_reserved_ids(self):

    for id in RESERVED_IDS:
      if id in self._labels:
        del self._labels[id]


  def _build_index(self):

    def build_label_index(id):

      children = []
      torrents = []

      for child_id in self._labels:
        if child_id == id: continue

        if labelplus.common.get_parent(child_id) == id:
          children.append(child_id)

      for torrent_id in self._mappings:
        if self._mappings[torrent_id] == id:
          torrents.append(torrent_id)

      label_index = {
        "children": children,
        "torrents": torrents,
      }

      return label_index


    index = {}
    shared_limit_index = []

    for id in self._labels:
      index[id] = build_label_index(id)

      if (self._labels[id]["data"]["bandwidth_settings"] and
          self._labels[id]["data"]["shared_limit_on"]):
        shared_limit_index.append(id)

    self._index = index
    self._shared_limit_index = shared_limit_index

    for id in self._labels:
      self._build_label_ancestry(id)


  def _initialize_data(self):

    self._normalize_options(self._prefs["options"])
    self._normalize_label_data(self._prefs["defaults"])

    for id in self._labels:
      self._normalize_label_data(self._labels[id]["data"])

    for id in self._mappings.keys():
      if id not in self._torrents:
        del self._mappings[id]
        continue

      if self._mappings[id] in self._labels:
        self._apply_torrent_options(id)
      else:
        self._reset_torrent_options(id)
        del self._mappings[id]


  def _remove_orphans(self):

    removals = []

    for id in self._labels:
      parent_id = labelplus.common.get_parent(id)
      if parent_id != NULL_PARENT and parent_id not in self._labels:
        removals.append(id)

    for id in removals:
      self._remove_label(id)


  # Section: Deinitialization

  def disable(self):

    log.debug("Deinitializing Core...")

    component.get("EventManager").deregister_event_handler(
        "SessionStartedEvent", self._initialize)

    self._initialized = False

    self._config.save()
    deluge.configmanager.close(CORE_CONFIG)

    component.get("EventManager").deregister_event_handler(
        "TorrentAddedEvent", self.on_torrent_added)
    component.get("EventManager").deregister_event_handler(
        "PreTorrentRemovedEvent", self.on_torrent_removed)

    component.get("AlertManager").deregister_handler(
        self.on_torrent_finished)

    component.get("CorePluginManager").deregister_status_field(STATUS_ID)
    component.get("CorePluginManager").deregister_status_field(STATUS_NAME)

    component.get("FilterManager").deregister_filter(STATUS_ID)

    self._rpc_deregister(PLUGIN_NAME)

    log.debug("Core deinitialized")


  def _rpc_deregister(self, name):

    server = component.get("RPCServer")
    name = name.lower()

    for d in dir(self):
      if d[0] == "_": continue

      if getattr(getattr(self, d), '_rpcserver_export', False):
        method = "%s.%s" % (name, d)
        log.debug("Deregistering method: %s", method)
        if method in server.factory.methods:
          del server.factory.methods[method]


  # Section: Public API

  @export
  def is_initialized(self):

    return self._initialized


  @export
  @init_check
  def add_label(self, parent_id, label_name):

    if parent_id != NULL_PARENT and parent_id not in self._labels:
      raise ValueError("Unknown label: %r" % parent_id)

    label_name = label_name.strip()
    self._validate_name(parent_id, label_name)

    id = self._get_unused_id(parent_id)
    self._index[parent_id]["children"].append(id)

    self._labels[id] = {
      "name": label_name,
      "data": copy.deepcopy(self._prefs["defaults"]),
    }

    self._index[id] = {
      "children": [],
      "torrents": [],
    }

    options = self._labels[id]["data"]
    mode = options["move_data_completed_mode"]
    if mode != "folder":
      path = self.get_parent_path(id)

      if mode == "subfolder":
        path = os.path.join(path, label_name)

      options["move_data_completed_path"] = path

    self._build_label_ancestry(id)

    self._last_modified = datetime.datetime.now()
    self._config.save()

    return id


  @export
  @init_check
  def remove_label(self, label_id):

    if label_id in RESERVED_IDS or label_id not in self._labels:
      raise ValueError("Unknown label: %r" % label_id)

    self._remove_label(label_id)

    parent_id = labelplus.common.get_parent(label_id)
    self._index[parent_id]["children"].remove(label_id)

    self._last_modified = datetime.datetime.now()
    self._config.save()


  @export
  @init_check
  def rename_label(self, label_id, label_name):

    if label_id in RESERVED_IDS or label_id not in self._labels:
      raise ValueError("Unknown label: %r" % label_id)

    label_name = label_name.strip()
    self._validate_name(labelplus.common.get_parent(label_id), label_name)

    obj = self._labels[label_id]
    obj["name"] = label_name

    self._clear_subtree_ancestry(label_id)

    if obj["data"]["move_data_completed_mode"] == "subfolder":
      path = os.path.join(self.get_parent_path(label_id), label_name)
      obj["data"]["move_data_completed_path"] = path

      self._apply_data_completed_path(label_id)
      self._propagate_path_to_descendents(label_id)

    self._last_modified = datetime.datetime.now()
    self._config.save()

    if (obj["data"]["move_data_completed_mode"] == "subfolder" and
        self._prefs["options"]["move_on_changes"]):
      self._subtree_move_completed(label_id)


  @export
  @init_check
  def get_label_data(self, timestamp):

    if timestamp:
      t = cPickle.loads(timestamp)
    else:
      t = datetime.datetime(1, 1, 1)

    if t < self._last_modified:
      return (cPickle.dumps(self._last_modified), self._get_label_counts())
    else:
      return None


  @export
  @init_check
  def set_options(self, label_id, options_in):

    if label_id in RESERVED_IDS or label_id not in self._labels:
      raise ValueError("Unknown label: %r" % label_id)

    retroactive = options_in.get("tmp_auto_retroactive", False)
    unlabeled_only = options_in.get("tmp_auto_unlabeled", True)

    options = self._labels[label_id]["data"]

    old_download = options["download_settings"]
    old_move = options["move_data_completed"]
    old_move_path = options["move_data_completed_path"]

    self._normalize_label_data(options_in)
    options.update(options_in)

    self._config.save()

    for id in self._index[label_id]["torrents"]:
      self._apply_torrent_options(id)

    if label_id in self._shared_limit_index:
      self._shared_limit_index.remove(label_id)

    if options["bandwidth_settings"] and options["shared_limit_on"]:
      self._shared_limit_index.append(label_id)

    # Make sure descendent labels are updated if path changed
    if old_move_path != options["move_data_completed_path"]:
      self._propagate_path_to_descendents(label_id)

      self._config.save()

      if self._prefs["options"]["move_on_changes"]:
        self._subtree_move_completed(label_id)
    else:
      # If move completed was just turned on...
      if (options["download_settings"] and
          options["move_data_completed"] and
          (not old_download or not old_move) and
          self._prefs["options"]["move_on_changes"]):
        self._do_move_completed(label_id, self._index[label_id]["torrents"])

    if options["auto_settings"] and retroactive:
      autolabel = []
      for torrent_id in self._torrents:
        if not unlabeled_only or torrent_id not in self._mappings:
          if self._has_auto_apply_match(label_id, torrent_id):
            autolabel.append(torrent_id)

      if autolabel:
        self.set_torrent_labels(label_id, autolabel)

    self._last_modified = datetime.datetime.now()
    self._config.save()


  @export
  @init_check
  def get_options(self, label_id):

    if label_id in RESERVED_IDS or label_id not in self._labels:
      raise ValueError("Unknown label: %r" % label_id)

    return self._labels[label_id]["data"]


  @export
  @init_check
  def set_preferences(self, prefs):

    self._normalize_options(prefs["options"])
    self._prefs["options"].update(prefs["options"])

    self._normalize_label_data(prefs["defaults"])
    self._prefs["defaults"].update(prefs["defaults"])

    self._last_modified = datetime.datetime.now()
    self._config.save()


  @export
  @init_check
  def get_preferences(self):

    return self._prefs


  @export
  @init_check
  def get_parent_path(self, label_id):

    if label_id in RESERVED_IDS or label_id not in self._labels:
      raise ValueError("Unknown label: %r" % label_id)

    parent_id = labelplus.common.get_parent(label_id)
    if parent_id == NULL_PARENT:
      path = self._get_default_save_path()
    else:
      path = self._labels[parent_id]["data"]["move_data_completed_path"]

    return path


  @export
  @init_check
  def set_torrent_labels(self, label_id, torrent_list):

    if not label_id:
      label_id = ID_NONE

    if (label_id != ID_NONE and label_id in RESERVED_IDS or
        label_id not in self._labels):
      raise ValueError("Unknown label: %r" % label_id)

    torrents = [t for t in torrent_list if t in self._torrents]
    for id in torrents:
      self._set_torrent_label(id, label_id)

    self._last_modified = datetime.datetime.now()
    self._config.save()

    if self._prefs["options"]["move_on_changes"]:
      self._do_move_completed(label_id, torrents)


  @export
  @init_check
  def get_torrent_label(self, torrent_id):

    return self._get_torrent_label(torrent_id)


  @export
  @init_check
  def get_label_bandwidth_usage(self, label_id, sublabels=False):

    if (label_id != ID_NONE and label_id in RESERVED_IDS or
        label_id not in self._labels):
      raise ValueError("Unknown label: %r" % label_id)

    if not label_id:
      label_id = ID_NONE

    labels = [label_id]

    if label_id != ID_NONE and sublabels:
      labels += self._get_descendent_labels(label_id)

    active_torrents = self._get_labeled_torrents_status(
      labels, {"state": ["Seeding", "Downloading"]},
      ["download_payload_rate", "upload_payload_rate"])

    return self._get_bandwidth_usage(active_torrents)


  @export
  @init_check
  def get_daemon_vars(self):

    vars = {
      "os_path_module": os.path.__name__,
    }

    return vars


  # Section: Event Handlers

  def on_torrent_added(self, torrent_id):

    def cmp_len_then_value(x, y):

      if len(x) > len(y): return -1
      if len(x) < len(y): return 1
      return cmp(x, y)

    labels = sorted(self._labels, cmp=cmp_len_then_value)

    for label_id in labels:
      if label_id == NULL_PARENT: continue

      if self._labels[label_id]["data"]["auto_settings"]:
        if self._has_auto_apply_match(label_id, torrent_id):
          self._set_torrent_label(torrent_id, label_id)
          log.debug("Torrent %r is labeled %r", torrent_id, label_id)

          self._config.save()

          break

    self._last_modified = datetime.datetime.now()


  def on_torrent_removed(self, torrent_id):

    if torrent_id in self._mappings:
      label_id = self._mappings[torrent_id]
      self._index[label_id]["torrents"].remove(torrent_id)
      del self._mappings[torrent_id]
      log.debug("Torrent %r removed from label %r", torrent_id, label_id)

      self._config.save()

    self._last_modified = datetime.datetime.now()


  def on_torrent_finished(self, alert):

    torrent_id = str(alert.handle.info_hash())

    if torrent_id in self._mappings:
      log.debug("Labeled torrent %r has finished", torrent_id)

      if self._prefs["options"]["move_after_recheck"]:
        # Try to move in case this alert was from a recheck
        label_id = self._mappings[torrent_id]
        self._do_move_completed(label_id, [torrent_id])


  # Section: General

  @export
  @init_check
  def get_daemon_vars(self):

    vars = {
      "os_path_module": os.path.__name__,
    }

    return vars

  def _get_default_save_path(self):

    path = self._core["download_location"]
    if not path:
      path = deluge.common.get_default_download_dir()

    return path


  # Section: Maintenance

  def _normalize_options(self, options):

    for key in options.keys():
      if key not in OPTION_DEFAULTS:
        del options[key]

    for key in OPTION_DEFAULTS:
      if key not in options:
        options[key] = OPTION_DEFAULTS[key]

    if options["shared_limit_update_interval"] < 1:
      options["shared_limit_update_interval"] = 1


  def _normalize_label_data(self, data):

    for key in data.keys():
      if key not in LABEL_DEFAULTS:
        del data[key]

    for key in LABEL_DEFAULTS:
      if key not in data:
        data[key] = LABEL_DEFAULTS[key]

    data["move_data_completed_path"] = \
        data["move_data_completed_path"].strip()
    if not data["move_data_completed_path"]:
      data["move_data_completed_path"] = \
        self._core["move_completed_path"] or self._get_default_save_path()

    queries = [line for line in data["auto_queries"] if line.strip()]
    data["auto_queries"] = queries

    if data["max_download_speed"] == 0.0:
      data["max_download_speed"] = LABEL_DEFAULTS["max_download_speed"]

    if data["max_upload_speed"] == 0.0:
      data["max_upload_speed"] = LABEL_DEFAULTS["max_upload_speed"]

    if data["max_connections"] == 0:
      data["max_connections"] = LABEL_DEFAULTS["max_connections"]

    if data["max_upload_slots"] == 0:
      data["max_upload_slots"] = LABEL_DEFAULTS["max_upload_slots"]

    if data["stop_ratio"] < 0.0:
      data["stop_ratio"] = LABEL_DEFAULTS["stop_ratio"]


  # Section: Preference: Queries

  @export
  @init_check
  def get_options(self, label_id):

    if label_id in RESERVED_IDS or label_id not in self._labels:
      raise ValueError("Unknown label: %r" % label_id)

    return self._labels[label_id]["data"]


  @export
  @init_check
  def get_preferences(self):

    return self._prefs


  # Section: Preference: Modifiers

  @export
  @init_check
  def set_options(self, label_id, options_in):

    if label_id in RESERVED_IDS or label_id not in self._labels:
      raise ValueError("Unknown label: %r" % label_id)

    retroactive = options_in.get("tmp_auto_retroactive", False)
    unlabeled_only = options_in.get("tmp_auto_unlabeled", True)

    options = self._labels[label_id]["data"]

    old_download = options["download_settings"]
    old_move = options["move_data_completed"]
    old_move_path = options["move_data_completed_path"]

    self._normalize_label_data(options_in)
    options.update(options_in)

    self._config.save()

    for id in self._index[label_id]["torrents"]:
      self._apply_torrent_options(id)

    if label_id in self._shared_limit_index:
      self._shared_limit_index.remove(label_id)

    if options["bandwidth_settings"] and options["shared_limit_on"]:
      self._shared_limit_index.append(label_id)

    # Make sure descendent labels are updated if path changed
    if old_move_path != options["move_data_completed_path"]:
      self._propagate_path_to_descendents(label_id)

      self._config.save()

      if self._prefs["options"]["move_on_changes"]:
        self._subtree_move_completed(label_id)
    else:
      # If move completed was just turned on...
      if (options["download_settings"] and
          options["move_data_completed"] and
          (not old_download or not old_move) and
          self._prefs["options"]["move_on_changes"]):
        self._do_move_completed(label_id, self._index[label_id]["torrents"])

    if options["auto_settings"] and retroactive:
      autolabel = []
      for torrent_id in self._torrents:
        if not unlabeled_only or torrent_id not in self._mappings:
          if self._has_auto_apply_match(label_id, torrent_id):
            autolabel.append(torrent_id)

      if autolabel:
        self.set_torrent_labels(label_id, autolabel)

    self._last_modified = datetime.datetime.now()
    self._config.save()


  @export
  @init_check
  def set_preferences(self, prefs):

    self._normalize_options(prefs["options"])
    self._prefs["options"].update(prefs["options"])

    self._normalize_label_data(prefs["defaults"])
    self._prefs["defaults"].update(prefs["defaults"])

    self._last_modified = datetime.datetime.now()
    self._config.save()


  # Section: Label: Queries

  @export
  @init_check
  def get_parent_path(self, label_id):

    if label_id in RESERVED_IDS or label_id not in self._labels:
      raise ValueError("Unknown label: %r" % label_id)

    parent_id = labelplus.common.get_parent(label_id)
    if parent_id == NULL_PARENT:
      path = self._get_default_save_path()
    else:
      path = self._labels[parent_id]["data"]["move_data_completed_path"]

    return path

  def _get_unused_id(self, parent_id):

    i = 0
    label_obj = {}
    while label_obj is not None:
      id = "%s:%s" % (parent_id, i)
      label_obj = self._labels.get(id)
      i += 1

    return id


  def _validate_name(self, parent_id, label_name):

    labelplus.common.validate_name(label_name)

    names = self._get_children_names(parent_id)
    if label_name in names:
      raise ValueError("Label already exists: %r" % label_name)


  def _get_descendent_labels(self, label_id):

    descendents = []

    if label_id in self._index:
      for child in self._index[label_id]["children"]:
        descendents.append(child)
        descendents += self._get_descendent_labels(child)

    return descendents


  def _get_children_names(self, parent_id):

    names = []
    for id in self._index[parent_id]["children"]:
      names.append(self._labels[id]["name"])

    return names


  @export
  @init_check
  def get_label_data(self, timestamp):

    if timestamp:
      t = cPickle.loads(timestamp)
    else:
      t = datetime.datetime(1, 1, 1)

    if t < self._last_modified:
      return (cPickle.dumps(self._last_modified), self._get_label_counts())
    else:
      return None

  def _get_label_counts(self):

    label_count = 0
    counts = {}
    for id in sorted(self._labels, reverse=True):
      if id == NULL_PARENT: continue

      count = len(self._index[id]["torrents"])
      label_count += count

      if self._prefs["options"]["include_children"]:
        for child in self._index[id]["children"]:
          count += counts[child]["count"]

      full_name = self._get_label_ancestry(id)

      counts[id] = {
        "name": self._labels[id]["name"],
        "count": count,
        "full_name": full_name,
      }

    total = len(self._torrents)
    counts[ID_ALL] = {
      "name": ID_ALL,
      "count": total,
      "full_name": ID_ALL,
    }

    counts[ID_NONE] = {
      "name": ID_NONE,
      "count": total-label_count,
      "full_name": ID_NONE,
    }

    return counts


  @export
  @init_check
  def get_label_bandwidth_usage(self, label_id, sublabels=False):

    if (label_id != ID_NONE and label_id in RESERVED_IDS or
        label_id not in self._labels):
      raise ValueError("Unknown label: %r" % label_id)

    if not label_id:
      label_id = ID_NONE

    labels = [label_id]

    if label_id != ID_NONE and sublabels:
      labels += self._get_descendent_labels(label_id)

    active_torrents = self._get_labeled_torrents_status(
      labels, {"state": ["Seeding", "Downloading"]},
      ["download_payload_rate", "upload_payload_rate"])

    return self._get_bandwidth_usage(active_torrents)


  def _get_sorted_labels(self, cmp_func=None, reverse=False):

    last_sorted = self._timestamp["labels_sorted"]
    last_changed = self._timestamp["labels_changed"]

    if last_sorted < last_changed:
      self._sorted_labels.clear()

    key = (cmp_func, reverse)

    if key not in self._sorted_labels:
      self._sorted_labels[key] = sorted(self._labels,
        cmp=key[0], reverse=key[1])

      self._timestamp["labels_sorted"] = datetime.datetime.now()

    return self._sorted_labels[key]


  # Section: Label: Modifiers

  @export
  @init_check
  def add_label(self, parent_id, label_name):

    if parent_id != NULL_PARENT and parent_id not in self._labels:
      raise ValueError("Unknown label: %r" % parent_id)

    label_name = label_name.strip()
    self._validate_name(parent_id, label_name)

    id = self._get_unused_id(parent_id)
    self._index[parent_id]["children"].append(id)

    self._labels[id] = {
      "name": label_name,
      "data": copy.deepcopy(self._prefs["defaults"]),
    }

    self._index[id] = {
      "children": [],
      "torrents": [],
    }

    options = self._labels[id]["data"]
    mode = options["move_data_completed_mode"]
    if mode != "folder":
      path = self.get_parent_path(id)

      if mode == "subfolder":
        path = os.path.join(path, label_name)

      options["move_data_completed_path"] = path

    self._build_label_ancestry(id)

    self._last_modified = datetime.datetime.now()
    self._config.save()

    return id


  @export
  @init_check
  def remove_label(self, label_id):

    if label_id in RESERVED_IDS or label_id not in self._labels:
      raise ValueError("Unknown label: %r" % label_id)

    self._remove_label(label_id)

    parent_id = labelplus.common.get_parent(label_id)
    self._index[parent_id]["children"].remove(label_id)

    self._last_modified = datetime.datetime.now()
    self._config.save()


  @export
  @init_check
  def rename_label(self, label_id, label_name):

    if label_id in RESERVED_IDS or label_id not in self._labels:
      raise ValueError("Unknown label: %r" % label_id)

    label_name = label_name.strip()
    self._validate_name(labelplus.common.get_parent(label_id), label_name)

    obj = self._labels[label_id]
    obj["name"] = label_name

    self._clear_subtree_ancestry(label_id)

    if obj["data"]["move_data_completed_mode"] == "subfolder":
      path = os.path.join(self.get_parent_path(label_id), label_name)
      obj["data"]["move_data_completed_path"] = path

      self._apply_data_completed_path(label_id)
      self._propagate_path_to_descendents(label_id)

    self._last_modified = datetime.datetime.now()
    self._config.save()

    if (obj["data"]["move_data_completed_mode"] == "subfolder" and
        self._prefs["options"]["move_on_changes"]):
      self._subtree_move_completed(label_id)


  def _remove_label(self, label_id):

    for id in self._index[label_id]["children"]:
      self._remove_label(id)

    for id in self._index[label_id]["torrents"]:
      self._reset_torrent_options(id)
      del self._mappings[id]

    del self._index[label_id]
    del self._labels[label_id]


  # Section: Label: Ancestry

  def _build_label_ancestry(self, label_id):

    members = []
    member = label_id
    while member and member != NULL_PARENT:
      ancestry_str = self._index[member].get("ancestry")
      if ancestry_str:
        members.append(ancestry_str)

        break

      members.append(self._labels[member]["name"])
      member = labelplus.common.get_parent(member)

    ancestry_str = "/".join(reversed(members))
    self._index[label_id]["ancestry"] = ancestry_str

    return ancestry_str


  def _get_label_ancestry(self, label_id):

    ancestry_str = self._index[label_id].get("ancestry")
    if ancestry_str:
      return ancestry_str

    return self._build_label_ancestry(label_id)


  def _clear_subtree_ancestry(self, parent_id):

    if self._index[parent_id].get("ancestry") is not None:
      del self._index[parent_id]["ancestry"]

    for id in self._index[parent_id]["children"]:
      self._clear_subtree_ancestry(id)


  # Section: Label: Shared Limit

  def _shared_limit_update(self):

    if self._initialized:
      for id in self._shared_limit_index:
        self._do_update_shared_limit(id)

      reactor.callLater(
        self._prefs["options"]["shared_limit_update_interval"],
        self._shared_limit_update)


  def _do_update_shared_limit(self, label_id):

    shared_download_limit = \
      self._labels[label_id]["data"]["max_download_speed"]
    shared_upload_limit = self._labels[label_id]["data"]["max_upload_speed"]

    if shared_download_limit < 0.0 and shared_upload_limit < 0.0:
      return

    active_torrents = self._get_labeled_torrents_status(
      [label_id], {"state": ["Seeding", "Downloading"]},
      ["download_payload_rate", "upload_payload_rate"])

    (download_rate_sum, upload_rate_sum) = self._get_bandwidth_usage(active_torrents)
    download_rate_sum /= 1024.0
    upload_rate_sum /= 1024.0

    download_diff = download_rate_sum - shared_download_limit
    upload_diff = upload_rate_sum - shared_upload_limit

    num_active_download = sum(
      1 for id in active_torrents \
      if active_torrents[id]["download_payload_rate"] > 0.0)
    num_active_upload = sum(
      1 for id in active_torrents \
      if active_torrents[id]["upload_payload_rate"] > 0.0)

    # Modify individual bandwidth limits based on shared limit
    for id in active_torrents:
      torrent = self._torrents[id]
      status = active_torrents[id]

      if shared_download_limit < 0.0:
        torrent.set_max_download_speed(-1.0)
      else:
        download_rate = status["download_payload_rate"] / 1024.0
        limit = download_rate

        if download_diff >= 0.0:
          usage_ratio = download_rate / download_rate_sum
          limit -= (usage_ratio * download_diff)
        elif download_rate > 0.0:
          limit += (-download_diff) / num_active_download
        else:
          limit = shared_download_limit

        if limit < 0.1: limit = 0.1
        torrent.set_max_download_speed(limit)

      if shared_upload_limit < 0.0:
        torrent.set_max_upload_speed(-1.0)
      else:
        upload_rate = status["upload_payload_rate"] / 1024.0
        limit = upload_rate

        if upload_diff >= 0.0:
          usage_ratio = upload_rate / upload_rate_sum
          limit -= (usage_ratio * upload_diff)
        elif upload_rate > 0.0:
          limit += (-upload_diff) / num_active_upload
        else:
          limit = shared_upload_limit

        if limit < 0.1: limit = 0.1
        torrent.set_max_upload_speed(limit)


  # Section: Label-Torrent: Queries

  @export
  @init_check
  def get_torrent_label(self, torrent_id):

    return self._get_torrent_label(torrent_id)

  def _get_torrent_label(self, torrent_id):

    return self._mappings.get(torrent_id) or ""


  def _get_torrent_label_name(self, torrent_id):

    label_id = self._mappings.get(torrent_id)
    if not label_id:
      return ""

    if self._prefs["options"]["show_full_name"]:
      name = self._get_label_ancestry(label_id)
    else:
      name = self._labels[label_id]["name"]

    return name


  def _has_auto_apply_match(self, label_id, torrent_id):

    uses_regex = self._prefs["options"]["autolabel_uses_regex"]

    name = self._torrents[torrent_id].get_status(["name"])["name"]
    trackers = tuple(t["url"] for t in self._torrents[torrent_id].trackers)

    options = self._labels[label_id]["data"]
    for line in options["auto_queries"]:
      if uses_regex:
        re_line = re.compile(line)
      else:
        terms = line.split()

      if options["auto_name"]:
        if uses_regex:
          match = re_line.search(name)
          if match:
            return True
        elif all(t in name for t in terms):
          return True
      elif options["auto_tracker"]:
        for tracker in trackers:
          if uses_regex:
            match = re_line.search(tracker)
            if match:
              return True
          elif all(t in tracker for t in terms):
            return True

    return False


  def _filter_by_label(self, torrent_ids, label_ids):

    filtered = []

    for id in torrent_ids:
      label_id = self._mappings.get(id)

      if not label_id:
        if ID_NONE in label_ids:
          filtered.append(id)
      elif label_id in label_ids:
        filtered.append(id)
      elif self._prefs["options"]["include_children"]:
        if any(x for x in label_ids if
            labelplus.common.is_ancestor(x, label_id)):
          filtered.append(id)

    return filtered


  def _get_labeled_torrents_status(self, label_ids, filters, fields):

    filtered_torrents = {}
    torrents = []

    if ID_ALL in label_ids:
      torrents = self._torrents.keys()
    elif ID_NONE in label_ids:
      torrents = self._filter_by_label(self._torrents.keys(), label_ids)
    else:
      for label_id in label_ids:
        if label_id in self._index:
          for id in self._index[label_id]["torrents"]:
            if id not in torrents:
              torrents.append(id)

    for filter in filters:
      if filter not in fields:
        fields.append(filter)

    for torrent_id in torrents:
      status_values = self._torrents[torrent_id].get_status(fields)

      if not filters:
        filtered_torrents[torrent_id] = status_values
      else:
        filter_passed = True

        for filter in filters:
          if status_values[filter] not in filters[filter]:
            filter_passed = False
            break

        if filter_passed:
          filtered_torrents[torrent_id] = status_values

    return filtered_torrents


  # Section: Label-Torrent: Modifiers

  @export
  @init_check
  def set_torrent_labels(self, label_id, torrent_list):

    if not label_id:
      label_id = ID_NONE

    if (label_id != ID_NONE and label_id in RESERVED_IDS or
        label_id not in self._labels):
      raise ValueError("Unknown label: %r" % label_id)

    torrents = [t for t in torrent_list if t in self._torrents]
    for id in torrents:
      self._set_torrent_label(id, label_id)

    self._last_modified = datetime.datetime.now()
    self._config.save()

    if self._prefs["options"]["move_on_changes"]:
      self._do_move_completed(label_id, torrents)


  def _set_torrent_label(self, torrent_id, label_id):

    log.debug("Setting label %r on %r", label_id, torrent_id)

    id = self._mappings.get(torrent_id)
    if id is not None:
      self._reset_torrent_options(torrent_id)
      self._index[id]["torrents"].remove(torrent_id)
      del self._mappings[torrent_id]
      log.debug("Torrent %r removed from label %r", torrent_id, id)

    if label_id and label_id not in RESERVED_IDS:
      self._mappings[torrent_id] = label_id
      self._index[label_id]["torrents"].append(torrent_id)
      self._apply_torrent_options(torrent_id)
      log.debug("Torrent %r is labeled %r", torrent_id, label_id)


  # Section: Torrent: Queries

  def _get_bandwidth_usage(self, torrents):

    download_rate_sum = 0.0
    upload_rate_sum = 0.0

    for torrent in torrents:
      status = torrents[torrent]
      download_rate_sum += status["download_payload_rate"]
      upload_rate_sum += status["upload_payload_rate"]

    return (download_rate_sum, upload_rate_sum)


  # Section: Torrent: Modifiers

  def _reset_torrent_options(self, torrent_id):

    torrent = self._torrents[torrent_id]

    # Download settings
    torrent.set_move_completed(self._core["move_completed"])
    torrent.set_move_completed_path(self._core["move_completed_path"])
    torrent.set_options({
      "prioritize_first_last_pieces":
        self._core["prioritize_first_last_pieces"],
    })

    # Bandwidth settings
    torrent.set_max_download_speed(
      self._core["max_download_speed_per_torrent"])
    torrent.set_max_upload_speed(self._core["max_upload_speed_per_torrent"])
    torrent.set_max_connections(self._core["max_connections_per_torrent"])
    torrent.set_max_upload_slots(self._core["max_upload_slots_per_torrent"])

    # Queue settings
    torrent.set_auto_managed(self._core["auto_managed"])
    torrent.set_stop_at_ratio(self._core["stop_seed_at_ratio"])
    torrent.set_stop_ratio(self._core["stop_seed_ratio"])
    torrent.set_remove_at_ratio(self._core["remove_seed_at_ratio"])


  def _apply_torrent_options(self, torrent_id):

    label_id = self._mappings.get(torrent_id)

    options = self._labels[label_id]["data"]
    torrent = self._torrents[torrent_id]

    if options["download_settings"]:
      torrent.set_move_completed(options["move_data_completed"])

      if options["move_data_completed"]:
        torrent.set_move_completed_path(options["move_data_completed_path"])

      torrent.set_options({
        "prioritize_first_last_pieces": options["prioritize_first_last"],
      })

    if options["bandwidth_settings"]:
      torrent.set_max_download_speed(options["max_download_speed"])
      torrent.set_max_upload_speed(options["max_upload_speed"])
      torrent.set_max_connections(options["max_connections"])
      torrent.set_max_upload_slots(options["max_upload_slots"])

    if options["queue_settings"]:
      torrent.set_auto_managed(options["auto_managed"])
      torrent.set_stop_at_ratio(options["stop_at_ratio"])

      if options["stop_at_ratio"]:
        torrent.set_stop_ratio(options["stop_ratio"])
        torrent.set_remove_at_ratio(options["remove_at_ratio"])


  # Section: Torrent: Move Completed: Modifiers

  def _apply_data_completed_path(self, label_id):

    for id in self._index[label_id]["torrents"]:
      self._torrents[id].set_move_completed_path(
          self._labels[label_id]["data"]["move_data_completed_path"])


  def _propagate_path_to_descendents(self, parent_id):


    def descend(parent_id):
      name = self._labels[parent_id]["name"]
      options = self._labels[parent_id]["data"]

      mode = options["move_data_completed_mode"]
      if mode == "folder": return

      if mode == "subfolder":
        move_path.append(name)

      options["move_data_completed_path"] = os.path.join(*move_path)

      if options["download_settings"] and options["move_data_completed"]:
        self._apply_data_completed_path(parent_id)

      for id in self._index[parent_id]["children"]:
        descend(id)

      if mode == "subfolder":
        move_path.pop()


    options = self._labels[parent_id]["data"]
    path = options["move_data_completed_path"]

    move_path = [path]

    for id in self._index[parent_id]["children"]:
      descend(id)


  # Section: Torrent: Move Completed: Execution

  def _subtree_move_completed(self, parent_id):

    if self._prefs["options"]["move_on_changes"]:
      self._do_move_completed(parent_id, self._index[parent_id]["torrents"])

    for id in self._index[parent_id]["children"]:
      self._subtree_move_completed(id)


  def _do_move_completed(self, label_id, torrent_list):

    if label_id in self._labels:
      options = self._labels[label_id]["data"]

      if not options["download_settings"] or \
          not options["move_data_completed"]:
        return

      dest_path = options["move_data_completed_path"]
    else:
      dest_path = self._get_default_save_path()

    move_list = []
    for tid in torrent_list:
      torrent = self._torrents.get(tid)
      if torrent:
        path = torrent.get_status(["save_path"])["save_path"]
        if path != dest_path:
          move_list.append(tid)

    try:
      component.get("CorePlugin.MoveTools").move_completed(move_list)
    except KeyError:
      pass
