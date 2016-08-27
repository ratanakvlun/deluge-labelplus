#
# core.py
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


import cPickle
import copy
import datetime
import logging
import os

import twisted.internet

import deluge.common
import deluge.component
import deluge.configmanager
import deluge.core.rpcserver

import labelplus.common
import labelplus.common.config
import labelplus.common.config.convert
import labelplus.common.config.autolabel
import labelplus.common.label

import labelplus.core.config
import labelplus.core.config.convert


from deluge.plugins.pluginbase import CorePluginBase

from labelplus.common import LabelUpdate
from labelplus.common import LabelPlusError


from labelplus.common.literals import (
  ERR_CORE_NOT_INITIALIZED,
  ERR_INVALID_LABEL, ERR_INVALID_PARENT, ERR_LABEL_EXISTS,
)

CORE_CONFIG = "%s.conf" % labelplus.common.MODULE_NAME
DELUGE_CORE_CONFIG = "core.conf"

CONFIG_SAVE_INTERVAL = 60*2


log = logging.getLogger(__name__)


def cmp_length_then_value(x, y):

  if len(x) > len(y): return -1
  if len(x) < len(y): return 1

  return cmp(x, y)


def check_init(func):

  def wrap(*args, **kwargs):

    if args and isinstance(args[0], Core):
      if not args[0]._initialized:
        raise LabelPlusError(ERR_CORE_NOT_INITIALIZED)

    return func(*args, **kwargs)


  return wrap


