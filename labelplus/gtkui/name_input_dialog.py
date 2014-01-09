#
# name_input_dialog.py
#
# Copyright (C) 2014 Ratanak Lun <ratanakvlun@gmail.com>
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

from deluge import component
from deluge.ui.client import client
import deluge.configmanager

import labelplus.common.validation as Validation
from labelplus.common.file import get_resource
from labelplus.common.debug import debug

from labelplus.common.constant import NULL_PARENT
from labelplus.common.constant import GTKUI_CONFIG

from widget_encapsulator import WidgetEncapsulator


DIALOG_TYPES = {
  "add": (_("Add Label"), gtk.STOCK_ADD),
  "rename": (_("Rename Label"), gtk.STOCK_EDIT),
  "sublabel": (_("Add SubLabel"), gtk.STOCK_ADD),
}

DIALOG_NAME = 0
DIALOG_ICON = 1


class NameInputDialog(object):


  def __init__(self, method, label_id="", label_name=""):

    self.config = deluge.configmanager.ConfigManager(GTKUI_CONFIG)

    self.method = method
    self.label_id = label_id
    self.label_name = label_name

    self.close_func = None

    self.icon = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, 16, 16)
    self.icon.fill(0)

    self.type = DIALOG_TYPES[self.method]

    self.we = WidgetEncapsulator(get_resource("wnd_name_input.glade"))
    self.we.wnd_name_input.set_transient_for(
        component.get("MainWindow").window)
    self.we.wnd_name_input.set_destroy_with_parent(True)

    self.we.wnd_name_input.set_title(self.type[DIALOG_NAME])
    icon = self.we.wnd_name_input.render_icon(self.type[DIALOG_ICON],
        gtk.ICON_SIZE_SMALL_TOOLBAR)
    self.we.wnd_name_input.set_icon(icon)

    pos = self.config["name_input_pos"]
    if pos:
      self.we.wnd_name_input.move(*pos)

    size = self.config["name_input_size"]
    if size:
      size[1] = 1
      self.we.wnd_name_input.resize(*size)

    if self.method == "add":
      self.we.blk_header.hide()
    else:
      self.we.lbl_header.set_markup(
          "<b>%s</b>" % self.we.lbl_header.get_text())
      self.we.lbl_selected_label.set_text(self.label_name)
      self.we.lbl_selected_label.set_tooltip_text(self.label_name)

      if self.method == "rename":
        self.we.txt_name.set_text(self.label_name)
        self.we.txt_name.select_region(0, -1)

    self.we.model.signal_autoconnect({
      "cb_do_submit" : self.cb_do_submit,
      "cb_do_close" : self.cb_do_close,
      "on_txt_changed" : self.on_txt_changed,
    })

    self.we.btn_ok.set_sensitive(False)

    self.we.wnd_name_input.show()


  def register_close_func(self, func):

    self.close_func = func


  def cb_do_close(self, widget, event=None):

    self.config["name_input_pos"] = \
        list(self.we.wnd_name_input.get_position())
    self.config["name_input_size"] = \
        list(self.we.wnd_name_input.get_size())
    self.config.save()

    if self.close_func:
      self.close_func(self)

    self.we.wnd_name_input.destroy()


  def on_txt_changed(self, widget):

    value = self.we.txt_name.get_text()
    try:
      Validation.validate_name(value)

      self.we.btn_ok.set_sensitive(True)
      self.we.txt_name.set_icon_from_pixbuf(
          gtk.ENTRY_ICON_SECONDARY, self.icon)
      self.we.txt_name.set_icon_tooltip_text(gtk.ENTRY_ICON_SECONDARY, None)
    except Validation.LabelPlusError as e:
      self._set_error_hints(e.args[0])


  def cb_do_submit(self, widget):

    self.we.btn_ok.set_sensitive(False)
    self.label_name = self.we.txt_name.get_text()

    if self.method == "add":
      deferred = client.labelplus.add_label(NULL_PARENT, self.label_name)
    elif self.method == "sublabel":
      deferred = client.labelplus.add_label(self.label_id, self.label_name)
    elif self.method == "rename":
      deferred = client.labelplus.rename_label(self.label_id, self.label_name)

    deferred.addCallbacks(self.cb_do_submit_ok, self.cb_do_submit_err)


  @debug()
  def cb_do_submit_ok(self, result):

    self.label_id = result
    self.cb_do_close(None)


  @debug()
  def cb_do_submit_err(self, result):

    if result.value.exception_type == Validation.LabelPlusError.__name__:
      self._set_error_hints(result.value.exception_msg)
      result.cleanFailure()


  def _set_error_hints(self, message):

    self.we.btn_ok.set_sensitive(False)
    self.we.txt_name.set_icon_from_stock(
        gtk.ENTRY_ICON_SECONDARY, gtk.STOCK_NO)
    self.we.txt_name.set_icon_tooltip_text(
        gtk.ENTRY_ICON_SECONDARY, _(message))
