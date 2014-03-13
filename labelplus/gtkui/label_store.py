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
import labelplus.gtkui.common

from labelplus.gtkui import RT


LABEL_ID = 0
LABEL_DATA = 1


log = logging.getLogger(__name__)


class LabelStore(object):

  # Section: Initialization

  def __init__(self):

    self._data = None
    self._store = None
    self._map = None
    self.model = None


  # Section: Public: General

  def __len__(self):

    return len(self._data)


  def __getitem__(self, id):

    return self._data[id]


  def __iter__(self):

    return iter(self._data)


  def __contains__(self, id):

    return id in self._data


  def copy(self):

    return copy.copy(self)


  def destroy(self):

    self.model = None
    self._map = None
    self._store = None
    self._data = None


  # Section: Public: Store

  def update(self, data):

    self._normalize_data(data)
    self._build_fullname_index(data)
    self._build_store(data)


  def get_model_iter(self, id):

    if id in self._map:
      return self.model.convert_child_iter_to_iter(None, self._map[id])
    else:
      return None


  # Section: Public: Label

  def get_descendent_ids(self, id, max_depth=-1):

    if id != labelplus.common.label.ID_NULL and id not in self._data:
      return []

    def add_descendents(iter, depth):

      if max_depth != -1 and depth > max_depth:
        return

      children = labelplus.gtkui.common.treemodel_get_children(
        self.model, iter)

      for child in children:
        descendents.append(self.model[child][LABEL_ID])
        add_descendents(child, depth+1)


    descendents = []

    iter = self.get_model_iter(id)
    add_descendents(iter, 1)

    return descendents


  # Section: Data

  def _normalize_data(self, data):

    for id in labelplus.common.label.RESERVED_IDS:
      if id in data:
        data[id]["name"] = _(id)


  def _build_fullname_index(self, data):

    def resolve_fullname(id):

      parts = []

      while id:
        parts.append(data[id]["name"])
        id = labelplus.common.label.get_parent_id(id)

      return "/".join(reversed(parts))


    for id in data:
      data[id]["fullname"] = resolve_fullname(id)


  def _build_store(self, data):

    def data_sort_asc(model, iter1, iter2):

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

    for id in sorted(data):
      if id in labelplus.common.label.RESERVED_IDS:
        parent_id = labelplus.common.label.ID_NULL
      else:
        parent_id = labelplus.common.label.get_parent_id(id)

      parent_iter = store_map.get(parent_id)
      iter = store.append(parent_iter, [id, data[id]])
      store_map[id] = iter

    sorted_model = gtk.TreeModelSort(store)
    sorted_model.set_sort_func(LABEL_DATA, data_sort_asc)
    sorted_model.set_sort_column_id(LABEL_DATA, gtk.SORT_ASCENDING)

    self._data = data
    self._store = store
    self._map = store_map

    self.model = sorted_model

    RT.register(store, __name__)
    RT.register(sorted_model, __name__)