class Core(CorePluginBase):

  # Section: Initialization

  def __init__(self, plugin_name):

    super(Core, self).__init__(plugin_name)

    self._initialized = False
    self._config = None


  def enable(self):

    log.debug("Initializing %s...", self.__class__.__name__)

    if not deluge.component.get("TorrentManager").session_started:
      deluge.component.get("EventManager").register_event_handler(
        "SessionStartedEvent", self._on_session_started)
      log.debug("Waiting for session to start...")
    else:
      twisted.internet.reactor.callLater(0.1, self._initialize)


  def _on_session_started(self):

    log.debug("Resuming initialization...")

    twisted.internet.reactor.callLater(0.1, self._initialize)


  def _initialize(self):

    def hook_set_torrent(torrent_id, label_id):

      self._orig_set_torrent(torrent_id, label_id)
      target_label_id = self._find_autolabel_match(torrent_id)
      if target_label_id != labelplus.common.label.ID_NONE:
        self._do_autolabel_torrent(torrent_id)


    self._orig_set_torrent = None

    self._core = deluge.configmanager.ConfigManager(DELUGE_CORE_CONFIG)

    try:
      self._config = self._load_config()
    except ValueError as e:
      log.debug("Initialization failed: %s", e.message)
      deluge.component.get("CorePluginManager").disable_plugin("LabelPlus")
      return

    self._prefs = self._config["prefs"]
    self._labels = self._config["labels"]
    self._mappings = self._config["mappings"]

    self._sorted_labels = {}

    self._timestamp = {
      "labels_changed": labelplus.common.DATETIME_010101,
      "mappings_changed": labelplus.common.DATETIME_010101,
      "labels_sorted": labelplus.common.DATETIME_010101,
      "last_saved": labelplus.common.DATETIME_010101,
    }

    self._torrents = deluge.component.get("TorrentManager").torrents

    self._build_label_index()
    self._remove_orphans()

    self._normalize_data()
    self._normalize_mappings()
    self._normalize_path_modes()

    self._build_fullname_index()
    self._build_shared_limit_index()

    deluge.component.get("FilterManager").register_filter(
      labelplus.common.STATUS_ID, self.filter_by_label)

    deluge.component.get("CorePluginManager").register_status_field(
      labelplus.common.STATUS_NAME, self.get_torrent_label_name)
    deluge.component.get("CorePluginManager").register_status_field(
      labelplus.common.STATUS_ID, self.get_torrent_label_id)

    deluge.component.get("EventManager").register_event_handler(
      "TorrentAddedEvent", self.on_torrent_added)
    deluge.component.get("EventManager").register_event_handler(
      "PreTorrentRemovedEvent", self.on_torrent_removed)

    deluge.component.get("AlertManager").register_handler(
      "torrent_finished_alert", self.on_torrent_finished)

    try:
      rs = deluge.component.get("RPCServer")
      self._orig_set_torrent = rs.factory.methods["label.set_torrent"]

      hook_set_torrent._rpcserver_export = self._orig_set_torrent._rpcserver_export
      hook_set_torrent._rpcserver_auth_level = self._orig_set_torrent._rpcserver_auth_level
      hook_set_torrent.__doc__ = self._orig_set_torrent.__doc__

      rs.factory.methods["label.set_torrent"] = hook_set_torrent
      log.debug("Hooked into label.set_torrent")
    except KeyError:
      pass

    self._initialized = True

    twisted.internet.reactor.callLater(1, self._save_config_update_loop)
    twisted.internet.reactor.callLater(1, self._shared_limit_update_loop)

    log.debug("%s initialized", self.__class__.__name__)


  def _load_config(self):

    config = deluge.configmanager.ConfigManager(CORE_CONFIG)

    old_ver = labelplus.common.config.init_config(config,
      labelplus.common.config.CONFIG_DEFAULTS,
      labelplus.common.config.CONFIG_VERSION,
      labelplus.core.config.convert.CONFIG_SPECS)

    if old_ver != labelplus.common.config.CONFIG_VERSION:
      log.debug("Config file converted: v%s -> v%s",
        old_ver, labelplus.common.config.CONFIG_VERSION)

    labelplus.core.config.remove_invalid_keys(config.config)

    return config


  def _build_label_index(self):

    def build_label_entry(label_id):

      children = []
      torrents = []

      for id in self._labels:
        if id == label_id:
          continue

        if labelplus.common.label.get_parent_id(id) == label_id:
          children.append(id)

      for id in self._mappings:
        if self._mappings[id] == label_id:
          torrents.append(id)

      label_entry = {
        "children": children,
        "torrents": torrents,
      }

      return label_entry


    index = {}

    index[labelplus.common.label.ID_NULL] = build_label_entry(
      labelplus.common.label.ID_NULL)

    for id in self._labels:
      if id not in labelplus.common.label.RESERVED_IDS:
        index[id] = build_label_entry(id)

    self._index = index


  def _remove_orphans(self):

    removals = []

    for id in self._labels:
      parent_id = labelplus.common.label.get_parent_id(id)
      if (parent_id != labelplus.common.label.ID_NULL and
          parent_id not in self._labels):
        removals.append(id)

    for id in removals:
      self._remove_label(id)


  def _normalize_data(self):

    self._normalize_options(self._prefs["options"])
    self._normalize_label_options(self._prefs["label"])

    for id in labelplus.common.label.RESERVED_IDS:
      if id in self._labels:
        del self._labels[id]

    for id in self._labels:
      self._normalize_label_options(self._labels[id]["options"],
        self._prefs["label"])


  def _normalize_mappings(self):

    for id in self._mappings.keys():
      if id in self._torrents:
        if self._mappings[id] in self._labels:
          self._apply_torrent_options(id)
          continue
        elif self._prefs["options"]["reset_on_label_unset"]:
          self._reset_torrent_options(id)

      self._remove_torrent_label(id)


  def _normalize_path_modes(self):

    root_ids = self._get_descendent_labels(labelplus.common.label.ID_NULL, 1)
    for id in root_ids:
      for path_type in labelplus.common.config.PATH_TYPES:
        self._labels[id]["options"]["%s_mode" % path_type] = \
          labelplus.common.config.MOVE_FOLDER


  def _build_shared_limit_index(self):

    shared_limit_index = []

    for id in self._labels:
      if (self._labels[id]["options"]["bandwidth_settings"] and
          self._labels[id]["options"]["shared_limit"]):
        shared_limit_index.append(id)

    self._shared_limit_index = shared_limit_index


  # Section: Deinitialization

  def disable(self):

    log.debug("Deinitializing %s...", self.__class__.__name__)

    deluge.component.get("EventManager").deregister_event_handler(
      "SessionStartedEvent", self._on_session_started)

    if self._config:
      if self._initialized:
        self._config.save()

      deluge.configmanager.close(CORE_CONFIG)

    self._initialized = False

    rs = deluge.component.get("RPCServer")
    if self._orig_set_torrent and "label.set_torrent" in rs.factory.methods:
      rs.factory.methods["label.set_torrent"] = self._orig_set_torrent
      log.debug("Unhooked label.set_torrent")
    self._orig_set_torrent = None

    deluge.component.get("EventManager").deregister_event_handler(
      "TorrentAddedEvent", self.on_torrent_added)
    deluge.component.get("EventManager").deregister_event_handler(
      "PreTorrentRemovedEvent", self.on_torrent_removed)

    deluge.component.get("AlertManager").deregister_handler(
      self.on_torrent_finished)

    deluge.component.get("CorePluginManager").deregister_status_field(
      labelplus.common.STATUS_ID)
    deluge.component.get("CorePluginManager").deregister_status_field(
      labelplus.common.STATUS_NAME)

    if (labelplus.common.STATUS_ID in
        deluge.component.get("FilterManager").registered_filters):
      deluge.component.get("FilterManager").deregister_filter(
        labelplus.common.STATUS_ID)

    self._rpc_deregister(labelplus.common.PLUGIN_NAME)

    log.debug("%s deinitialized", self.__class__.__name__)


  def _rpc_deregister(self, name):

    server = deluge.component.get("RPCServer")
    name = name.lower()

    for d in dir(self):
      if d[0] == "_": continue

      if getattr(getattr(self, d), '_rpcserver_export', False):
        method = "%s.%s" % (name, d)
        log.debug("Deregistering method: %s", method)
        if method in server.factory.methods:
          del server.factory.methods[method]


  # Section: Update Loops

  def _save_config_update_loop(self):

    if self._initialized:
      last_changed = max(self._timestamp["labels_changed"],
        self._timestamp["mappings_changed"])

      if self._timestamp["last_saved"] <= last_changed:
        self._config.save()
        self._timestamp["last_saved"] = datetime.datetime.now()

      twisted.internet.reactor.callLater(CONFIG_SAVE_INTERVAL,
        self._save_config_update_loop)


  def _shared_limit_update_loop(self):

    if self._initialized:
      for id in self._shared_limit_index:
        if id in self._labels:
          self._do_update_shared_limit(id)

      twisted.internet.reactor.callLater(
        self._prefs["options"]["shared_limit_interval"],
        self._shared_limit_update_loop)


  # Section: Public API: General

  @deluge.core.rpcserver.export
  def is_initialized(self):

    return self._initialized


  @deluge.core.rpcserver.export
  def get_daemon_info(self):

    return self._get_daemon_info()


  # Section: Public API: Preferences

  @deluge.core.rpcserver.export
  @check_init
  def get_preferences(self):

    log.debug("Getting preferences")

    return self._prefs


  @deluge.core.rpcserver.export
  @check_init
  def set_preferences(self, prefs):

    log.debug("Setting preferences")

    self._normalize_options(prefs["options"])
    self._prefs["options"].update(prefs["options"])

    self._normalize_label_options(prefs["label"])
    self._prefs["label"].update(prefs["label"])

    self._config.save()
    self._timestamp["last_saved"] = datetime.datetime.now()


  @deluge.core.rpcserver.export
  @check_init
  def get_label_defaults(self):

    log.debug("Getting label defaults")

    return self._prefs["label"]


  # Section: Public API: Label: Queries

  # Deprecated
  @deluge.core.rpcserver.export
  @check_init
  def get_move_path_options(self, label_id):

    if label_id not in self._labels:
      raise LabelPlusError(ERR_INVALID_LABEL)

    parent_path = self._get_parent_path(label_id,
      labelplus.common.config.PATH_MOVE_COMPLETED)

    options = {
      "parent": parent_path,
      "subfolder": os.path.join(parent_path, self._labels[label_id]["name"]),
    }

    return options


  @deluge.core.rpcserver.export
  @check_init
  def get_path_options(self, label_id):

    if label_id not in self._labels:
      raise LabelPlusError(ERR_INVALID_LABEL)

    options = {}

    for path_type in labelplus.common.config.PATH_TYPES:
      parent_path = self._get_parent_path(label_id, path_type)
      options[path_type] = {
        "parent": parent_path,
        "subfolder": os.path.join(parent_path, self._labels[label_id]["name"]),
      }

    return options


  @deluge.core.rpcserver.export
  @check_init
  def get_label_bandwidth_usages(self, label_ids):

    usages = {}

    for id in set(label_ids):
      if id == labelplus.common.label.ID_NONE or id in self._labels:
        usages[id] = self._get_label_bandwidth_usage(id)

    return usages


  # Deprecated
  @deluge.core.rpcserver.export
  @check_init
  def get_labels_data(self, timestamp=None):

    if timestamp:
      t = cPickle.loads(timestamp)
    else:
      t = labelplus.common.DATETIME_010101

    last_changed = max(self._timestamp["labels_changed"],
      self._timestamp["mappings_changed"])

    if t <= last_changed:
      return self._get_labels_data()
    else:
      return None


  @deluge.core.rpcserver.export
  @check_init
  def get_label_updates(self, since=None):

    if since:
      t = cPickle.loads(since)
    else:
      t = labelplus.common.DATETIME_010101

    last_changed = max(self._timestamp["labels_changed"],
      self._timestamp["mappings_changed"])

    if t <= last_changed:
      u = LabelUpdate(LabelUpdate.TYPE_FULL, datetime.datetime.now(),
        self._get_labels_data())
      return cPickle.dumps(u)
    else:
      return None


  # New get_label_updates candidate, use dict instead of LabelUpdate class
  @deluge.core.rpcserver.export
  @check_init
  def get_label_updates_dict(self, since=None):

    if since:
      t = cPickle.loads(since)
    else:
      t = labelplus.common.DATETIME_010101

    last_changed = max(self._timestamp["labels_changed"],
      self._timestamp["mappings_changed"])

    if t <= last_changed:
      u = LabelUpdate(LabelUpdate.TYPE_FULL, datetime.datetime.now(),
        self._get_labels_data())

      return {
        "type": u.type,
        "timestamp": cPickle.dumps(u.timestamp),
        "data": u.data
      }
    else:
      return None


  # Section: Public API: Label: Modifiers

  @deluge.core.rpcserver.export
  @check_init
  def add_label(self, parent_id, label_name):

    log.debug("Adding %r to label %r", label_name, parent_id)

    if (parent_id != labelplus.common.label.ID_NULL and
        parent_id not in self._labels):
      raise LabelPlusError(ERR_INVALID_PARENT)

    id = self._add_label(parent_id, label_name)

    self._timestamp["labels_changed"] = datetime.datetime.now()

    return id


  @deluge.core.rpcserver.export
  @check_init
  def rename_label(self, label_id, label_name):

    log.debug("Renaming name of label %r to %r", label_id, label_name)

    if label_id not in self._labels:
      raise LabelPlusError(ERR_INVALID_LABEL)

    self._rename_label(label_id, label_name)

    self._timestamp["labels_changed"] = datetime.datetime.now()


  @deluge.core.rpcserver.export
  @check_init
  def move_label(self, label_id, dest_id, dest_name):

    log.debug("Moving label %r to %r with name %r", label_id, dest_id,
      dest_name)

    if label_id not in self._labels:
      raise LabelPlusError(ERR_INVALID_LABEL)

    if dest_id != labelplus.common.label.ID_NULL and (
        label_id == dest_id or dest_id not in self._labels or
        labelplus.common.label.is_ancestor(label_id, dest_id)):
      raise LabelPlusError(ERR_INVALID_PARENT)

    parent_id = labelplus.common.label.get_parent_id(label_id)
    if parent_id == dest_id:
      self._rename_label(label_id, dest_name)
    else:
      self._move_label(label_id, dest_id, dest_name)

    self._timestamp["labels_changed"] = datetime.datetime.now()


  @deluge.core.rpcserver.export
  @check_init
  def remove_label(self, label_id):

    log.debug("Removing label %r", label_id)

    if label_id not in self._labels:
      raise LabelPlusError(ERR_INVALID_LABEL)

    self._remove_label(label_id)

    self._timestamp["labels_changed"] = datetime.datetime.now()
    self._timestamp["mappings_changed"] = datetime.datetime.now()


  # Section: Public API: Label: Options

  @deluge.core.rpcserver.export
  @check_init
  def get_label_options(self, label_id):

    log.debug("Getting label options for %r", label_id)

    if label_id not in self._labels:
      raise LabelPlusError(ERR_INVALID_LABEL)

    return self._labels[label_id]["options"]


  @deluge.core.rpcserver.export
  @check_init
  def set_label_options(self, label_id, options_in, apply_to_all=None):

    log.debug("Setting label options for %r", label_id)

    if label_id not in self._labels:
      raise LabelPlusError(ERR_INVALID_LABEL)

    self._set_label_options(label_id, options_in, apply_to_all)


  # Section: Public API: Torrent-Label

  @deluge.core.rpcserver.export
  @check_init
  def get_torrent_labels(self, torrent_ids):

    log.debug("Getting torrent labels")

    mappings = {}

    for id in set(torrent_ids):
      if id in self._torrents:
        mappings[id] = [
          self._get_torrent_label_id(id),
          self._get_torrent_label_name(id),
        ]

    return mappings


  @deluge.core.rpcserver.export
  @check_init
  def set_torrent_labels(self, torrent_ids, label_id):

    log.debug("Setting torrent labels to %r", label_id)

    if (label_id != labelplus.common.label.ID_NONE and
        label_id not in self._labels):
      raise LabelPlusError(ERR_INVALID_LABEL)

    torrent_ids = [x for x in set(torrent_ids) if x in self._torrents]
    if not torrent_ids:
      return

    for id in torrent_ids:
      self._set_torrent_label(id, label_id)

    if self._prefs["options"]["move_on_changes"]:
      self._move_torrents(torrent_ids)

    self._timestamp["mappings_changed"] = datetime.datetime.now()


  # Section: Public Callbacks

  @check_init
  def on_torrent_added(self, torrent_id):

    label_id = self._do_autolabel_torrent(torrent_id)

    if label_id != labelplus.common.label.ID_NONE:
      self._move_torrents([torrent_id])

    self._timestamp["mappings_changed"] = datetime.datetime.now()


  @check_init
  def on_torrent_removed(self, torrent_id):

    if torrent_id in self._mappings:
      label_id = self._mappings[torrent_id]
      self._remove_torrent_label(torrent_id)
      log.debug("Removing torrent %r from label %r", torrent_id, label_id)

    self._timestamp["mappings_changed"] = datetime.datetime.now()


  @check_init
  def on_torrent_finished(self, alert):

    torrent_id = str(alert.handle.info_hash())

    if torrent_id in self._mappings:
      log.debug("Labeled torrent %r has finished", torrent_id)

      if self._prefs["options"]["move_after_recheck"]:
        # Try to move in case this alert was from a recheck
        self._move_torrents([torrent_id])


  @check_init
  def get_torrent_label_id(self, torrent_id):

    return self._get_torrent_label_id(torrent_id)


  @check_init
  def get_torrent_label_name(self, torrent_id):

    return self._get_torrent_label_name(torrent_id)


  @check_init
  def filter_by_label(self, torrent_ids, label_ids):

    return self._filter_by_label(torrent_ids, label_ids)


  # Section: General

  def _get_daemon_info(self):

    info = {
      "os.path": os.path.__name__,
    }

    return info


  def _get_deluge_save_path(self):

    path = self._core["download_location"]
    if not path:
      path = deluge.common.get_default_download_dir()

    return path


  def _get_deluge_move_path(self):

    path = self._core["move_completed_path"]
    if not path:
      path = self._get_deluge_save_path()

    return path


  # Section: Options

  def _normalize_options(self, options):

    for key in options.keys():
      if key not in labelplus.common.config.OPTION_DEFAULTS:
        del options[key]

    for key in labelplus.common.config.OPTION_DEFAULTS:
      if key not in options:
        options[key] = copy.deepcopy(
          labelplus.common.config.OPTION_DEFAULTS[key])

    if options["shared_limit_interval"] < 1:
      options["shared_limit_interval"] = 1


  # Section: Label: Queries

  def _get_unused_id(self, parent_id):

    assert(parent_id == labelplus.common.label.ID_NULL or
      parent_id in self._labels)

    i = 0
    label_obj = {}

    if parent_id == labelplus.common.label.ID_NULL:
      prefix = ""
    else:
      prefix = "%s:" % parent_id

    while label_obj is not None:
      id = "%s%s" % (prefix, i)
      label_obj = self._labels.get(id)
      i += 1

    return id


  def _get_children_names(self, parent_id):

    assert(parent_id == labelplus.common.label.ID_NULL or
      parent_id in self._labels)

    names = []

    for id in self._index[parent_id]["children"]:
      names.append(self._labels[id]["name"])

    return names


  def _validate_name(self, parent_id, label_name):

    assert(parent_id == labelplus.common.label.ID_NULL or
      parent_id in self._labels)

    labelplus.common.label.validate_name(label_name)

    names = self._get_children_names(parent_id)
    if label_name in names:
      raise LabelPlusError(ERR_LABEL_EXISTS)


  def _get_descendent_labels(self, label_id, depth=-1):

    assert(label_id == labelplus.common.label.ID_NULL or
      label_id in self._labels)

    descendents = []

    if depth == -1 or depth > 0:
      if depth > 0:
        depth -= 1

      for id in self._index[label_id]["children"]:
        descendents.append(id)
        descendents += self._get_descendent_labels(id, depth)

    return descendents


  def _get_label_bandwidth_usage(self, label_id):

    assert(label_id == labelplus.common.label.ID_NONE or
      label_id in self._labels)

    if label_id == labelplus.common.label.ID_NONE:
      torrent_ids = self._get_unlabeled_torrents()
    else:
      torrent_ids = self._index[label_id]["torrents"]

    return self._get_torrent_bandwidth_usage(torrent_ids)


  def _get_sorted_labels(self, cmp_func=None, reverse=False):

    if self._timestamp["labels_sorted"] <= self._timestamp["labels_changed"]:
      self._sorted_labels.clear()

    key = (cmp_func, reverse)

    if key not in self._sorted_labels:
      self._sorted_labels[key] = sorted(self._labels,
        cmp=key[0], reverse=key[1])

      self._timestamp["labels_sorted"] = datetime.datetime.now()

    return self._sorted_labels[key]


  def _get_labels_data(self):

    total_count = len(self._torrents)
    labeled_count = 0
    data = {}

    label_ids = self._get_sorted_labels(cmp_length_then_value)

    for id in label_ids:
      count = len(self._index[id]["torrents"])
      labeled_count += count

      data[id] = {
        "name": self._labels[id]["name"],
        "count": count,
      }

    data[labelplus.common.label.ID_ALL] = {
      "name": labelplus.common.label.ID_ALL,
      "count": total_count,
    }

    data[labelplus.common.label.ID_NONE] = {
      "name": labelplus.common.label.ID_NONE,
      "count": total_count-labeled_count,
    }

    return data


  # Section: Label: Modifiers

  def _add_label(self, parent_id, label_name):

    assert(parent_id == labelplus.common.label.ID_NULL or
      parent_id in self._labels)

    label_name = label_name.strip()

    try:
      label_name = unicode(label_name, "utf8")
    except (TypeError, UnicodeDecodeError):
      pass

    self._validate_name(parent_id, label_name)

    id = self._get_unused_id(parent_id)
    self._index[parent_id]["children"].append(id)

    self._labels[id] = {
      "name": label_name,
      "options": copy.deepcopy(self._prefs["label"]),
    }

    self._index[id] = {
      "fullname": self._resolve_fullname(id),
      "children": [],
      "torrents": [],
    }

    for path_type in labelplus.common.config.PATH_TYPES:
      self._labels[id]["options"]["%s_path" % path_type] = \
        self._resolve_path(id, path_type)

    if self._labels[id]["options"]["shared_limit"]:
      self._shared_limit_index.append(id)

    return id


  def _rename_label(self, label_id, label_name):

    assert(label_id in self._labels)

    label_name = label_name.strip()

    try:
      label_name = unicode(label_name, "utf8")
    except (TypeError, UnicodeDecodeError):
      pass

    parent_id = labelplus.common.label.get_parent_id(label_id)
    self._validate_name(parent_id, label_name)
    self._labels[label_id]["name"] = label_name

    self._build_fullname_index(label_id)

    for path_type in labelplus.common.config.PATH_TYPES:
      self._update_paths(label_id, path_type)

    self._apply_move_completed_paths(label_id, True)

    if self._prefs["options"]["move_on_changes"]:
      self._move_torrents_by_label(label_id, True)


  def _move_label(self, label_id, dest_id, dest_name):

    def reparent(label_id, dest_id):

      id = self._get_unused_id(dest_id)
      self._index[dest_id]["children"].append(id)

      self._labels[id] = self._labels[label_id]

      self._index[id] = {
        "fullname": self._resolve_fullname(id),
        "torrents": self._index[label_id]["torrents"],
        "children": [],
      }

      if label_id in self._shared_limit_index:
        self._shared_limit_index.remove(label_id)
        self._shared_limit_index.append(id)

      parent_id = labelplus.common.label.get_parent_id(label_id)
      if parent_id in self._index:
        self._index[parent_id]["children"].remove(label_id)

      for torrent_id in self._index[label_id]["torrents"]:
        self._mappings[torrent_id] = id

      for child_id in list(self._index[label_id]["children"]):
        reparent(child_id, id)

      del self._index[label_id]
      del self._labels[label_id]

      return id


    assert(label_id in self._labels)
    assert(dest_id == labelplus.common.label.ID_NULL or
      dest_id in self._labels)

    dest_name = dest_name.strip()

    try:
      dest_name = unicode(dest_name, "utf8")
    except (TypeError, UnicodeDecodeError):
      pass

    self._validate_name(dest_id, dest_name)
    id = reparent(label_id, dest_id)

    self._labels[id]["name"] = dest_name

    for path_type in labelplus.common.config.PATH_TYPES:
      self._update_paths(id, path_type)

    self._apply_move_completed_paths(id, True)

    if self._prefs["options"]["move_on_changes"]:
      self._move_torrents_by_label(id, True)


  def _remove_label(self, label_id):

    assert(label_id in self._labels)

    if label_id in self._shared_limit_index:
      self._shared_limit_index.remove(label_id)

    parent_id = labelplus.common.label.get_parent_id(label_id)
    if parent_id in self._index:
      self._index[parent_id]["children"].remove(label_id)

    for id in list(self._index[label_id]["children"]):
      self._remove_label(id)

    torrent_ids = []

    for id in list(self._index[label_id]["torrents"]):
      if id in self._torrents:
        self._set_torrent_label(id, labelplus.common.label.ID_NONE)
        torrent_ids.append(id)

    del self._index[label_id]
    del self._labels[label_id]

    if self._prefs["options"]["move_on_changes"]:
      self._move_torrents(torrent_ids)


  # Section: Label: Options

  def _normalize_label_options(self, options,
      template=labelplus.common.config.LABEL_DEFAULTS):

    for key in options.keys():
      if key not in template:
        del options[key]

    for key in template:
      if key not in options:
        options[key] = copy.deepcopy(template[key])

    options["move_completed_path"] = \
      options["move_completed_path"].strip()
    if not options["move_completed_path"]:
      options["move_completed_mode"] = \
        labelplus.common.config.MOVE_FOLDER
      options["move_completed_path"] = self._get_deluge_move_path()
    if (options["move_completed_mode"] not in
        labelplus.common.config.MOVE_MODES):
      options["move_completed_mode"] = \
        labelplus.common.config.MOVE_FOLDER

    options["download_location_path"] = \
      options["download_location_path"].strip()
    if not options["download_location_path"]:
      options["download_location_mode"] = \
        labelplus.common.config.MOVE_FOLDER
      options["download_location_path"] = self._get_deluge_save_path()
    if (options["download_location_mode"] not in
        labelplus.common.config.MOVE_MODES):
      options["download_location_mode"] = \
        labelplus.common.config.MOVE_FOLDER

    options["max_connections"] = int(options["max_connections"])
    options["max_upload_slots"] = int(options["max_upload_slots"])

    rules = options["autolabel_rules"]
    options["autolabel_rules"] = list(options["autolabel_rules"])
    for rule in rules:
      if len(rule) != labelplus.common.config.autolabel.NUM_FIELDS:
        options["autolabel_rules"].remove(rule)
        continue

      prop, op, case, query = rule
      if (prop not in labelplus.common.config.autolabel.PROPS or
          op not in labelplus.common.config.autolabel.OPS or
          case not in labelplus.common.config.autolabel.CASES or
          (not query and prop != labelplus.common.config.autolabel.PROP_LABEL)):
        options["autolabel_rules"].remove(rule)


  def _set_label_options(self, label_id, options_in, apply_to_all=None):

    assert(label_id in self._labels)

    options = self._labels[label_id]["options"]

    old = {
      "download_settings": options["download_settings"],
      "download_location": options["download_location"],
      "download_location_path": options["download_location_path"],
      "move_completed": options["move_completed"],
      "move_completed_path": options["move_completed_path"],
    }

    self._normalize_label_options(options_in, self._prefs["label"])
    options.update(options_in)

    if label_id in self._shared_limit_index:
      self._shared_limit_index.remove(label_id)

    if options["bandwidth_settings"] and options["shared_limit"]:
      self._shared_limit_index.append(label_id)

    for id in self._index[label_id]["torrents"]:
      self._apply_torrent_options(id)

    path_toggled_on = False
    if options["download_settings"]:
      if options["download_settings"] != old["download_settings"]:
        if options["download_location"] or options["move_completed"]:
          path_toggled_on = True
      else:
        for path_type in labelplus.common.config.PATH_TYPES:
          if options[path_type] and options[path_type] != old[path_type]:
            path_toggled_on = True
            break

    changed_paths = []
    for path_type in labelplus.common.config.PATH_TYPES:
      if options["%s_path" % path_type] != old["%s_path" % path_type]:
        for id in self._index[label_id]["children"]:
          self._update_paths(id, path_type)
        changed_paths.append(path_type)

    if changed_paths:
      self._timestamp["labels_changed"] = datetime.datetime.now()

      if labelplus.common.config.PATH_MOVE_COMPLETED in changed_paths:
        self._apply_move_completed_paths(label_id, True)

    if self._prefs["options"]["move_on_changes"]:
      if changed_paths:
        self._move_torrents_by_label(label_id, True)
      elif path_toggled_on:
        self._move_torrents_by_label(label_id, False)

    if options["autolabel_settings"] and apply_to_all is not None:
      self._do_autolabel_torrents(label_id, apply_to_all)


  # Section: Label: Options: Paths

  def _get_parent_path(self, label_id, path_type):
    # Get label's parent path of the given type

    assert(label_id in self._labels)
    assert(path_type in labelplus.common.config.PATH_TYPES)

    parent_id = labelplus.common.label.get_parent_id(label_id)
    if parent_id in self._labels:
      path = self._labels[parent_id]["options"]["%s_path" % path_type]
    elif path_type == labelplus.common.config.PATH_MOVE_COMPLETED:
      path = self._get_deluge_move_path()
    else:
      path = self._get_deluge_save_path()

    return path


  def _resolve_path(self, label_id, path_type):
    # Resolve full path while accounting for relativity

    assert(label_id in self._labels)
    assert(path_type in labelplus.common.config.PATH_TYPES)

    name = self._labels[label_id]["name"]
    options = self._labels[label_id]["options"]

    path = options["%s_path" % path_type]
    mode = options["%s_mode" % path_type]

    if mode != labelplus.common.config.MOVE_FOLDER:
      path = self._get_parent_path(label_id, path_type)

      if mode == labelplus.common.config.MOVE_SUBFOLDER:
        path = os.path.join(path, name)

    return path


  def _update_paths(self, label_id, path_type):
    # Ensure relative paths in label options are consistent

    assert(label_id in self._labels)
    assert(path_type in labelplus.common.config.PATH_TYPES)

    options = self._labels[label_id]["options"]
    path = self._resolve_path(label_id, path_type)

    if path == options["%s_path" % path_type]:
      return

    options["%s_path" % path_type] = path

    for id in self._index[label_id]["children"]:
      self._update_paths(id, path_type)


  # Section: Label: Full Name

  def _resolve_fullname(self, label_id):

    assert(label_id == labelplus.common.label.ID_NULL or
      label_id in self._labels)

    parts = []
    id = label_id

    while id != labelplus.common.label.ID_NULL:
      parts.append(self._labels[id]["name"])
      id = labelplus.common.label.get_parent_id(id)

    fullname = "/".join(reversed(parts))

    return fullname


  def _build_fullname_index(self, label_id=labelplus.common.label.ID_NULL):

    assert(label_id == labelplus.common.label.ID_NULL or
      label_id in self._labels)

    self._index[label_id]["fullname"] = self._resolve_fullname(label_id)

    for id in self._index[label_id]["children"]:
      self._build_fullname_index(id)


  # Section: Label: Shared Limit

  def _do_update_shared_limit(self, label_id):

    assert(label_id in self._labels)

    options = self._labels[label_id]["options"]
    shared_download_limit = options["max_download_speed"]
    shared_upload_limit = options["max_upload_speed"]

    if shared_download_limit < 0.0 and shared_upload_limit < 0.0:
      return

    torrent_ids = self._index[label_id]["torrents"]

    statuses = self._get_torrent_statuses(
      torrent_ids, {"state": ["Seeding", "Downloading"]},
      ["download_payload_rate", "upload_payload_rate"])

    num_active_downloads = \
      sum(1 for id in statuses if statuses[id]["download_payload_rate"] > 0.0)
    download_rate_sum = \
      sum(statuses[id]["download_payload_rate"] for id in statuses) / 1024.0
    download_diff = download_rate_sum - shared_download_limit

    num_active_uploads = \
      sum(1 for id in statuses if statuses[id]["upload_payload_rate"] > 0.0)
    upload_rate_sum = \
      sum(statuses[id]["upload_payload_rate"] for id in statuses) / 1024.0
    upload_diff = upload_rate_sum - shared_upload_limit

    # Modify individual torrent bandwidth limits based on shared limit
    for id in statuses:
      torrent = self._torrents[id]
      status = statuses[id]

      # Determine new torrent download limit
      if shared_download_limit < 0.0:
        torrent.set_max_download_speed(-1.0)
      else:
        download_rate = status["download_payload_rate"] / 1024.0
        limit = download_rate

        if download_diff >= 0.0:
        # Total is above shared limit; deduct based on usage
          usage_ratio = download_rate / download_rate_sum
          limit -= (usage_ratio * download_diff)
        elif download_rate > 0.0:
        # Total is below and torrent active; increase by a slice of unused
          limit += abs(download_diff) / num_active_downloads
        else:
        # Total is below and torrent inactive; give chance by setting max
          limit = shared_download_limit

        if limit < 0.1: limit = 0.1
        torrent.set_max_download_speed(limit)

      # Determine new torrent upload limit
      if shared_upload_limit < 0.0:
        torrent.set_max_upload_speed(-1.0)
      else:
        upload_rate = status["upload_payload_rate"] / 1024.0
        limit = upload_rate

        if upload_diff >= 0.0:
          usage_ratio = upload_rate / upload_rate_sum
          limit -= (usage_ratio * upload_diff)
        elif upload_rate > 0.0:
          limit += abs(upload_diff) / num_active_uploads
        else:
          limit = shared_upload_limit

        if limit < 0.1: limit = 0.1
        torrent.set_max_upload_speed(limit)


  # Section: Torrent: Queries

  def _get_torrent_statuses(self, torrent_ids, filters, fields):

    assert(all(x in self._torrents for x in torrent_ids))

    statuses = {}

    for filter in filters:
      if filter not in fields:
        fields.append(filter)

    for id in torrent_ids:
      status = self._torrents[id].get_status(fields)

      if not filters:
        statuses[id] = status
      else:
        passed = True

        for filter in filters:
          if status[filter] not in filters[filter]:
            passed = False
            break

        if passed:
          statuses[id] = status

    return statuses


  def _get_torrent_bandwidth_usage(self, torrent_ids):

    assert(all(x in self._torrents for x in torrent_ids))

    statuses = self._get_torrent_statuses(
      torrent_ids, {"state": ["Seeding", "Downloading"]},
      ["download_payload_rate", "upload_payload_rate"])

    download_rate_sum = 0.0
    upload_rate_sum = 0.0

    for id in statuses:
      status = statuses[id]
      download_rate_sum += status["download_payload_rate"]
      upload_rate_sum += status["upload_payload_rate"]

    return (download_rate_sum, upload_rate_sum)


  # Section: Torrent: Modifiers

  def _reset_torrent_options(self, torrent_id):

    assert(torrent_id in self._torrents)

    torrent = self._torrents[torrent_id]

    # Download settings
    torrent.set_move_completed(self._core["move_completed"])
    torrent.set_move_completed_path(self._core["move_completed_path"])
    torrent.set_prioritize_first_last(
      self._core["prioritize_first_last_pieces"])

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

    assert(torrent_id in self._torrents)

    label_id = self._mappings.get(torrent_id, labelplus.common.label.ID_NONE)

    if label_id == labelplus.common.label.ID_NONE:
      self._reset_torrent_options(torrent_id)
      return

    options = self._labels[label_id]["options"]
    torrent = self._torrents[torrent_id]

    if options["download_settings"]:
      torrent.set_move_completed(options["move_completed"])
      torrent.set_prioritize_first_last(options["prioritize_first_last"])

      if options["move_completed"]:
        torrent.set_move_completed_path(options["move_completed_path"])

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


  # Section: Torrent-Label: Queries

  def _get_unlabeled_torrents(self):

    torrent_ids = []

    for id in self._torrents:
      if id not in self._mappings:
        torrent_ids.append(id)

    return torrent_ids


  def _get_torrent_label_id(self, torrent_id):

    return self._mappings.get(torrent_id, labelplus.common.label.ID_NONE)


  def _get_torrent_label_name(self, torrent_id):

    label_id = self._mappings.get(torrent_id, labelplus.common.label.ID_NONE)
    if label_id == labelplus.common.label.ID_NONE:
      return ""

    return self._index[label_id]["fullname"]


  def _filter_by_label(self, torrent_ids, label_ids):

    filtered = []

    for id in torrent_ids:
      label_id = self._mappings.get(id, labelplus.common.label.ID_NONE)
      if label_id in label_ids:
        filtered.append(id)

    return filtered


  # Section: Torrent-Label: Modifiers

  def _remove_torrent_label(self, torrent_id):

    label_id = self._mappings.get(torrent_id, labelplus.common.label.ID_NONE)
    if label_id in self._index:
      self._index[label_id]["torrents"].remove(torrent_id)

    del self._mappings[torrent_id]


  def _set_torrent_label(self, torrent_id, label_id):

    assert(torrent_id in self._torrents)
    assert(label_id == labelplus.common.label.ID_NONE or
      label_id in self._labels)

    if torrent_id in self._mappings:
      self._remove_torrent_label(torrent_id)

    if label_id == labelplus.common.label.ID_NONE:
      if self._prefs["options"]["reset_on_label_unset"]:
        self._reset_torrent_options(torrent_id)
    else:
      self._mappings[torrent_id] = label_id
      self._index[label_id]["torrents"].append(torrent_id)
      self._apply_torrent_options(torrent_id)


  # Section: Torrent-Label: Autolabel

  def _has_autolabel_match(self, torrent_id, label_id):

    assert(torrent_id in self._torrents)
    assert(label_id in self._labels)

    options = self._labels[label_id]["options"]
    rules = options["autolabel_rules"]
    match_all = options["autolabel_match_all"]

    status = deluge.component.get("Core").get_torrent_status(torrent_id,
      ["name", "trackers", "files", "label"])

    name = status["name"]
    trackers = [x["url"] for x in status["trackers"]]
    files = [x["path"] for x in status["files"]]

    props = {
      labelplus.common.config.autolabel.PROP_NAME: [name],
      labelplus.common.config.autolabel.PROP_TRACKER: trackers,
      labelplus.common.config.autolabel.PROP_FILES: files,
      labelplus.common.config.autolabel.PROP_LABEL: [],
    }

    pm = deluge.component.get("CorePluginManager")
    if "Label" in pm.get_enabled_plugins():
      label = status.get("label")
      props[labelplus.common.config.autolabel.PROP_LABEL] = [label]

    return labelplus.common.config.autolabel.find_match(props,
      rules, match_all)


  def _find_autolabel_match(self, torrent_id):

    assert(torrent_id in self._torrents)

    label_ids = self._get_sorted_labels(cmp_length_then_value)

    for id in label_ids:
      if self._labels[id]["options"]["autolabel_settings"]:
        if self._has_autolabel_match(torrent_id, id):
          return id

    return labelplus.common.label.ID_NONE


  def _do_autolabel_torrent(self, torrent_id):

    assert(torrent_id in self._torrents)

    label_id = self._find_autolabel_match(torrent_id)
    if label_id != self._get_torrent_label_id(torrent_id):
      self._set_torrent_label(torrent_id, label_id)
      log.debug("Setting torrent %r to label %r", torrent_id, label_id)

      self._timestamp["mappings_changed"] = datetime.datetime.now()

    return label_id


  def _do_autolabel_torrents(self, label_id, apply_to_all=False):

    assert(label_id in self._labels)

    changed = False

    for id in self._torrents:
      if apply_to_all or id not in self._mappings:
        if self._has_autolabel_match(id, label_id):
          self._set_torrent_label(id, label_id)
          changed = True

    if changed:
      self._timestamp["mappings_changed"] = datetime.datetime.now()


  # Section: Torrent-Label: Path Options

  def _apply_move_completed_paths(self, label_id, sublabels=False):
    # Apply move completed options to torrents under given label

    assert(label_id in self._labels)

    options = self._labels[label_id]["options"]

    if options["download_settings"] and options["move_completed"]:
      for id in self._index[label_id]["torrents"]:
        self._torrents[id].set_move_completed_path(
          self._labels[label_id]["options"]["move_completed_path"])

    if sublabels:
      for id in self._index[label_id]["children"]:
        self._apply_move_completed_paths(id, sublabels)


  def _move_torrents(self, torrent_ids):
    # Move the specified torrents to where they should be

    assert(all(x in self._torrents for x in torrent_ids))

    for id in torrent_ids:
      torrent = self._torrents[id]
      status = torrent.get_status(["save_path", "move_completed_path"])

      dest_path = status["save_path"]
      label_id = self._mappings.get(id, labelplus.common.label.ID_NONE)

      if label_id == labelplus.common.label.ID_NONE:
        if torrent.handle.is_finished() and self._core["move_completed"]:
          dest_path = status["move_completed_path"]
      else:
        options = self._labels[label_id]["options"]
        if options["download_settings"]:
          if torrent.handle.is_finished() and \
              options[labelplus.common.config.PATH_MOVE_COMPLETED]:
            dest_path = options["%s_path" %
              labelplus.common.config.PATH_MOVE_COMPLETED]
          elif options[labelplus.common.config.PATH_DOWNLOAD_LOCATION]:
            dest_path = options["%s_path" %
              labelplus.common.config.PATH_DOWNLOAD_LOCATION]

      if dest_path != status["save_path"]:
        torrent.move_storage(dest_path)


  def _move_torrents_by_label(self, label_id, sublabels=False):
    # Move all torrents under the given label

    assert(label_id in self._labels)

    self._move_torrents(self._index[label_id]["torrents"])

    if sublabels:
      for id in self._index[label_id]["children"]:
        self._move_torrents_by_label(id, sublabels)
