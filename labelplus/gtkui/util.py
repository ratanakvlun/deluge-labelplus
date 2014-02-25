#
# util.py
#
# Copyright (C) 2013 Ratanak Lun <ratanakvlun@gmail.com>
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


import gtk


def textview_set_text(textview, text):

  buff = textview.get_buffer()
  buff.set_text(text)
  textview.set_buffer(buff)


def textview_get_text(textview):

  buff = textview.get_buffer()

  return buff.get_text(buff.get_start_iter(), buff.get_end_iter())


def treemodel_recurse(model, root, pre_func=None,
    post_func=None, user_data=None):

  abort = None

  if pre_func:
    if user_data:
      abort = pre_func(model, root, user_data)
    else:
      abort = pre_func(model, root)

  if abort:
    return abort

  children = []

  iter = model.iter_children(root)
  while iter is not None:
    children.append(iter)
    iter = model.iter_next(iter)

  for child in children:
    abort = treemodel_recurse(model, child, pre_func, post_func, user_data)
    if abort:
      return abort

  if post_func:
    if user_data:
      abort = post_func(model, root, user_data)
    else:
      abort = post_func(model, root)

  return abort
