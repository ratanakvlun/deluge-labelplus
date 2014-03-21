#
# name_input_dialog.py
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


import logging

import gtk

import deluge.component

import labelplus.common
import labelplus.common.label
import labelplus.gtkui.common.gtklib


from twisted.python.failure import Failure

from deluge.ui.client import client

from labelplus.common import LabelPlusError
from labelplus.gtkui.common.widgets.label_selection_menu import LabelSelectionMenu
from labelplus.gtkui.common.gtklib.widget_encapsulator import WidgetEncapsulator


from labelplus.common.label import (
  ID_NULL, RESERVED_IDS,
)

from labelplus.common.literals import (
  TITLE_ADD_LABEL, TITLE_RENAME_LABEL,

  STR_ADD_LABEL, STR_RENAME_LABEL, STR_PARENT, STR_NONE,

  ERR_TIMED_OUT, ERR_INVALID_TYPE,
  ERR_INVALID_LABEL, ERR_INVALID_PARENT, ERR_LABEL_EXISTS,
)

GLADE_FILE = labelplus.common.get_resource("wnd_name_input.glade")
ROOT_WIDGET = "wnd_name_input"

REQUEST_TIMEOUT = 10.0

TYPE_ADD = "add"
TYPE_RENAME = "rename"

DIALOG_SPECS = {
  TYPE_ADD: (_(TITLE_ADD_LABEL), gtk.STOCK_ADD, STR_ADD_LABEL),
  TYPE_RENAME: (_(TITLE_RENAME_LABEL), gtk.STOCK_EDIT, STR_RENAME_LABEL),
}

DIALOG_NAME = 0
DIALOG_ICON = 1
DIALOG_CONTEXT = 2


log = logging.getLogger(__name__)

from labelplus.gtkui import RT


