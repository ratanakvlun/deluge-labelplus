#
# label_store.py
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


import copy
import logging

import gobject
import gtk

import labelplus.common.label
import labelplus.gtkui.common.gtklib


from labelplus.gtkui import RT


from labelplus.common.label import (
  ID_NULL, ID_ALL, ID_NONE, RESERVED_IDS,
)

from labelplus.common.literals import (
  STR_ALL, STR_NONE,
)


log = logging.getLogger(__name__)


class LabelStore(object):

  # Section: Constants

  LABEL_ID = 0
  LABEL_DATA = 1


  # Section: Initialization

  def __init__(self):

    self._data = {}
    self._map = {}
    self._store = None
    self.model = None


  # Section: Deinitialization

  def destroy(self):

    self.model = None
    self._store = None
    self._map = {}
    self._data = {}


  # Section: Public: General

  def __len__(self):

    return len(self._data)


  def __getitem__(self, id_):

    return self._data.get(id_)


  def __iter__(self):

    return iter(self._data)


  def __contains__(self, id_):

    return id_ in self._data


  def copy(self):

    return copy.copy(self)


  # Section: Public: Model

  def update(self, data):

    self._normalize_data(data)
    self._build_fullname_index(data)
    self._build_store(data)
    self._build_descendent_data()


  def get_model_iter(self, id_):

    if id_ in self._map and self.model:
      return self.model.convert_child_iter_to_iter(None, self._map[id_])

    return None


  def get_model_path(self, id_):

    iter_ = self.get_model_iter(id_)
    if iter_:
      return self.model.get_path(iter_)

    return None


  # Section: Public: Label

  def get_descendent_ids(self, id_, max_depth=-1):

    def add_descendents(iter_, depth):

      if max_depth != -1 and depth > max_depth:
        return

      children = labelplus.gtkui.common.gtklib.treemodel_get_children(
        self.model, iter_)

      for child in children:
        descendents.append(self.model[child][self.LABEL_ID])
        add_descendents(child, depth+1)


    descendents = []

    if id_ == ID_NULL or id_ in self._data:
      if self.model:
        iter_ = self.get_model_iter(id_)
        add_descendents(iter_, 1)

    return descendents


  def get_total_count(self, ids):

    sum = 0

    for id_ in ids:
      if id_ in self._data:
        sum += self._data[id_]["count"]

    return sum


  def is_user_label(self, id_):

    if id_ and id_ not in RESERVED_IDS and id_ in self._data:
      return True

    return False


  def user_labels(self, ids):

    if not ids:
      return False

    for id_ in ids:
      if not self.is_user_label(id_):
        return False

    return True


  # Section: Model: Update

  def _normalize_data(self, data):

    data[ID_ALL]["name"] = _(STR_ALL)
    data[ID_NONE]["name"] = _(STR_NONE)

    for id_ in data:
      try:
        data[id_]["name"] = unicode(data[id_]["name"], "utf8")
      except (TypeError, UnicodeDecodeError):
        pass


  def _build_fullname_index(self, data):

    def resolve_fullname(id_):

      parts = []

      while id_:
        parts.append(data[id_]["name"])
        id_ = labelplus.common.label.get_parent_id(id_)

      return "/".join(reversed(parts))


    for id_ in data:
      data[id_]["fullname"] = resolve_fullname(id_)


  def _build_store(self, data):

    def data_sort_asc(model, iter1, iter2):

      id1, data1 = model[iter1]
      id2, data2 = model[iter2]

      is_reserved1 = id1 in RESERVED_IDS
      is_reserved2 = id2 in RESERVED_IDS

      if is_reserved1 and is_reserved2:
        return cmp(id1, id2)
      elif is_reserved1:
        return -1
      elif is_reserved2:
        return 1

      return cmp(data1["name"], data2["name"])


    store = gtk.TreeStore(str, gobject.TYPE_PYOBJECT)
    store_map = {}

    if __debug__: RT.register(store, __name__)

    for id_ in sorted(data):
      if id_ in RESERVED_IDS:
        parent_id = ID_NULL
      else:
        parent_id = labelplus.common.label.get_parent_id(id_)

      parent_iter = store_map.get(parent_id)
      iter_ = store.append(parent_iter, [id_, data[id_]])
      store_map[id_] = iter_

    sorted_model = gtk.TreeModelSort(store)
    sorted_model.set_sort_func(self.LABEL_DATA, data_sort_asc)
    sorted_model.set_sort_column_id(self.LABEL_DATA, gtk.SORT_ASCENDING)

    if __debug__: RT.register(sorted_model, __name__)

    self._data = data
    self._map = store_map
    self._store = store
    self.model = sorted_model


  def _build_descendent_data(self):

    for id_ in self._data:
      self._data[id_]["children"] = self.get_descendent_ids(id_, 1)
      self._data[id_]["descendents"] = {}

      descendents = self.get_descendent_ids(id_)

      self._data[id_]["descendents"]["ids"] = descendents
      self._data[id_]["descendents"]["count"] = self.get_total_count(
        descendents)
