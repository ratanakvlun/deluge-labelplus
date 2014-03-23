#
# preferences_ext.py
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
import twisted.internet.reactor

import deluge.component

import labelplus.common
import labelplus.common.config
import labelplus.common.config.autolabel
import labelplus.gtkui.common.gtklib
import labelplus.gtkui.config


from twisted.python.failure import Failure

from deluge.ui.client import client

from labelplus.common import LabelPlusError
from labelplus.gtkui.common.widgets.autolabel_box import AutolabelBox
from labelplus.gtkui.common.gtklib.radio_button_group import RadioButtonGroup

from labelplus.gtkui.common.gtklib.widget_encapsulator import (
  WidgetEncapsulator)


from labelplus.common import (
  DISPLAY_NAME,
)

from labelplus.common.config import (
  MOVE_PARENT, MOVE_SUBFOLDER, MOVE_FOLDER,
)

from labelplus.common.literals import (
  TITLE_USER_INTERFACE, TITLE_DAEMON, TITLE_LABEL_DEFAULTS,
  TITLE_SELECT_FOLDER,

  STR_LOAD_PREFS, STR_SAVE_PREFS,

  ERR_TIMED_OUT,
)

GLADE_FILE = labelplus.common.get_resource("blk_preferences.glade")
ROOT_WIDGET = "blk_preferences"

REQUEST_TIMEOUT = 10.0

CLEAR_TEST_DELAY = 2.0

OP_MAP = {
  gtk.CheckButton: ("set_active", "get_active"),
  gtk.Entry: ("set_text", "get_text"),
  gtk.Label: ("set_text", "get_text"),
  gtk.RadioButton: ("set_active", "get_active"),
  gtk.SpinButton: ("set_value", "get_value"),
  AutolabelBox: ("set_all_row_values", "get_all_row_values"),
  RadioButtonGroup: ("set_active_value", "get_active_value"),
}

SETTER = 0
GETTER = 1


log = logging.getLogger(__name__)

from labelplus.gtkui import RT