class NameInputDialog(WidgetEncapsulator):

  # Section: Initialization

  def __init__(self, plugin, dialog_type, label_id):

    self._plugin = plugin
    self._type = dialog_type

    if self._type == TYPE_ADD:
      self._parent_id = label_id
    elif self._type == TYPE_RENAME:
      if label_id in plugin.store:
        self._parent_id = labelplus.common.label.get_parent_id(label_id)
        self._label_id = label_id
        self._label_name = plugin.store[label_id]["name"]
        self._label_fullname = plugin.store[label_id]["fullname"]
      else:
        raise LabelPlusError(ERR_INVALID_LABEL)
    else:
      raise LabelPlusError(ERR_INVALID_TYPE)

    self._store = None
    self._menu = None

    super(NameInputDialog, self).__init__(GLADE_FILE, ROOT_WIDGET, "_")

    try:
      self._store = plugin.store.copy()
      self._set_parent_label(self._parent_id)

      # Keep window alive with cyclic reference
      self._root_widget.set_data("owner", self)

      self._setup_widgets()

      self._load_state()

      self._create_menu()

      self._refresh()

      self._plugin.register_update_func(self.update_store)
      self._plugin.register_cleanup_func(self.destroy)
    except:
      self.destroy()
      raise


  def _setup_widgets(self):

    self._wnd_name_input.set_transient_for(
      deluge.component.get("MainWindow").window)

    spec = DIALOG_SPECS[self._type]
    self._wnd_name_input.set_title(spec[DIALOG_NAME])
    icon = self._wnd_name_input.render_icon(spec[DIALOG_ICON],
      gtk.ICON_SIZE_SMALL_TOOLBAR)
    self._wnd_name_input.set_icon(icon)

    self._lbl_header.set_markup("<b>%s:</b>" % _(STR_PARENT))

    self._img_error.set_from_stock(gtk.STOCK_DIALOG_ERROR,
      gtk.ICON_SIZE_SMALL_TOOLBAR)

    if self._type == TYPE_RENAME:
      self._btn_revert.show()
      self._txt_name.set_text(self._label_name)
      self._txt_name.grab_focus()

    self.connect_signals({
      "do_close" : self._do_close,
      "do_submit" : self._do_submit,
      "do_toggle_fullname": self._do_toggle_fullname,
      "do_open_select_menu": self._do_open_select_menu,
      "do_check_input": self._do_check_input,
      "do_revert": self._do_revert,
    })


  def _create_menu(self):

    def on_activate(widget, parent_id):

      self._select_parent_label(parent_id)


    def on_activate_parent(widget):

      parent_id = labelplus.common.label.get_parent_id(self._parent_id)
      self._select_parent_label(parent_id)


    def on_show_menu(menu):

      menu.show_all()

      if self._type == TYPE_RENAME:
        item = menu.get_label_item(self._label_id)
        if item:
          item.hide()

      parent_id = labelplus.common.label.get_parent_id(self._parent_id)
      if parent_id not in self._store:
        items[0].hide()


    root_items = (((gtk.MenuItem, _(STR_NONE)), on_activate, ID_NULL),)

    self._menu = LabelSelectionMenu(self._store.model, on_activate,
      root_items=root_items)
    self._menu.connect("show", on_show_menu)

    RT.register(self._menu, __name__)

    items = labelplus.gtkui.common.gtklib.menu_add_items(self._menu, 1,
      (((gtk.MenuItem, _(STR_PARENT)), on_activate_parent),))

    for item in items:
      RT.register(item, __name__)


  # Section: Deinitialization

  def destroy(self):

    self._plugin.deregister_update_func(self.update_store)
    self._plugin.deregister_cleanup_func(self.destroy)

    self._destroy_menu()
    self._destroy_store()

    if self.valid:
      self._root_widget.set_data("owner", None)
      super(NameInputDialog, self).destroy()


  def _destroy_menu(self):

    if self._menu:
      self._menu.destroy()
      self._menu = None


  def _destroy_store(self):

    if self._store:
      self._store.destroy()
      self._store = None


  # Section: Public

  def show(self):

    self._wnd_name_input.show()


  def update_store(self, store):

    if self._type == TYPE_RENAME:
      if self._label_id not in store:
        self._do_close()
        return

    self._destroy_store()
    self._store = store.copy()

    self._destroy_menu()
    self._create_menu()

    self._select_parent_label(self._parent_id)


  # Section: General

  def _report_error(self, error):

    log.error("%s: %s", DIALOG_SPECS[self._type][DIALOG_CONTEXT], error)
    self._set_error(error.tr())


  def _set_parent_label(self, parent_id):

    if parent_id in self._store:
      self._parent_id = parent_id
      self._parent_name = self._store[parent_id]["name"]
      self._parent_fullname = self._store[parent_id]["fullname"]
    else:
      self._parent_id = ID_NULL
      self._parent_name = _(STR_NONE)
      self._parent_fullname = _(STR_NONE)


  def _validate(self):

    if self._parent_id != ID_NULL and self._parent_id not in self._store:
      raise LabelPlusError(ERR_INVALID_PARENT)

    if self._type == TYPE_RENAME:
      if self._label_id not in self._store:
        raise LabelPlusError(ERR_INVALID_LABEL)

      if (self._label_id == self._parent_id or
          labelplus.common.label.is_ancestor(self._label_id,
            self._parent_id)):
        raise LabelPlusError(ERR_INVALID_PARENT)

    name = unicode(self._txt_name.get_text(), "utf8")
    labelplus.common.label.validate_name(name)

    for id in self._store.get_descendent_ids(self._parent_id, max_depth=1):
      if name == self._store[id]["name"]:
        raise LabelPlusError(ERR_LABEL_EXISTS)


  # Section: Widget State

  def _load_state(self):

    if self._plugin.initialized:
      pos = self._plugin.config["common"]["name_input_pos"]
      if pos:
        self._wnd_name_input.move(*pos)

      size = self._plugin.config["common"]["name_input_size"]
      if size:
        self._wnd_name_input.resize(*size)

      self._tgb_fullname.set_active(
        self._plugin.config["common"]["name_input_fullname"])


  def _save_state(self):

    if self._plugin.initialized:
      self._plugin.config["common"]["name_input_pos"] = \
        list(self._wnd_name_input.get_position())

      self._plugin.config["common"]["name_input_size"] = \
        list(self._wnd_name_input.get_size())

      self._plugin.config["common"]["name_input_fullname"] = \
        self._tgb_fullname.get_active()

      self._plugin.config.save()


  # Section: Widget Modifiers

  def _refresh(self):

    self._do_toggle_fullname()

    if self._parent_id == ID_NULL:
      self._lbl_selected_label.set_tooltip_text(None)
    else:
      self._lbl_selected_label.set_tooltip_text(self._parent_fullname)

    self._do_check_input()


  def _set_error(self, message):

    if message:
      self._img_error.set_tooltip_text(message)
      self._img_error.show()
    else:
      self._img_error.hide()


  def _select_parent_label(self, parent_id):

      self._set_parent_label(parent_id)
      self._refresh()
      self._txt_name.grab_focus()


  # Section: Widget Handlers

  def _do_close(self, *args):

    self._save_state()
    self.destroy()


  def _do_submit(self, *args):

    def on_timeout():

      if self.valid:
        self._wnd_name_input.set_sensitive(True)
        self._report_error(LabelPlusError(ERR_TIMED_OUT))


    def process_result(result):

      if self.valid:
        self._wnd_name_input.set_sensitive(True)

        if isinstance(result, Failure):
          error = labelplus.common.extract_error(result)
          if error:
            self._report_error(error)
          else:
            return result
        else:
          self._do_close()


    self._do_check_input()
    if not self._btn_ok.get_property("sensitive"):
      return

    name = unicode(self._txt_name.get_text(), "utf8")

    if self._parent_id != ID_NULL:
      dest_name = "%s/%s" % (self._parent_fullname, name)
    else:
      dest_name = name

    if self._type == TYPE_ADD:
      log.info("Adding label: %r", dest_name)
      deferred = client.labelplus.add_label(self._parent_id, name)
    elif self._type == TYPE_RENAME:
      log.info("Renaming label: %r -> %r", self._label_fullname, dest_name)
      deferred = client.labelplus.move_label(self._label_id, self._parent_id,
        name)

    labelplus.common.deferred_timeout(deferred, REQUEST_TIMEOUT, on_timeout,
      process_result, process_result)

    self._wnd_name_input.set_sensitive(False)


  def _do_toggle_fullname(self, *args):

    if self._tgb_fullname.get_active():
      self._lbl_selected_label.set_text(self._parent_fullname)
    else:
      self._lbl_selected_label.set_text(self._parent_name)


  def _do_open_select_menu(self, *args):

    if self._menu:
      self._menu.popup(None, None, None, 1, gtk.gdk.CURRENT_TIME)


  def _do_check_input(self, *args):

    try:
      self._validate()
      self._btn_ok.set_sensitive(True)
      self._set_error(None)
    except LabelPlusError as e:
      self._btn_ok.set_sensitive(False)
      self._set_error(e.tr())


  def _do_revert(self, *args):

    if self._type != TYPE_RENAME:
      return

    self._txt_name.set_text(self._label_name)

    parent_id = labelplus.common.label.get_parent_id(self._label_id)
    self._select_parent_label(parent_id)


# Wrapper Classes

class AddLabelDialog(NameInputDialog):

  def __init__(self, plugin, parent_id=ID_NULL):

    if parent_id in RESERVED_IDS:
      parent_id = ID_NULL

    super(AddLabelDialog, self).__init__(plugin, TYPE_ADD, parent_id)


class RenameLabelDialog(NameInputDialog):

  def __init__(self, plugin, label_id):

    if label_id in RESERVED_IDS:
      raise LabelPlusError(ERR_INVALID_LABEL)

    super(RenameLabelDialog, self).__init__(plugin, TYPE_RENAME, label_id)
