#
# label_options_dialog.py
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
import os

import gtk
import twisted.internet.defer
import twisted.internet.reactor

import deluge.component

import labelplus.common
import labelplus.common.label
import labelplus.common.config.autolabel
import labelplus.gtkui.common.gtklib


from twisted.python.failure import Failure

from deluge.ui.client import client

from labelplus.common import LabelPlusError
from labelplus.gtkui.common.widgets.autolabel_box import AutolabelBox
from labelplus.gtkui.common.gtklib.radio_button_group import RadioButtonGroup

from labelplus.gtkui.common.widgets.label_selection_menu import (
  LabelSelectionMenu)

from labelplus.gtkui.common.gtklib.widget_encapsulator import (
  WidgetEncapsulator)

from labelplus.gtkui import RT


from labelplus.common.label import ID_NULL, RESERVED_IDS
from labelplus.common.config.autolabel import PROPS

from labelplus.common.config import (
  MOVE_PARENT, MOVE_SUBFOLDER, MOVE_FOLDER,
  LABEL_DEFAULTS,
)

from labelplus.common.literals import (
  TITLE_LABEL_OPTIONS, TITLE_SELECT_FOLDER,
  STR_LOAD_OPTIONS, STR_SAVE_OPTIONS, STR_LABEL, STR_PARENT, STR_NONE,
  ERR_TIMED_OUT, ERR_INVALID_LABEL,
)


log = logging.getLogger(__name__)


