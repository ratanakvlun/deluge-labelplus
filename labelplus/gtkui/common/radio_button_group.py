#
# radio_button_group.py
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


class RadioButtonGroup(object):

  def __init__(self, members=()):

    self._members = members
    self._group = None
    self._name = None

    for button, value in self._members:
      if not self._group:
        self._group = button
      elif button not in self._group.get_group():
        button.set_group(self._group)


  def get_name(self):

    return self._name


  def set_name(self, name):

    self._name = name


  def connect(self, signal, func, *args):

    def func_wrapper(widget, value, *args):

      if not widget.get_active():
        return

      func(self, widget, value, *args)


    if signal == "changed":
      for button, value in self._members:
        button.connect("toggled", func_wrapper, value, *args)


  def get_active_value(self):

    for button, value in self._members:
      if button.get_active():
        return value

    return None


  def set_active_value(self, value_in):

    for button, value in self._members:
      if value == value_in:
        button.set_active(True)
