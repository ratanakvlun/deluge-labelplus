#
# core.py
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

import twisted.internet.reactor

import deluge.common
import deluge.configmanager
import deluge.component
import deluge.core.rpcserver
import deluge.plugins.pluginbase

import labelplus.common
import labelplus.common.label
import labelplus.common.config
import labelplus.common.config.convert
import labelplus.common.config.autolabel

import labelplus.core.config.convert


CORE_CONFIG = "%s.conf" % labelplus.common.MODULE_NAME
DELUGE_CORE_CONFIG = "core.conf"

log = logging.getLogger(__name__)
log.addFilter(labelplus.common.LOG_FILTER)


def cmp_length_then_value(x, y):

  if len(x) > len(y): return -1
  if len(x) < len(y): return 1

  return cmp(x, y)


def check_init(func):

  def wrap(*args, **kwargs):

    if args and isinstance(args[0], Core):
      if not args[0]._initialized:
        raise RuntimeError("Plugin %r not initialized" %
          labelplus.common.PLUGIN_NAME)

    return func(*args, **kwargs)


  return wrap


class Core(deluge.plugins.pluginbase.CorePluginBase):

  # Section: Initialization

  def __init__(self, plugin_name):

    super(Core, self).__init__(plugin_name)
    self._initialized = False


  def enable(self):

    log.debug("Initializing Core...")

    self._core = deluge.configmanager.ConfigManager(DELUGE_CORE_CONFIG)
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

    if not deluge.component.get("TorrentManager").session_started:
      deluge.component.get("EventManager").register_event_handler(
        "SessionStartedEvent", self._initialize)
      log.debug("Waiting for session to start...")
    else:
      self._initialize()


  def _load_config(self):

    config = deluge.configmanager.ConfigManager(CORE_CONFIG)

    if not config.config:
      config.config.update(copy.deepcopy(
        labelplus.common.config.CONFIG_DEFAULTS))
      labelplus.common.config.set_version(config,
        labelplus.common.config.CONFIG_VERSION)

    file_ver = labelplus.common.config.get_version(config)
    ver = file_ver
    while ver != labelplus.common.config.CONFIG_VERSION:
      if ver < labelplus.common.config.CONFIG_VERSION:
        key = (ver, ver+1)
      else:
        key = (ver, ver-1)

      spec = labelplus.core.config.convert.CONFIG_SPECS.get(key)
      if spec:
        labelplus.common.config.convert.convert(spec,
          config, strict_paths=True)
        ver = labelplus.common.config.get_version(config)
      else:
        raise ValueError("Config file conversion v%s->v%s not supported" %
          (file_ver, labelplus.common.config.CONFIG_VERSION))

    for key in config.config.keys():
      if key not in labelplus.common.config.CONFIG_DEFAULTS:
        del config.config[key]

    return config


  def _initialize(self):

    log.debug("Resuming initialization...")

    deluge.component.get("EventManager").deregister_event_handler(
      "SessionStartedEvent", self._initialize)

    self._torrents = deluge.component.get("TorrentManager").torrents

    self._normalize_data()
    self._build_index()
    self._remove_orphans()
    self._build_full_name_index()
    self._apply_label_options()

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

    self._initialized = True

    twisted.internet.reactor.callLater(1, self._shared_limit_update_loop)

    log.debug("Core initialized")


  def _normalize_data(self):

    self._normalize_options(self._prefs["options"])
    self._normalize_label_options(self._prefs["defaults"])

    for id in labelplus.common.label.RESERVED_IDS:
      if id in self._labels:
        del self._labels[id]

    for id in self._labels:
      self._normalize_label_options(self._labels[id]["data"],
        self._prefs["defaults"])


  def _build_index(self):

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
    shared_limit_index = []

    index[NULL_PARENT] = build_label_entry(NULL_PARENT)

    for id in self._labels:
      index[id] = build_label_entry(id)

      if (self._labels[id]["data"]["bandwidth_settings"] and
          self._labels[id]["data"]["shared_limit_on"]):
        shared_limit_index.append(id)

    self._index = index
    self._shared_limit_index = shared_limit_index


  def _remove_orphans(self):

    removals = []

    for id in self._labels:
      parent_id = labelplus.common.label.get_parent_id(id)
      if (parent_id != labelplus.common.label.NULL_PARENT and
          parent_id not in self._labels):
        removals.append(id)

    for id in removals:
      self._remove_label(id)


  def _apply_label_options(self):

    for id in self._mappings.keys():
      if id in self._torrents:
        if self._mappings[id] in self._labels:
          self._apply_torrent_options(id)
          continue
        else:
          self._reset_torrent_options(id)

      self._remove_torrent_label(id)


  # Section: Deinitialization

  def disable(self):

    log.debug("Deinitializing Core...")

    deluge.component.get("EventManager").deregister_event_handler(
      "SessionStartedEvent", self._initialize)

    if getattr(self, "_config", None):
      if self._initialized:
        self._config.save()
      deluge.configmanager.close(CORE_CONFIG)

    if self._initialized:
      self._initialized = False

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

      deluge.component.get("FilterManager").deregister_filter(
        labelplus.common.STATUS_ID)

      self._rpc_deregister(labelplus.common.PLUGIN_NAME)

    log.debug("Core deinitialized")


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

    self._normalize_label_options(prefs["defaults"])
    self._prefs["defaults"].update(prefs["defaults"])

    self._config.save()


  # Section: Public API: Label: Queries

  @deluge.core.rpcserver.export
  @check_init
  def get_label_bandwidth_usages(self, label_ids):

    usages = {}

    for id in set(label_ids):
      if id == labelplus.common.label.ID_NONE or id in self._labels:
        usages[id] = self._get_label_bandwidth_usage(id)

    return usages


  @deluge.core.rpcserver.export
  @check_init
  def get_labels_summary(self, timestamp):

    if timestamp:
      t = cPickle.loads(timestamp)
    else:
      t = datetime.datetime(1, 1, 1)

    latest = max(
      self._timestamp["labels_changed"], self._timestamp["mappings_changed"])

    if t < latest:
      return self._get_labels_summary()
    else:
      return None


  # Section: Public API: Label: Modifiers

  @deluge.core.rpcserver.export
  @check_init
  def add_label(self, parent_id, label_name):

    log.debug("Adding %r to label %r", label_name, parent_id)

    if (parent_id != labelplus.common.label.NULL_PARENT and
        parent_id not in self._labels):
      raise ValueError("Invalid label: %r" % parent_id)

    id = self._add_label(parent_id, label_name)

    self._timestamp["labels_changed"] = datetime.datetime.now()

    return id


  @deluge.core.rpcserver.export
  @check_init
  def rename_label(self, label_id, label_name):

    log.debug("Renaming name of label %r to %r", label_id, label_name)

    if label_id not in self._labels:
      raise ValueError("Invalid label: %r" % label_id)

    self._rename_label(label_id, label_name)

    self._timestamp["labels_changed"] = datetime.datetime.now()


  @deluge.core.rpcserver.export
  @check_init
  def remove_label(self, label_id):

    log.debug("Removing label %r", label_id)

    if label_id not in self._labels:
      raise ValueError("Invalid label: %r" % label_id)

    count = len(self._index[label_id]["torrents"])

    self._remove_label(label_id)

    self._timestamp["labels_changed"] = datetime.datetime.now()
    if count:
      self._timestamp["mappings_changed"] = datetime.datetime.now()


  # Section: Public API: Label: Options

  @deluge.core.rpcserver.export
  @check_init
  def get_label_options(self, label_id):

    log.debug("Getting label options for %r", label_id)

    if label_id not in self._labels:
      raise ValueError("Invalid label: %r" % label_id)

    return self._labels[label_id]["data"]


  @deluge.core.rpcserver.export
  @check_init
  def set_label_options(self, label_id, options_in, apply_to_all=None):

    log.debug("Setting label options for %r", label_id)

    if label_id not in self._labels:
      raise ValueError("Invalid label: %r" % label_id)

    self._normalize_label_options(options_in, self._prefs["defaults"])
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
      raise ValueError("Invalid label: %r" % label_id)

    torrent_ids = [x for x in set(torrent_ids) if x in self._torrents]

    for id in torrent_ids:
      self._set_torrent_label(id, label_id)

    if torrent_ids:
      self._timestamp["mappings_changed"] = datetime.datetime.now()


  # Section: Public Callbacks

  @check_init
  def on_torrent_added(self, torrent_id):

    label_id = self._find_autolabel_match(torrent_id)
    if label_id:
      self._set_torrent_label(torrent_id, label_id)
      log.debug("Setting torrent %r to label %r", torrent_id, label_id)

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
        self._do_move_completed([torrent_id])


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
      elif (type(options[key]) !=
          type(labelplus.common.config.OPTION_DEFAULTS[key])):
        options[key] = copy.deepcopy(
          labelplus.common.config.OPTION_DEFAULTS[key])

    for key in labelplus.common.config.OPTION_DEFAULTS:
      if key not in options:
        options[key] = copy.deepcopy(
          labelplus.common.config.OPTION_DEFAULTS[key])

    if options["shared_limit_update_interval"] < 1:
      options["shared_limit_update_interval"] = 1


  # Section: Label: Queries


  def _get_unused_id(self, parent_id):

    i = 0
    label_obj = {}

    while label_obj is not None:
      id = "%s:%s" % (parent_id, i)
      label_obj = self._labels.get(id)
      i += 1

    return id


  def _get_children_names(self, parent_id):

    names = []
    for id in self._index[parent_id]["children"]:
      names.append(self._labels[id]["name"])

    return names


  def _validate_name(self, parent_id, label_name):

    labelplus.common.validate_name(label_name)

    names = self._get_children_names(parent_id)
    if label_name in names:
      raise ValueError("Label already exists: %r" % label_name)


  def _get_descendent_labels(self, label_id):

    descendents = []

    for id in self._index[label_id]["children"]:
      descendents.append(id)
      descendents += self._get_descendent_labels(id)

    return descendents


  def _get_parent_move_path(self, label_id):

    parent_id = labelplus.common.label.get_parent_id(label_id)
    if parent_id == labelplus.common.label.NULL_PARENT:
      path = self._get_deluge_move_path()
    else:
      path = self._labels[parent_id]["data"]["move_data_completed_path"]

    return path


  def _resolve_move_path(self, label_id):

    name = self._labels[label_id]["name"]
    options = self._labels[label_id]["data"]

    mode = options["move_data_completed_mode"]
    path = options["move_data_completed_path"]

    if mode != labelplus.common.config.MOVE_FOLDER:
      path = self._get_parent_move_path(label_id)

      if mode == labelplus.common.config.MOVE_SUBFOLDER:
        path = os.path.join(path, name)

    return path


  def _get_label_bandwidth_usage(self, label_id):

    torrent_ids = []

    if label_id == labelplus.common.label.ID_NONE:
      torrent_ids = self._get_unlabeled_torrents()
    else:
      for id in self._index[id]["torrents"]:
        if id in self._torrents:
          torrent_ids.append(id)

    return self._get_torrent_bandwidth_usage(torrent_ids)


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


  def _get_labels_summary(self):

    total = len(self._torrents)
    label_count = 0
    counts = {}

    label_ids = self._get_sorted_labels(cmp_length_then_value)

    for id in label_ids:
      count = len(self._index[id]["torrents"])
      label_count += count

      counts[id] = {
        "name": self._index[id]["full_name"],
        "count": count,
      }

    counts[labelplus.common.label.ID_ALL] = {
      "name": labelplus.common.label.ID_ALL,
      "count": total,
    }

    counts[labelplus.common.label.ID_NONE] = {
      "name": labelplus.common.label.ID_NONE,
      "count": total-label_count,
    }

    return counts


  # Section: Label: Modifiers

  def _add_label(self, parent_id, label_name):

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
      "data": copy.deepcopy(self._prefs["defaults"]),
    }

    self._index[id] = {
      "full_name": self._resolve_full_name(id),
      "children": [],
      "torrents": [],
    }

    options["move_data_completed_path"] = self._resolve_move_path(id)

    return id


  def _rename_label(self, label_id, label_name):

    label_name = label_name.strip()

    try:
      label_name = unicode(label_name, "utf8")
    except (TypeError, UnicodeDecodeError):
      pass

    self._validate_name(labelplus.common.label.get_parent_id(label_id),
      label_name)

    label = self._labels[label_id]
    label["name"] = label_name
    options = label["data"]

    self._build_full_name_index(label_id)
    self._update_move_completed_paths(label_id)

    if self._prefs["options"]["move_on_changes"]:
      self._do_move_completed_by_label(label_id, True)


  def _remove_label(self, label_id):

    parent_id = labelplus.common.label.get_parent_id(label_id)
    if parent_id in self._index:
      self._index[parent_id]["children"].remove(label_id)

    for id in list(self._index[label_id]["children"]):
      if id in self._labels:
        self._remove_label(id)

    torrent_ids = []

    for id in list(self._index[label_id]["torrents"]):
      if id in self._torrents:
        self._remove_torrent_label(id)
        torrent_ids.append(id)

    if self._prefs["options"]["move_on_changes"] and torrent_ids:
      self._do_move_completed(torrent_ids)

    del self._index[label_id]
    del self._labels[label_id]


  # Section: Label: Options

  def _normalize_label_options(self, options,
      template=labelplus.common.config.LABEL_DEFAULTS):

    for key in options.keys():
      if key not in template:
        del options[key]
      elif type(options[key]) != type(template[key]):
        options[key] = copy.deepcopy(template[key])

    for key in template:
      if key not in options:
        options[key] = copy.deepcopy(template[key])

    options["move_data_completed_path"] = \
      options["move_data_completed_path"].strip()

    if not options["move_data_completed_path"]:
      options["move_data_completed_mode"] = \
        labelplus.common.config.MOVE_FOLDER
      options["move_data_completed_path"] = self._get_deluge_move_path()

    if (options["move_data_completed_mode"] not in
        labelplus.common.config.MOVE_MODES):
      options["move_data_completed_mode"] = \
        labelplus.common.config.MOVE_FOLDER

    for rule in list(options["autolabel_rules"]):
      if len(rule) != labelplus.common.config.autolabel.NUM_FIELDS:
        options["autolabel_rules"].remove(rule)
        continue

      prop, op, case, query = rule
      if (prop not in labelplus.common.config.autolabel.PROPS or
          op not in labelplus.common.config.autolabel.OPS or
          case not in labelplus.common.config.autolabel.CASES or
          not query):
        options["autolabel_rules"].remove(rule)


  def _set_label_options(self, label_id, options_in, apply_to_all=None):

    options = self._labels[label_id]["data"]
    old = {
      "download_settings": options["download_settings"],
      "move_data_completed": options["move_data_completed"],
      "move_data_completed_path": options["move_data_completed_path"],
    }
    options.update(options_in)

    for id in self._index[label_id]["torrents"]:
      if id in self._torrents:
        self._apply_torrent_options(id)

    if label_id in self._shared_limit_index:
      self._shared_limit_index.remove(label_id)

    if options["bandwidth_settings"] and options["shared_limit_on"]:
      self._shared_limit_index.append(label_id)

    # If move completed was just turned on and move on changes enabled...
    if (options["download_settings"] and options["move_data_completed"] and
        (not old["download_settings"] or not old["move_data_completed"]) and
        self._prefs["options"]["move_on_changes"]):
      self._do_move_completed_by_label(label_id)

    if options["move_data_completed_path"] != old["move_data_completed_path"]:
    # Path was modified; make sure descendent paths are updated
      for id in self._index[label_id]["children"]:
        if id in self._labels:
          self._update_move_completed_paths(id)

          if self._prefs["options"]["move_on_changes"]:
            self._do_move_completed_by_label(id, True)

    if options["auto_settings"] and apply_to_all is not None:
      self._do_autolabel_torrents(label_id, apply_to_all)


  # Section: Label: Full Name

  def _resolve_full_name(self, label_id):

    parts = []
    id = label_id

    while id and id != labelplus.common.label.NULL_PARENT:
      parts.append(self._labels[id]["name"])
      id = labelplus.common.label.get_parent_id(id)

    full_name = "/".join(reversed(parts))

    return full_name


  def _build_full_name_index(self,
    label_id=labelplus.common.label.NULL_PARENT):

    assert(label_id in self._labels or
      label_id == labelplus.common.label.NULL_PARENT)

    self._index[label_id]["full_name"] = self._resolve_full_name(label_id)

    for id in self._index[label_id]["children"]:
      self._build_full_name_index(id)


  # Section: Label: Shared Limit

  def _shared_limit_update_loop(self):

    if self._initialized:
      for id in self._shared_limit_index:
        if id in self._labels:
          self._do_update_shared_limit(id)

      twisted.internet.reactor.callLater(
        self._prefs["options"]["shared_limit_update_interval"],
        self._shared_limit_update_loop)


  def _do_update_shared_limit(self, label_id):

    options = self._labels[label_id]["data"]
    shared_download_limit = options["max_download_speed"]
    shared_upload_limit = options["max_upload_speed"]

    if shared_download_limit < 0.0 and shared_upload_limit < 0.0:
      return

    torrent_ids = []
    for id in self._index[label_id]["torrents"]:
      if id in self._torrents:
        torrent_ids.append(id)

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

    label_id = self._mappings.get(torrent_id, labelplus.common.label.ID_NONE)

    if label_id == labelplus.common.label.ID_NONE:
      self._reset_torrent_options(torrent_id)
      return

    options = self._labels[label_id]["data"]
    torrent = self._torrents[torrent_id]

    if options["download_settings"]:
      torrent.set_move_completed(options["move_data_completed"])
      torrent.set_prioritize_first_last(options["prioritize_first_last"])

      if options["move_data_completed"]:
        torrent.set_move_completed_path(options["move_data_completed_path"])

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

    if self._prefs["options"]["show_full_name"]:
      name = self._get_full_label_name(label_id)
    else:
      name = self._labels[label_id]["name"]

    return name


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

    if torrent_id in self._mappings:
      self._remove_torrent_label(torrent_id)

    if label_id == labelplus.common.label.ID_NONE:
      self._reset_torrent_options(torrent_id)
    else:
      self._mappings[torrent_id] = label_id
      self._index[label_id]["torrents"].append(torrent_id)
      self._apply_torrent_options(torrent_id)


  # Section: Torrent-Label: Autolabel

  def _has_autolabel_match(self, torrent_id, label_id):

    status = self._torrents[torrent_id].get_status(["name", "trackers"])
    name = status["name"]
    trackers = [x["url"] for x in status["trackers"]]

    props = {
      labelplus.common.config.autolabel.PROP_NAME: [name],
      labelplus.common.config.autolabel.PROP_TRACKER: trackers,
    }

    options = self._labels[label_id]["data"]
    rules = options["autolabel_rules"]
    match_all = options["autolabel_match_all"]

    return labelplus.common.config.autolabel.find_match(
      props, rules, match_all)


  def _find_autolabel_match(self, torrent_id):

    labels = self._get_sorted_labels(cmp_length_then_value)

    for id in labels:
      if self._labels[id]["data"]["auto_settings"]:
        if self._has_autolabel_match(torrent_id, id):
          return id

    return labelplus.common.label.ID_NONE


  def _do_autolabel_torrents(self, label_id, apply_to_all=False):

    for id in self._torrents:
      if apply_to_all or id not in self._mappings:
        if self._has_autolabel_match(id, label_id):
          self._set_torrent_label(id, label_id)


  # Section: Torrent-Label: Move Completed

  def _apply_move_completed_path(self, label_id):

    for id in self._index[label_id]["torrents"]:
      self._torrents[id].set_move_completed_path(
          self._labels[label_id]["data"]["move_data_completed_path"])


  def _update_move_completed_paths(self, label_id):

    options = self._labels[label_id]["data"]

    path = self._resolve_move_path(label_id)
    if path == options["move_data_completed_path"]:
      return

    options["move_data_completed_path"] = path

    if options["download_settings"] and options["move_data_completed"]:
      self._apply_move_completed_path(label_id)

    for id in self._index[label_id]["children"]:
      self._update_move_completed_paths(id)


  def _do_move_completed(self, torrent_ids):

    for id in torrent_ids:
      torrent = self._torrents[id]
      status = torrent.get_status(
        ["save_path", "move_completed_path", "is_finished"])

      label_id = self._mappings.get(id, labelplus.common.label.ID_NONE)
      if label_id == labelplus.common.label.ID_NONE:
        dest_path = status["move_completed_path"]
      else:
        options = self._labels[label_id]["data"]
        dest_path = options["move_data_completed_path"]

      if status["is_finished"] and dest_path != status["save_path"]:
        torrent.move_storage(dest_path)


  def _do_move_completed_by_label(self, label_id, sublabels=False):

    options = self._labels[label_id]["data"]
    if options["download_settings"] and options["move_data_completed"]:
      torrent_ids = []

      for id in self._index[label_id]["torrents"]:
        if id in self._torrents:
          torrent_ids.append(id)

      self._do_move_completed(torrent_ids)

    if sublabels:
      for id in self._index[label_id]["children"]:
        if id in self._labels:
          self._do_move_completed_by_label(id, sublabels)
