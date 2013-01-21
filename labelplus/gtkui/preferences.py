#
# preferences.py
#
# Copyright (C) 2013 Ratanak Lun <ratanakvlun@gmail.com>
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
#
# Deluge is free software.
#
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


import os.path
import gtk

from deluge import component
from deluge.ui.client import client
import deluge.configmanager

from labelplus.common.constant import DISPLAY_NAME
from labelplus.common.constant import OPTION_DEFAULTS
from labelplus.common.constant import LABEL_DEFAULTS
from labelplus.common.constant import GTKUI_CONFIG

from labelplus.common.file import get_resource
from labelplus.common.debug import debug

from util import textview_set_text
from util import textview_get_text
from widget_encapsulator import WidgetEncapsulator


OP_MAP = {
  gtk.RadioButton: ("set_active", "get_active"),
  gtk.CheckButton: ("set_active", "get_active"),
  gtk.SpinButton: ("set_value", "get_value"),
  gtk.Label: ("set_text", "get_text"),
}


class Preferences(object):


  def __init__(self):

    self.config = deluge.configmanager.ConfigManager(GTKUI_CONFIG)

    self.plugin = component.get("PluginManager")
    self.we = WidgetEncapsulator(get_resource("wnd_preferences.glade"))
    self.daemon_is_local = client.is_localhost()

    self.header_widgets = (
      self.we.lbl_general,
      self.we.lbl_defaults,
    )

    self.general_widgets = (
      self.we.chk_include_children,
    )

    self.defaults_widgets = (
      self.we.chk_download_settings,
      self.we.chk_move_data_completed,
      self.we.chk_prioritize_first_last,

      self.we.chk_bandwidth_settings,
      self.we.spn_max_download_speed,
      self.we.spn_max_upload_speed,
      self.we.spn_max_connections,
      self.we.spn_max_upload_slots,

      self.we.chk_queue_settings,
      self.we.chk_auto_managed,
      self.we.chk_stop_at_ratio,
      self.we.spn_stop_ratio,
      self.we.chk_remove_at_ratio,

      self.we.chk_auto_settings,
      self.we.rb_auto_name,
      self.we.rb_auto_tracker,
    )

    self.rgrp_move_data_completed = (
      self.we.rb_move_data_completed_to_parent,
      self.we.rb_move_data_completed_to_subfolder,
      self.we.rb_move_data_completed_to_folder,
    )

    self.exp_group = (
      self.we.exp_download,
      self.we.exp_bandwidth,
      self.we.exp_queue,
      self.we.exp_autolabel,
    )

    expanded = self.config["prefs_state"]
    for exp in expanded:
      widget = getattr(self.we, exp, None)
      if widget:
        widget.set_expanded(True)

    for header in self.header_widgets:
      heading = header.get_text()
      header.set_markup("<b>%s</b>" % heading)

    self.we.btn_defaults.connect("clicked", self._reset_preferences)

    if self.daemon_is_local:
      self.we.fcb_move_data_completed_select.show()
      self.we.txt_move_data_completed_entry.hide()
    else:
      self.we.fcb_move_data_completed_select.hide()
      self.we.txt_move_data_completed_entry.show()

    self.plugin.add_preferences_page(DISPLAY_NAME, self.we.blk_preferences)
    self.plugin.register_hook("on_show_prefs", self._load_settings)
    self.plugin.register_hook("on_apply_prefs", self._save_settings)

    self._load_settings()


  def unload(self):

    self.plugin.deregister_hook("on_apply_prefs", self._save_settings)
    self.plugin.deregister_hook("on_show_prefs", self._load_settings)
    self.plugin.remove_preferences_page(DISPLAY_NAME)


  @debug()
  def _reset_preferences(self, widget):

    self._load_general(OPTION_DEFAULTS)
    self._load_defaults(LABEL_DEFAULTS)


  def _load_settings(self, widget=None, data=None):

    client.labelplus.get_preferences().addCallback(self._do_load)


  @debug()
  def _save_settings(self):

    general = self._get_general()
    defaults = self._get_defaults()

    prefs = {
      "options": general,
      "defaults": defaults,
    }

    client.labelplus.set_preferences(prefs)

    expanded = []
    for exp in self.exp_group:
      if exp.get_expanded():
        expanded.append(exp.get_name())

    self.config["prefs_state"] = expanded
    self.config.save()


  @debug()
  def _do_load(self, prefs):

    general = prefs["options"]
    defaults = prefs["defaults"]

    self._load_general(general)
    self._load_defaults(defaults)


  def _load_general(self, general):

    options = dict(OPTION_DEFAULTS)
    options.update(general)

    for widget in self.general_widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options:
        widget_type = type(widget)
        if widget_type in OP_MAP:
          setter = getattr(widget, OP_MAP[widget_type][0])
          setter(options[name])


  def _get_general(self):

    options = dict(OPTION_DEFAULTS)

    for widget in self.general_widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options:
        widget_type = type(widget)
        if widget_type in OP_MAP:
          getter = getattr(widget, OP_MAP[widget_type][1])
          options[name] = getter()

    return options


  def _load_defaults(self, defaults):

    options = dict(LABEL_DEFAULTS)
    options.update(defaults)

    for widget in self.defaults_widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options:
        widget_type = type(widget)
        if widget_type in OP_MAP:
          setter = getattr(widget, OP_MAP[widget_type][0])
          setter(options[name])

    rb = getattr(self.we, "rb_move_data_completed_to_%s" %
        options["move_data_completed_mode"])
    rb.set_active(True)

    path = options["move_data_completed_path"]
    if self.daemon_is_local:
      self.we.fcb_move_data_completed_select.set_current_folder(path)
    else:
      self.we.txt_move_data_completed_entry.set_text(path)

    textview_set_text(self.we.tv_auto_queries,
        "\n".join(options["auto_queries"]))


  def _get_defaults(self):

    options = dict(LABEL_DEFAULTS)

    for widget in self.defaults_widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options:
        widget_type = type(widget)
        if widget_type in OP_MAP:
          getter = getattr(widget, OP_MAP[widget_type][1])
          options[name] = getter()

    options["max_upload_slots"] = int(options["max_upload_slots"])
    options["max_connections"] = int(options["max_connections"])

    for rb in self.rgrp_move_data_completed:
      if rb.get_active():
        prefix, sep, mode = rb.get_name().rpartition("_")
        options["move_data_completed_mode"] = mode

        break

    if options["move_data_completed_mode"] == "folder":
      if self.daemon_is_local:
        options["move_data_completed_path"] = \
            self.we.fcb_move_data_completed_select.get_current_folder()
      else:
        options["move_data_completed_path"] = \
            self.we.txt_move_data_completed_entry.get_text().strip()

    lines = textview_get_text(self.we.tv_auto_queries).split("\n")
    options["auto_queries"] = [x.strip() for x in lines if x.strip()]

    return options