class LabelOptionsDialog(WidgetEncapsulator):

  # Section: Constants

  GLADE_FILE = labelplus.common.get_resource("wnd_label_options.glade")
  ROOT_WIDGET = "wnd_label_options"

  REQUEST_TIMEOUT = 10.0
  CLEAR_TEST_DELAY = 2.0

  OP_MAP = {
    gtk.CheckButton: ("set_active", "get_active"),
    gtk.Label: ("set_text", "get_text"),
    gtk.RadioButton: ("set_active", "get_active"),
    gtk.SpinButton: ("set_value", "get_value"),
    AutolabelBox: ("set_all_row_values", "get_all_row_values"),
    RadioButtonGroup: ("set_active_value", "get_active_value"),
  }

  SETTER = 0
  GETTER = 1


  # Section: Initialization

  def __init__(self, plugin, label_id, page=0):

    self._plugin = plugin

    if label_id in RESERVED_IDS or label_id not in plugin.store:
      raise LabelPlusError(ERR_INVALID_LABEL)

    self._store = None
    self._menu = None

    self._label_defaults = {}
    self._move_path_options = {}
    self._label_options = {}

    super(LabelOptionsDialog, self).__init__(self.GLADE_FILE, self.ROOT_WIDGET,
      "_")

    try:
      self._store = plugin.store.copy()
      self._set_label(ID_NULL)

      # Keep window alive with cyclic reference
      self._root_widget.set_data("owner", self)

      self._setup_widgets()
      self._index_widgets()

      self._load_state()
      self._nb_tabs.set_current_page(page)

      self._create_menu()

      self._request_options(label_id)

      self._plugin.register_update_func(self.update_store)
      self._plugin.register_cleanup_func(self.destroy)
    except:
      self.destroy()
      raise


  # Section: Deinitialization

  def destroy(self):

    self._plugin.deregister_update_func(self.update_store)
    self._plugin.deregister_cleanup_func(self.destroy)

    self._destroy_menu()
    self._destroy_store()

    if self.valid:
      self._root_widget.set_data("owner", None)
      super(LabelOptionsDialog, self).destroy()


  def _destroy_store(self):

    if self._store:
      self._store.destroy()
      self._store = None


  # Section: Public

  def show(self):

    self._wnd_label_options.show()


  def update_store(self, store):

    if self._label_id not in store:
      self.destroy()
      return

    self._destroy_store()
    self._store = store.copy()

    self._destroy_menu()
    self._create_menu()

    self._request_options(self._label_id)


  # Section: General

  def _set_label(self, label_id):

    if label_id in self._store:
      self._label_id = label_id
      self._label_name = self._store[label_id]["name"]
      self._label_fullname = self._store[label_id]["fullname"]
    else:
      self._label_id = ID_NULL
      self._label_name = _(STR_NONE)
      self._label_fullname = _(STR_NONE)


  def _report_error(self, context, error):

    log.error("%s: %s", context, error)
    self._set_error(error.tr())


  # Section: Options

  def _request_options(self, label_id):

    def on_timeout():

      if self.valid:
        self._wnd_label_options.set_sensitive(True)
        self._report_error(STR_LOAD_OPTIONS, LabelPlusError(ERR_TIMED_OUT))


    def process_result(result):

      if self.valid:
        self._wnd_label_options.set_sensitive(True)

        for success, data in result:
          if not success:
            error = labelplus.common.extract_error(data)
            if error:
              self._report_error(STR_LOAD_OPTIONS, error)
            else:
              self.destroy()
            return

        self._label_defaults = result[0][1]
        self._move_path_options = result[1][1]
        self._label_options = result[2][1]

        self._load_options(self._label_options)
        self._enable_options()


    self._clear_options()
    self._disable_options()
    self._set_label(label_id)
    self._refresh()

    if not label_id in self._store:
      self._report_error(STR_LOAD_OPTIONS, LabelPlusError(ERR_INVALID_LABEL))
      return

    self._set_error(None)

    log.info("Loading options for %r", self._label_fullname)

    deferreds = []
    deferreds.append(client.labelplus.get_label_defaults())
    deferreds.append(client.labelplus.get_move_path_options(label_id))
    deferreds.append(client.labelplus.get_label_options(label_id))

    deferred = twisted.internet.defer.DeferredList(deferreds,
      consumeErrors=True)

    labelplus.common.deferred_timeout(deferred, self.REQUEST_TIMEOUT,
      on_timeout, process_result, None)

    self._wnd_label_options.set_sensitive(False)


  def _save_options(self):

    def on_timeout(options):

      if self.valid:
        self._wnd_label_options.set_sensitive(True)
        self._report_error(STR_SAVE_OPTIONS, LabelPlusError(ERR_TIMED_OUT))


    def process_result(result, options):

      if self.valid:
        self._wnd_label_options.set_sensitive(True)

        if isinstance(result, Failure):
          error = labelplus.common.extract_error(result)
          if error:
            self._report_error(STR_SAVE_OPTIONS, error)
          else:
            self.destroy()
            return result
        else:
          self._label_options = options


    if not self._label_id in self._store:
      self._report_error(STR_SAVE_OPTIONS, LabelPlusError(ERR_INVALID_LABEL))
      return

    self._set_error(None)

    log.info("Saving options for %r", self._label_fullname)

    options = self._get_options()
    same = labelplus.common.dict_equals(options, self._label_options)

    if self._chk_autolabel_retroactive.get_active():
      apply_to_all = not self._chk_autolabel_unlabeled_only.get_active()
    else:
      apply_to_all = None

    if not same or apply_to_all is not None:
      deferred = client.labelplus.set_label_options(self._label_id, options,
        apply_to_all)

      labelplus.common.deferred_timeout(deferred, self.REQUEST_TIMEOUT,
        on_timeout, process_result, process_result, options)

      self._wnd_label_options.set_sensitive(False)
    else:
      log.info("No options were changed")


  # Section: Dialog: Setup

  def _setup_widgets(self):

    self._wnd_label_options.set_transient_for(
      deluge.component.get("MainWindow").window)

    self._wnd_label_options.set_title(_(TITLE_LABEL_OPTIONS))
    icon = self._wnd_label_options.render_icon(gtk.STOCK_PREFERENCES,
      gtk.ICON_SIZE_SMALL_TOOLBAR)
    self._wnd_label_options.set_icon(icon)

    self._lbl_header.set_markup("<b>%s:</b>" % _(STR_LABEL))

    self._img_error.set_from_stock(gtk.STOCK_DIALOG_ERROR,
      gtk.ICON_SIZE_SMALL_TOOLBAR)

    self._btn_close.grab_focus()

    self._setup_radio_button_groups()
    self._setup_autolabel_box()
    self._setup_test_combo_box()
    self._setup_criteria_area()

    self._rgrp_move_completed_mode.connect("changed", self._do_select_mode)

    self.connect_signals({
      "do_close": self._do_close,
      "do_submit": self._do_submit,
      "do_open_select_menu": self._do_open_select_menu,
      "do_revert_to_defaults": self._do_revert_to_defaults,
      "do_toggle_fullname": self._do_toggle_fullname,
      "do_toggle_dependents": self._do_toggle_dependents,
      "on_txt_changed": self._on_txt_changed,
      "do_open_file_dialog": self._do_open_file_dialog,
      "do_test_criteria": self._do_test_criteria,
    })


  def _setup_radio_button_groups(self):

    rgrp = RadioButtonGroup((
      (self._rb_move_completed_to_parent, MOVE_PARENT),
      (self._rb_move_completed_to_subfolder, MOVE_SUBFOLDER),
      (self._rb_move_completed_to_folder, MOVE_FOLDER),
    ))
    if __debug__: RT.register(rgrp, __name__)

    rgrp.set_name("rgrp_move_completed_mode")
    self._rgrp_move_completed_mode = rgrp


  def _setup_autolabel_box(self):

    crbox = AutolabelBox(row_spacing=6, column_spacing=3)
    if __debug__: RT.register(crbox, __name__)

    crbox.set_name("crbox_autolabel_rules")
    self._crbox_autolabel_rules = crbox
    self._blk_criteria_box.add(crbox)
    self._widgets.append(crbox)

    crbox.show_all()


  def _setup_test_combo_box(self):

    prop_store = labelplus.gtkui.common.gtklib.liststore_create(str,
      [_(x) for x in PROPS])
    if __debug__: RT.register(prop_store, __name__)

    cell = gtk.CellRendererText()
    if __debug__: RT.register(cell, __name__)

    self._cmb_test_criteria.pack_start(cell)
    self._cmb_test_criteria.add_attribute(cell, "text", 0)
    self._cmb_test_criteria.set_model(prop_store)
    self._cmb_test_criteria.set_active(0)


  def _setup_criteria_area(self):

    def on_mapped(widget, event):

      # Sometimes a widget is mapped but does not immediately have allocation
      if self._vp_criteria_area.allocation.x < 0:
        twisted.internet.reactor.callLater(0.1, widget.emit, "map-event",
          event)
        return

      if widget.handler_is_connected(handle):
        widget.disconnect(handle)

      self._vp_criteria_area.set_data("was_mapped", True)

      if self._plugin.config["common"]["label_options_pane_pos"] > -1:
        self._vp_criteria_area.set_position(
          self._vp_criteria_area.allocation.height -
          self._plugin.config["common"]["label_options_pane_pos"])

        clamp_position(self._vp_criteria_area)


    def clamp_position(widget, *args):

      handle_size = widget.allocation.height - \
        widget.get_property("max-position")
      max_dist = self._hb_test_criteria.allocation.height + handle_size*2

      if widget.allocation.height - widget.get_position() > max_dist:
        twisted.internet.reactor.callLater(0.1, widget.set_position,
          widget.allocation.height - max_dist)
      elif widget.allocation.height - widget.get_position() < max_dist:
        twisted.internet.reactor.callLater(0.1, widget.set_position,
          widget.allocation.height)


    handle = self._eb_criteria_area.connect("map-event", on_mapped)

    self._vp_criteria_area.connect("button-release-event", clamp_position)
    self._vp_criteria_area.connect("accept-position", clamp_position)


  def _index_widgets(self):

    self._option_groups = (
      (
        self._chk_download_settings,
        self._chk_move_completed,
        self._rgrp_move_completed_mode,
        self._lbl_move_completed_path,
        self._chk_prioritize_first_last,
      ),
      (
        self._chk_bandwidth_settings,
        self._rb_shared_limit,
        self._spn_max_download_speed,
        self._spn_max_upload_speed,
        self._spn_max_connections,
        self._spn_max_upload_slots,
      ),
      (
        self._chk_queue_settings,
        self._chk_auto_managed,
        self._chk_stop_at_ratio,
        self._spn_stop_ratio,
        self._chk_remove_at_ratio,
      ),
      (
        self._chk_autolabel_settings,
        self._rb_autolabel_match_all,
        self._crbox_autolabel_rules,
      ),
    )

    self._dependency_widgets = {
      self._chk_download_settings: (self._blk_download_settings_group,),
      self._chk_bandwidth_settings: (self._blk_bandwidth_settings_group,),
      self._chk_queue_settings: (self._blk_queue_settings_group,),
      self._chk_autolabel_settings: (self._blk_autolabel_settings_group,),

      self._chk_move_completed: (self._blk_move_completed_group,),
      self._rb_move_completed_to_folder: (self._txt_move_completed_path,),

      self._chk_stop_at_ratio:
        (self._spn_stop_ratio, self._chk_remove_at_ratio),

      self._chk_autolabel_retroactive: (self._chk_autolabel_unlabeled_only,),
    }


  # Section: Dialog: State

  def _load_state(self):

    if not client.is_localhost():
      self._btn_browse.hide()

    if self._plugin.initialized:
      pos = self._plugin.config["common"]["label_options_pos"]
      if pos:
        self._wnd_label_options.move(*pos)

      size = self._plugin.config["common"]["label_options_size"]
      if size:
        self._wnd_label_options.resize(*size)

      self._tgb_fullname.set_active(
        self._plugin.config["common"]["label_options_fullname"])


  def _save_state(self):

    if self._plugin.initialized:
      self._plugin.config["common"]["label_options_pos"] = \
        list(self._wnd_label_options.get_position())

      self._plugin.config["common"]["label_options_size"] = \
        list(self._wnd_label_options.get_size())

      self._plugin.config["common"]["label_options_fullname"] = \
        self._tgb_fullname.get_active()

      if self._vp_criteria_area.get_data("was_mapped"):
        self._plugin.config["common"]["label_options_pane_pos"] = \
          self._vp_criteria_area.allocation.height - \
          self._vp_criteria_area.get_position()

      self._plugin.config.save()


  # Section: Dialog: Options

  def _get_widget_values(self, widgets, options_out):

    for widget in widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options_out:
        ops = self.OP_MAP.get(type(widget))
        if ops:
          getter = getattr(widget, ops[self.GETTER])
          options_out[name] = getter()


  def _set_widget_values(self, widgets, options_in):

    for widget in widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options_in:
        ops = self.OP_MAP.get(type(widget))
        if ops:
          setter = getattr(widget, ops[self.SETTER])
          setter(options_in[name])


  def _load_options(self, options):

    for group in self._option_groups:
      self._set_widget_values(group, options)

    mode = options["move_completed_mode"]
    path = options["move_completed_path"]

    self._txt_move_completed_path.set_text(path)

    if mode != MOVE_FOLDER:
      path = self._move_path_options.get(mode, "")

    self._set_path_label(path)


  def _get_options(self):

    options = copy.deepcopy(self._label_defaults)

    for group in self._option_groups:
      self._get_widget_values(group, options)

    return options


  def _revert_options_by_page(self, options_out, page):

    widgets = self._option_groups[page]

    for widget in widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in self._label_defaults:
        options_out[name] = copy.deepcopy(self._label_defaults[name])


  def _clear_options(self):

    if not self._label_defaults:
      self._label_defaults = LABEL_DEFAULTS

    self._move_path_options = {}
    self._label_options = {}

    self._load_options(self._label_defaults)


  def _enable_options(self):

    self._nb_tabs.set_sensitive(True)
    self._btn_defaults.set_sensitive(True)
    self._btn_defaults_all.set_sensitive(True)
    self._btn_apply.set_sensitive(True)


  def _disable_options(self):

    self._nb_tabs.set_sensitive(False)
    self._btn_defaults.set_sensitive(False)
    self._btn_defaults_all.set_sensitive(False)
    self._btn_apply.set_sensitive(False)


  # Section: Dialog: Modifiers

  def _refresh(self):

    self._do_toggle_fullname()

    if self._label_id == ID_NULL:
      self._lbl_selected_label.set_tooltip_text(None)
    else:
      self._lbl_selected_label.set_tooltip_text(self._label_fullname)

    for widget in self._dependency_widgets:
      self._do_toggle_dependents(widget)

    self._set_test_result(None)


  def _set_path_label(self, path):

    self._lbl_move_completed_path.set_text(path)
    self._lbl_move_completed_path.set_tooltip_text(path)


  def _set_test_result(self, result):

    if result is not None:
      icon = gtk.STOCK_YES if result else gtk.STOCK_NO
      self._txt_test_criteria.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY,
        icon)
    else:
      self._txt_test_criteria.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY,
        None)


  def _set_error(self, message):

    if message:
      self._img_error.set_tooltip_text(message)
      self._img_error.show()
    else:
      self._img_error.hide()


  # Section: Dialog: Handlers

  # General

  def _do_close(self, *args):

    self._save_state()
    self.destroy()


  def _do_submit(self, *args):

    self._save_options()


  def _do_open_select_menu(self, *args):

    if self._menu:
      self._menu.popup(None, None, None, 1, gtk.gdk.CURRENT_TIME)


  def _do_revert_to_defaults(self, widget):

    if widget is self._btn_defaults:
      options = self._get_options()
      self._revert_options_by_page(options, self._nb_tabs.get_current_page())
    else:
      options = self._label_defaults

    self._load_options(options)
    self._refresh()


  def _do_toggle_fullname(self, *args):

    if self._tgb_fullname.get_active():
      self._lbl_selected_label.set_text(self._label_fullname)
    else:
      self._lbl_selected_label.set_text(self._label_name)


  def _do_toggle_dependents(self, widget):

    if widget in self._dependency_widgets:
      toggled = widget.get_active()

      for dependent in self._dependency_widgets[widget]:
        dependent.set_sensitive(toggled)


  # Move Completed

  def _do_select_mode(self, group, button, mode):

    self._do_toggle_dependents(self._rb_move_completed_to_folder)

    if mode == MOVE_FOLDER:
      self._on_txt_changed(self._txt_move_completed_path)
    else:
      path = self._move_path_options.get(mode, "")
      self._set_path_label(path)


  def _on_txt_changed(self, widget):

    self._set_path_label(widget.get_text())


  def _do_open_file_dialog(self, widget):

    def on_response(widget, response):

      if self.valid and response == gtk.RESPONSE_OK:
        self._txt_move_completed_path.set_text(widget.get_filename())

      widget.destroy()


    dialog = gtk.FileChooserDialog(_(TITLE_SELECT_FOLDER),
      self._wnd_label_options, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
      (
        gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
        gtk.STOCK_OK, gtk.RESPONSE_OK,
      )
    )

    RT.register(dialog, __name__)
    dialog.set_destroy_with_parent(True)
    dialog.connect("response", on_response)

    path = self._txt_move_completed_path.get_text()
    if not os.path.exists(path):
      path = ""

    dialog.set_filename(path)
    dialog.show_all()

    location_toggle = labelplus.gtkui.common.gtklib.widget_get_descendents(
      dialog, (gtk.ToggleButton,), 1)[0]
    location_toggle.set_active(False)


  # Autolabel Test

  def _do_test_criteria(self, *args):

    def clear_result():

      if self.valid:
        self._set_test_result(None)


    index = self._cmb_test_criteria.get_active()
    prop_name = PROPS[index]

    props = {
      prop_name: [unicode(self._txt_test_criteria.get_text(), "utf8")]
    }

    rules = self._crbox_autolabel_rules.get_all_row_values()
    match_all = self._rb_autolabel_match_all.get_active()

    log.debug("Properties: %r, Rules: %r, Match all: %s", props, rules,
      match_all)

    result = labelplus.common.config.autolabel.find_match(props, rules,
      match_all)

    log.debug("Test result: %s", result)
    self._set_test_result(result)

    twisted.internet.reactor.callLater(self.CLEAR_TEST_DELAY, clear_result)


  # Section: Dialog: Menu

  def _create_menu(self):

    def on_show_menu(widget):

      parent_id = labelplus.common.label.get_parent_id(self._label_id)
      if parent_id in self._store:
        items[0].show()
        items[1].show()
      else:
        items[0].hide()
        items[1].hide()


    def on_activate(widget, label_id):

      self._request_options(label_id)


    def on_activate_parent(widget):

      parent_id = labelplus.common.label.get_parent_id(self._label_id)
      self._request_options(parent_id)


    self._menu = LabelSelectionMenu(self._store.model, on_activate)
    if __debug__: RT.register(self._menu, __name__)

    items = labelplus.gtkui.common.gtklib.menu_add_items(self._menu, 0,
      (
        ((gtk.MenuItem, _(STR_PARENT)), on_activate_parent),
        ((gtk.SeparatorMenuItem,),),
      )
    )

    if __debug__:
      for item in items:
        RT.register(item, __name__)

    self._menu.connect("show", on_show_menu)
    self._menu.show_all()


  def _destroy_menu(self):

    if self._menu:
      self._menu.destroy()
      self._menu = None