class PreferencesExt(WidgetEncapsulator):

  # Section: Initialization

  def __init__(self, plugin):

    self._plugin = plugin
    self._manager = deluge.component.get("PluginManager")
    self._com_prefs = deluge.component.get("Preferences")

    self._prefs = {}
    self._handlers = []

    super(PreferencesExt, self).__init__(GLADE_FILE, ROOT_WIDGET, "_")

    try:
      self._setup_widgets()
      self._index_widgets()
      self._install_widgets()

      self._load_state()

      self._register_handlers()
    except:
      self.unload()
      raise


  def _setup_widgets(self):

    self._lbl_ui.set_markup("<b>%s</b>" % _(TITLE_USER_INTERFACE))
    self._lbl_daemon.set_markup("<b>%s</b>" % _(TITLE_DAEMON))
    self._lbl_defaults.set_markup("<b>%s</b>" % _(TITLE_LABEL_DEFAULTS))

    self._img_error.set_from_stock(gtk.STOCK_DIALOG_ERROR,
      gtk.ICON_SIZE_SMALL_TOOLBAR)

    self._setup_radio_button_groups()
    self._setup_autolabel_box()
    self._setup_test_combo_box()
    self._setup_criteria_area()

    self.connect_signals({
      "do_revert_to_defaults": self._do_revert_to_defaults,
      "do_toggle_dependents": self._do_toggle_dependents,
      "do_open_file_dialog": self._do_open_file_dialog,
      "do_test_criteria": self._do_test_criteria,
    })


  def _setup_radio_button_groups(self):

    rgrp = RadioButtonGroup((
      (self._rb_move_completed_to_parent, MOVE_PARENT),
      (self._rb_move_completed_to_subfolder, MOVE_SUBFOLDER),
      (self._rb_move_completed_to_folder, MOVE_FOLDER),
    ))

    rgrp.set_name("rgrp_move_completed_mode")
    self._rgrp_move_completed_mode = rgrp

    if __debug__: RT.register(rgrp, __name__)


  def _setup_autolabel_box(self):

    crbox = AutolabelBox(row_spacing=6, column_spacing=3)
    crbox.show_all()

    crbox.set_name("crbox_autolabel_rules")
    self._crbox_autolabel_rules = crbox

    self._blk_criteria_box.add(crbox)
    self._widgets.append(crbox)

    if __debug__: RT.register(crbox, __name__)


  def _setup_test_combo_box(self):

    prop_store = labelplus.gtkui.common.gtklib.liststore_create(str,
      [_(x) for x in labelplus.common.config.autolabel.PROPS])

    if __debug__: RT.register(prop_store, __name__)

    cell = gtk.CellRendererText()
    self._cmb_test_criteria.pack_start(cell)
    self._cmb_test_criteria.add_attribute(cell, "text", 0)
    self._cmb_test_criteria.set_model(prop_store)
    self._cmb_test_criteria.set_active(0)

    if __debug__: RT.register(cell, __name__)


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

      if self._plugin.config["common"]["prefs_pane_pos"] > -1:
        self._vp_criteria_area.set_position(
          self._vp_criteria_area.allocation.height -
          self._plugin.config["common"]["prefs_pane_pos"])

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

    self._ui_option_group = (
      self._chk_torrent_view_fullname,
      self._chk_filter_include_sublabels,
      self._chk_status_bar,
      self._chk_status_bar_include_sublabels,
    )

    self._daemon_option_group = (
      self._spn_shared_limit_update_interval,
      self._chk_move_on_changes,
      self._chk_move_after_recheck,
    )

    self._exp_group = (
      self._exp_download,
      self._exp_bandwidth,
      self._exp_queue,
      self._exp_autolabel,
    )

    self._option_groups = (
      (
        self._chk_download_settings,
        self._chk_move_completed,
        self._rgrp_move_completed_mode,
        self._txt_move_completed_path,
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
      self._chk_status_bar: (self._chk_status_bar_include_sublabels,),
    }


  def _install_widgets(self):

    self._manager.add_preferences_page(DISPLAY_NAME, self._blk_preferences)
    self._manager.register_hook("on_show_prefs", self._request_prefs)
    self._manager.register_hook("on_apply_prefs", self._save_prefs)


  def _register_handlers(self):

    self._register_handler(self._com_prefs.pref_dialog, "hide", self._on_hide)


  # Section: Deinitialization

  def unload(self):

    self._deregister_handlers()

    self._uninstall_widgets()

    super(PreferencesExt, self).destroy()


  def _deregister_handlers(self):

    for widget, handle in self._handlers:
      widget.disconnect(handle)


  def _uninstall_widgets(self):

    self._manager.deregister_hook("on_apply_prefs", self._save_prefs)
    self._manager.deregister_hook("on_show_prefs", self._request_prefs)
    self._manager.remove_preferences_page(DISPLAY_NAME)


  # Section: General

  def _register_handler(self, obj, signal, func, *args, **kwargs):

    handle = obj.connect(signal, func, *args, **kwargs)
    self._handlers.append((obj, handle))


  def _report_error(self, context, error):

    log.error("%s: %s", context, error)
    self._set_error(error.tr())


  # Section: Preferences

  def _request_prefs(self):

    def on_timeout():

      if self.valid:
        self._sw_settings.set_sensitive(True)
        self._report_error(STR_LOAD_PREFS, LabelPlusError(ERR_TIMED_OUT))


    def process_result(result):

      if self.valid:
        self._sw_settings.set_sensitive(True)

        if isinstance(result, Failure):
          error = labelplus.common.extract_error(result)
          if error:
            self._report_error(STR_LOAD_PREFS, error)
          else:
            return result
        else:
          self._prefs = result

          self._load_prefs(self._prefs)
          self._load_ui_options(self._plugin.config["common"])
          self._refresh()


    self._set_error(None)

    log.info("Loading preferences")

    deferred = client.labelplus.get_preferences()

    labelplus.common.deferred_timeout(deferred, REQUEST_TIMEOUT, on_timeout,
      process_result, process_result)

    self._sw_settings.set_sensitive(False)


  def _save_prefs(self):

    def on_timeout(prefs):

      if self.valid:
        self._sw_settings.set_sensitive(True)
        self._report_error(STR_SAVE_PREFS, LabelPlusError(ERR_TIMED_OUT))


    def process_result(result, prefs):

      if self.valid:
        self._sw_settings.set_sensitive(True)

        if isinstance(result, Failure):
          error = labelplus.common.extract_error(result)
          if error:
            self._report_error(STR_SAVE_PREFS, error)
          else:
            return result
        else:
          self._prefs = prefs
          self._save_ui_options()


    self._set_error(None)

    log.info("Saving preferences")

    prefs = self._get_prefs()
    options = self._get_ui_options()

    same = labelplus.common.dict_equals(prefs, self._prefs) and \
      labelplus.common.dict_equals(options, self._plugin.config["common"])

    if not same:
      deferred = client.labelplus.set_preferences(prefs)

      labelplus.common.deferred_timeout(deferred, REQUEST_TIMEOUT, on_timeout,
        process_result, process_result, prefs)

      self._sw_settings.set_sensitive(False)
    else:
      log.debug("No options were changed")


  # Section: Widget: State

  def _load_state(self):

    if not client.is_localhost():
      self._btn_browse.hide()

    if self._plugin.initialized:
      expanded = self._plugin.config["common"]["prefs_state"]
      for exp in expanded:
        widget = getattr(self, "_" + exp, None)
        if widget:
          widget.set_expanded(True)


  def _save_state(self):

    if self._plugin.initialized:
      expanded = []
      for exp in self._exp_group:
        if exp.get_expanded():
          expanded.append(exp.get_name())

      self._plugin.config["common"]["prefs_state"] = expanded

      if self._vp_criteria_area.get_data("was_mapped"):
        self._plugin.config["common"]["prefs_pane_pos"] = \
          self._vp_criteria_area.allocation.height - \
          self._vp_criteria_area.get_position()

      self._plugin.config.save()


  # Section: Widget: Preferences

  def _get_widget_values(self, widgets, options_out):

    for widget in widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options_out:
        ops = OP_MAP.get(type(widget))
        if ops:
          getter = getattr(widget, ops[GETTER])
          options_out[name] = getter()


  def _set_widget_values(self, widgets, options_in):

    for widget in widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options_in:
        ops = OP_MAP.get(type(widget))
        if ops:
          setter = getattr(widget, ops[SETTER])
          setter(options_in[name])


  def _load_prefs(self, prefs):

    self._set_widget_values(self._daemon_option_group,
      prefs["options"])

    for group in self._option_groups:
      self._set_widget_values(group, prefs["label"])


  def _get_prefs(self):

    prefs = copy.deepcopy(labelplus.common.config.CONFIG_DEFAULTS["prefs"])

    self._get_widget_values(self._daemon_option_group, prefs["options"])

    for group in self._option_groups:
      self._get_widget_values(group, prefs["label"])

    return prefs


  def _load_ui_options(self, options):

    self._set_widget_values(self._ui_option_group, options)


  def _get_ui_options(self):

    options = copy.deepcopy(self._plugin.config["common"])
    self._get_widget_values(self._ui_option_group, options)

    return options


  def _save_ui_options(self):

    self._get_widget_values(self._ui_option_group,
      self._plugin.config["common"])

    self._plugin.config.save()


  # Section: Widget: Modifiers

  def _refresh(self):

    for widget in self._dependency_widgets:
      self._toggle_dependents(widget)

    self._set_test_result(None)


  def _set_error(self, message):

    if message:
      self._img_error.set_tooltip_text(message)
      self._img_error.show()
    else:
      self._img_error.hide()


  def _set_test_result(self, result):

    if result is not None:
      icon = gtk.STOCK_YES if result else gtk.STOCK_NO
      self._txt_test_criteria.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY,
        icon)
    else:
      self._txt_test_criteria.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY,
        None)


  def _toggle_dependents(self, widget):

    if widget in self._dependency_widgets:
      toggled = widget.get_active()

      for dependent in self._dependency_widgets[widget]:
        dependent.set_sensitive(toggled)


  # Section: Widget: Handlers

  def _do_revert_to_defaults(self, widget):

    self._load_prefs(labelplus.common.config.CONFIG_DEFAULTS["prefs"])
    self._load_ui_options(labelplus.gtkui.config.CONFIG_DEFAULTS["common"])

    self._refresh()


  def _do_toggle_dependents(self, widget):

    self._toggle_dependents(widget)


  def _do_open_file_dialog(self, widget):

    def on_response(widget, response):

      if self.valid and response == gtk.RESPONSE_OK:
        self._txt_move_completed_path.set_text(widget.get_filename())

      widget.destroy()


    dialog = gtk.FileChooserDialog(_(TITLE_SELECT_FOLDER),
      self._blk_preferences.get_toplevel(),
      gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
      (
        gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
        gtk.STOCK_OK, gtk.RESPONSE_OK,
      )
    )
    if __debug__: RT.register(dialog, __name__)

    dialog.set_destroy_with_parent(True)
    dialog.connect("response", on_response)

    path = self._txt_move_completed_path.get_text()
    if not os.path.exists(path):
      path = ""

    dialog.set_filename(path)
    dialog.show_all()

    widgets = labelplus.gtkui.common.gtklib.widget_get_descendents(dialog,
      (gtk.ToggleButton,), 1)
    if widgets:
      location_toggle = widgets[0]
      location_toggle.set_active(False)


  def _do_test_criteria(self, *args):

    def clear_result():

      if self.valid:
        self._set_test_result(None)


    index = self._cmb_test_criteria.get_active()
    prop = labelplus.common.config.autolabel.PROPS[index]

    props = {
      prop: [unicode(self._txt_test_criteria.get_text(), "utf8")]
    }

    rules = self._crbox_autolabel_rules.get_all_row_values()
    match_all = self._rb_autolabel_match_all.get_active()

    log.debug("Properties: %r, Rules: %r, Match all: %s", props, rules,
      match_all)

    result = labelplus.common.config.autolabel.find_match(props, rules,
      match_all)

    log.debug("Test result: %s", result)
    self._set_test_result(result)

    twisted.internet.reactor.callLater(CLEAR_TEST_DELAY, clear_result)


  # Section: Deluge: Handlers

  def _on_hide(self, *args):

    self._save_state()
