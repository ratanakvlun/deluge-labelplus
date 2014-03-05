#
# __init__.py
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


import gtk

from labelplus.gtkui import RT


def textview_set_text(textview, text):

  buff = textview.get_buffer()
  buff.set_text(text)
  textview.set_buffer(buff)


def textview_get_text(textview):

  buff = textview.get_buffer()

  return buff.get_text(buff.get_start_iter(), buff.get_end_iter())


def treemodel_get_children(model, iter=None):

  if iter:
    return [x.iter for x in model[iter].iterchildren()]
  else:
    return [x.iter for x in model]


def menu_add_items(menu, items, *args, **kwargs):

  menu_items = []

  for name, on_activate in items:
    item = gtk.MenuItem(name); RT.register(item, __name__)

    if on_activate:
      item.connect("activate", on_activate, *args, **kwargs)

    menu.append(item)
    menu_items.append(item)

  return menu_items


def menu_add_separator(menu):

  sep = gtk.SeparatorMenuItem(); RT.register(sep, __name__)
  menu.append(sep)

  return sep
