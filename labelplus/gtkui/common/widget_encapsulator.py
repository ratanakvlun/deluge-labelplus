#
# widget_encapsulator.py
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


import gtk.glade

from labelplus.gtkui import RT


class WidgetEncapsulator(object):

  def __init__(self, filename, root, attr_prefix=""):

    self._model = None
    self._root_widget = None
    self._widgets = []

    self._attr_prefix = attr_prefix

    self._model = gtk.glade.XML(filename, root)
    RT.register(self._model, __name__)

    self._root_widget = self._model.get_widget(root)
    self._widgets = self._model.get_widget_prefix("")

    for widget in self._widgets:
      name = self._attr_prefix + widget.get_name()

      if not hasattr(self, name):
        setattr(self, name, widget)

      RT.register(widget, __name__)


  @property
  def valid(self):

    return self._root_widget is not None


  def get_widgets(self, prefix=""):

    return [x for x in self._widgets if x.get_name().startswith(prefix)]


  def connect_signals(self, map):

    if self._model:
      self._model.signal_autoconnect(map)


  def destroy(self):

    while len(self._widgets):
      widget = self._widgets.pop()
      name = self._attr_prefix + widget.get_name()

      attr_widget = getattr(self, name, None)
      if attr_widget is widget:
        delattr(self, name)

    if self._root_widget:
      self._root_widget.destroy()
      self._root_widget = None

    self._model = None
