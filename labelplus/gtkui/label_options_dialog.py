#
# label_options_dialog.py
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


import logging
import copy

import twisted.internet
import gtk

import deluge.component

from deluge.ui.client import client

import labelplus.common
import labelplus.common.config
import labelplus.common.config.autolabel

from labelplus.gtkui.autolabel_box import AutolabelBox
from labelplus.gtkui.widget_encapsulator import WidgetEncapsulator


SETTER = 0
GETTER = 1

OP_MAP = {
  gtk.RadioButton: ("set_active", "get_active"),
  gtk.CheckButton: ("set_active", "get_active"),
  gtk.SpinButton: ("set_value", "get_value"),
  gtk.Label: ("set_text", "get_text"),
  AutolabelBox: ("set_all_row_values", "get_all_row_values"),
}


log = logging.getLogger(__name__)


class LabelOptionsDialog(WidgetEncapsulator):

  # Section: Initialization

  def __init__(self, plugin, label_id, page=0):

    super(LabelOptionsDialog, self).__init__(
      labelplus.common.get_resource("wnd_label_options.glade"))

    self._plugin = plugin

    self._label_id = label_id
    self._name = self._plugin.data[label_id]["name"]

    self.nb_tabs.set_current_page(page)

    deferreds = []
    deferreds.append(client.labelplus.get_daemon_info())
    deferreds.append(client.labelplus.get_parent_move_path(self._label_id))
    deferreds.append(client.labelplus.get_preferences())
    deferreds.append(client.labelplus.get_label_options(self._label_id))

    deferred = twisted.internet.defer.DeferredList(deferreds)
    deferred.addCallback(self._finish_init)


  def _finish_init(self, result):

    for item in result:
      if not item[0]:
        raise RuntimeError("Could not get label options")

    try:
      self._path_module = __import__(result[0][1]["os.path"])
    except ImportError as e:
      self._path_module = os.path

    self._parent_move_path = result[1][1]
    self._defaults = result[2][1]["label"]
    options = result[3][1]

    self._setup_window()
    self._index_widgets()
    self._connect_signals()
    self._load_options(options)

    self.wnd_label_options.show_all()

    if client.is_localhost():
      self.txt_move_completed_entry.hide()
      self.fcb_move_completed_select.show()
    else:
      self.fcb_move_completed_select.hide()
      self.txt_move_completed_entry.show()


  def _setup_window(self):

    self.wnd_label_options.set_transient_for(
      deluge.component.get("MainWindow").window)
    self.wnd_label_options.set_destroy_with_parent(True)

    icon = self.wnd_label_options.render_icon(gtk.STOCK_PREFERENCES,
      gtk.ICON_SIZE_SMALL_TOOLBAR)
    self.wnd_label_options.set_icon(icon)

    pos = self._plugin.config["common"]["label_options_pos"]
    if pos: self.wnd_label_options.move(*pos)
    size = self._plugin.config["common"]["label_options_size"]
    if size: self.wnd_label_options.resize(*size)

    self.lbl_header.set_markup("<b>%s</b>" % self.lbl_header.get_text())
    self.lbl_selected_label.set_text(self._name)
    self.lbl_selected_label.set_tooltip_text(
      self._plugin.data[self._label_id]["fullname"])

    self.cr_autolabel_rules = AutolabelBox(row_spacing=3, column_spacing=3)
    self.cr_autolabel_rules.set_name("cr_autolabel_rules")
    self.blk_criteria_box.add(self.cr_autolabel_rules)


  def _index_widgets(self):

    self._option_widgets = (
      self.chk_download_settings,
      self.chk_move_completed,
      self.lbl_move_completed_path,
      self.chk_prioritize_first_last,

      self.chk_bandwidth_settings,
      self.rb_shared_limit,
      self.spn_max_download_speed,
      self.spn_max_upload_speed,
      self.spn_max_connections,
      self.spn_max_upload_slots,

      self.chk_queue_settings,
      self.chk_auto_managed,
      self.chk_stop_at_ratio,
      self.spn_stop_ratio,
      self.chk_remove_at_ratio,

      self.chk_autolabel_settings,
      self.rb_autolabel_match_all,
      self.cr_autolabel_rules,
    )

    self._dependent_widgets = {
      self.chk_download_settings: (self.blk_download_settings_group,),
      self.chk_bandwidth_settings: (self.blk_bandwidth_settings_group,),
      self.chk_queue_settings: (self.blk_queue_settings_group,),
      self.chk_autolabel_settings: (self.blk_autolabel_settings_group,),

      self.chk_move_completed: (self.blk_move_completed_group,),
      self.rb_move_completed_to_folder: (
        self.fcb_move_completed_select,
        self.txt_move_completed_entry
      ),

      self.chk_stop_at_ratio: (self.spn_stop_ratio, self.chk_remove_at_ratio),
      self.chk_auto_retroactive: (self.chk_auto_unlabeled,),
    }

    self._rgrp_move_completed = (
      self.rb_move_completed_to_parent,
      self.rb_move_completed_to_subfolder,
      self.rb_move_completed_to_folder,
    )


  def _connect_signals(self):

    self._model.signal_autoconnect({
      "on_btn_ok_clicked": self.on_btn_ok_clicked,
      "cb_do_close": self.cb_do_close,
      "cb_set_defaults": self.cb_set_defaults,
      "cb_toggle_dependents": self.cb_toggle_dependents,
      "on_rb_toggled": self.on_rb_toggled,
      "on_txt_changed": self.on_txt_changed,
      "on_fcb_selection_changed": self.on_fcb_selection_changed,
    })


  def register_close_func(self, func):

    self.close_func = func


  def cb_do_close(self, widget, event=None):

    self._plugin.config["common"]["label_options_pos"] = \
        list(self.wnd_label_options.get_position())
    self._plugin.config["common"]["label_options_size"] = \
        list(self.wnd_label_options.get_size())

    self._plugin.config.save()

    #if self.close_func:
    #  self.close_func(self)

    self.wnd_label_options.destroy()


  def on_btn_ok_clicked(self, widget):

    self._save_options()
    self.cb_do_close(widget)


  def cb_set_defaults(self, widget):

    options = copy.deepcopy(self._defaults)
    mode = options["move_completed_mode"]
    if mode != "folder":
      path = self._parent_move_path

      if mode == "subfolder":
        path = self._path_module.join(path, self._name)

      options["move_completed_path"] = path

    self._load_options(options)


  def cb_toggle_dependents(self, widget):

    toggled = widget.get_active()
    for dependent in self._dependent_widgets[widget]:
      dependent.set_sensitive(toggled)


  def on_rb_toggled(self, widget):

    if not widget.get_active():
      return False

    lbl = self.lbl_move_completed_path
    txt = self.txt_move_completed_entry
    fcb = self.fcb_move_completed_select
    path = self._parent_move_path

    txt.set_sensitive(False)
    fcb.set_sensitive(False)

    name = widget.get_name()
    if name.endswith("parent"):
      self._set_path_label(path)
    elif name.endswith("subfolder"):
      path = self._path_module.join(path, self._name)
      self._set_path_label(path)
    elif name.endswith("folder"):
      if client.is_localhost():
        fcb.set_sensitive(True)
        self.on_fcb_selection_changed(fcb)
      else:
        txt.set_sensitive(True)
        self.on_txt_changed(txt)


  def on_fcb_selection_changed(self, widget):

    path = widget.get_filename() or ""
    self._set_path_label(path)


  def on_txt_changed(self, widget):

    self._set_path_label(widget.get_text())


  def _set_path_label(self, path):

    self.lbl_move_completed_path.set_text(path)
    self.lbl_move_completed_path.set_tooltip_text(path)


  def _load_options(self, opts):

    log.debug("Loading label options")

    options = copy.deepcopy(labelplus.common.config.LABEL_DEFAULTS)
    options.update(opts)

    if not options["move_completed_path"]:
      options["move_completed_path"] = \
          self._defaults["move_completed_path"]

    for widget in self._option_widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options:
        widget_type = type(widget)
        if widget_type in OP_MAP:
          setter = getattr(widget, OP_MAP[widget_type][SETTER])
          setter(options[name])

    rb = getattr(self, "rb_move_completed_to_%s" %
        options["move_completed_mode"])
    rb.set_active(True)

    if options["shared_limit"]:
      self.rb_shared_limit.set_active(True)
    else:
      self.rb_per_torrent_limit.set_active(True)

    # Set the current move data completed path
    self._set_path_label(options["move_completed_path"])

    # Determine "folder" radio button's path
    if options["move_completed_mode"] == "folder":
      path = options["move_completed_path"]
    else:
      path = self._defaults["move_completed_path"]

    txt = self.txt_move_completed_entry
    txt.handler_block_by_func(self.on_txt_changed)
    self.txt_move_completed_entry.set_text(path)
    txt.handler_unblock_by_func(self.on_txt_changed)

    if client.is_localhost():
      if not self._path_module.exists(path):
        path = ""

      fcb = self.fcb_move_completed_select
      fcb.handler_block_by_func(self.on_fcb_selection_changed)

      fcb.unselect_all()
      fcb.set_filename(path)

      twisted.internet.reactor.callLater(0.2, fcb.handler_unblock_by_func,
        self.on_fcb_selection_changed)

    for widget in self._dependent_widgets:
      self.cb_toggle_dependents(widget)


  def _save_options(self):

    log.debug("Saving label options")

    options = copy.deepcopy(labelplus.common.config.LABEL_DEFAULTS)

    for widget in self._option_widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options:
        widget_type = type(widget)
        if widget_type in OP_MAP:
          getter = getattr(widget, OP_MAP[widget_type][GETTER])
          options[name] = getter()
          log.debug("%r: %r", name, options[name])

    for rb in self._rgrp_move_completed:
      if rb.get_active():
        prefix, sep, mode = rb.get_name().rpartition("_")
        options["move_completed_mode"] = mode
        break

    options["max_upload_slots"] = int(options["max_upload_slots"])
    options["max_connections"] = int(options["max_connections"])

    if self.chk_auto_retroactive.get_active():
      apply_to_all = not self.chk_auto_unlabeled.get_active()
    else:
      apply_to_all = None

    client.labelplus.set_label_options(self._label_id, options, apply_to_all)
