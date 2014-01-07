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


import os.path
import gtk

from twisted.internet import defer

from deluge import common
from deluge import component
from deluge.ui.client import client
import deluge.configmanager

from labelplus.common.constant import LABEL_DEFAULTS
from labelplus.common.constant import GTKUI_CONFIG

from labelplus.common.file import get_resource
from labelplus.common.debug import debug
from labelplus.common.validation import require

from util import textview_set_text
from util import textview_get_text
from widget_encapsulator import WidgetEncapsulator


OP_MAP = {
  gtk.RadioButton: ("set_active", "get_active"),
  gtk.CheckButton: ("set_active", "get_active"),
  gtk.SpinButton: ("set_value", "get_value"),
  gtk.Label: ("set_text", "get_text"),
}


class LabelOptionsDialog(object):


  def __init__(self, label_id, label_name, page=0):

    self.config = deluge.configmanager.ConfigManager(GTKUI_CONFIG)

    self.label_id = label_id
    self.label_name = label_name
    self.daemon_is_local = client.is_localhost()

    self.close_func = None

    self.we = WidgetEncapsulator(get_resource("wnd_label_options.glade"))
    self.we.wnd_label_options.set_transient_for(
        component.get("MainWindow").window)
    self.we.wnd_label_options.set_destroy_with_parent(True)

    icon = self.we.wnd_label_options.render_icon(gtk.STOCK_PREFERENCES,
        gtk.ICON_SIZE_SMALL_TOOLBAR)
    self.we.wnd_label_options.set_icon(icon)

    pos = self.config["label_options_pos"]
    if pos:
      self.we.wnd_label_options.move(*pos)

    size = self.config["label_options_size"]
    if size:
      self.we.wnd_label_options.resize(*size)

    self.we.lbl_header.set_markup("<b>%s</b>" % self.we.lbl_header.get_text())
    self.we.lbl_selected_label.set_text(label_name)
    self.we.lbl_selected_label.set_tooltip_text(label_name)

    self.we.nb_tabs.set_current_page(page)

    self.option_widgets = (
      self.we.chk_download_settings,
      self.we.chk_move_data_completed,
      self.we.lbl_move_data_completed_path,
      self.we.chk_prioritize_first_last,

      self.we.chk_bandwidth_settings,
      self.we.rb_shared_limit_on,
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

    self.dependency_widgets = {
      self.we.chk_download_settings:
        (self.we.blk_download_settings_group,),
      self.we.chk_bandwidth_settings:
        (self.we.blk_bandwidth_settings_group,),
      self.we.chk_queue_settings:
        (self.we.blk_queue_settings_group,),
      self.we.chk_auto_settings:
        (self.we.blk_auto_settings_group,),

      self.we.chk_move_data_completed:
        (self.we.blk_move_data_completed_group,),

      self.we.rb_move_data_completed_to_folder:
        (self.we.fcb_move_data_completed_select,
          self.we.txt_move_data_completed_entry),

      self.we.chk_stop_at_ratio:
        (self.we.spn_stop_ratio, self.we.chk_remove_at_ratio),

      self.we.chk_auto_retroactive: (self.we.chk_auto_unlabeled,),
    }

    self.rgrp_move_data_completed = (
      self.we.rb_move_data_completed_to_parent,
      self.we.rb_move_data_completed_to_subfolder,
      self.we.rb_move_data_completed_to_folder,
    )

    defers = []
    defers.append(client.labelplus.get_daemon_vars())
    defers.append(client.labelplus.get_parent_path(self.label_id))
    defers.append(client.labelplus.get_options(self.label_id))
    defers.append(client.labelplus.get_preferences())

    deferred = defer.DeferredList(defers)
    deferred.addCallback(self.cb_get_options_ok)


  @debug()
  def cb_get_options_ok(self, result):

    for item in result:
      require(item[0], "Could not load dialog options")

    try:
      self.daemon_path_module = __import__(result[0][1]["os_path_module"])
    except ImportError as e:
      self.daemon_path_module = os.path

    self.parent_move_data_path = result[1][1]
    options = result[2][1]
    self.defaults = result[3][1]["defaults"]

    self._load_options(options)
    self._connect_signals()

    if self.daemon_is_local:
      self.we.txt_move_data_completed_entry.hide()
      self.we.fcb_move_data_completed_select.show()
    else:
      self.we.fcb_move_data_completed_select.hide()
      self.we.txt_move_data_completed_entry.show()

    self.we.wnd_label_options.show()


  def register_close_func(self, func):

    self.close_func = func


  @debug()
  def cb_do_close(self, widget, event=None):

    self.config["label_options_pos"] = \
        list(self.we.wnd_label_options.get_position())
    self.config["label_options_size"] = \
        list(self.we.wnd_label_options.get_size())
    self.config.save()

    if self.close_func:
      self.close_func(self)

    self.we.wnd_label_options.destroy()


  @debug()
  def on_btn_ok_clicked(self, widget):

    self._save_options()
    self.cb_do_close(widget)


  def cb_set_defaults(self, widget):

    options = dict(self.defaults)
    mode = options["move_data_completed_mode"]
    if mode != "folder":
      path = self.parent_move_data_path

      if mode == "subfolder":
        path = self.daemon_path_module.join(path, self.label_name)

      options["move_data_completed_path"] = path

    self._load_options(options)


  def cb_toggle_dependents(self, widget):

    toggled = widget.get_active()
    for dependent in self.dependency_widgets[widget]:
      dependent.set_sensitive(toggled)


  def on_rb_toggled(self, widget):

    if not widget.get_active():
      return False

    lbl = self.we.lbl_move_data_completed_path
    txt = self.we.txt_move_data_completed_entry
    fcb = self.we.fcb_move_data_completed_select
    path = self.parent_move_data_path

    txt.set_sensitive(False)
    fcb.set_sensitive(False)

    name = widget.get_name()
    if name.endswith("parent"):
      txt.set_text(path)
    elif name.endswith("subfolder"):
      path = self.daemon_path_module.join(path, self.label_name)
      txt.set_text(path)
    elif name.endswith("folder"):
      if self.daemon_is_local:
        fcb.set_sensitive(True)
        self.on_folder_changed(fcb)
      else:
        txt.set_sensitive(True)
        self.on_txt_changed(txt)


  def on_folder_changed(self, widget):

    folder = widget.get_filename()
    self.we.txt_move_data_completed_entry.set_text(folder)


  def on_txt_changed(self, widget):

    folder = widget.get_text()
    self.we.lbl_move_data_completed_path.set_text(folder)
    self.we.lbl_move_data_completed_path.set_tooltip_text(folder)


  def _connect_signals(self):

    self.we.model.signal_autoconnect({
      "on_btn_ok_clicked": self.on_btn_ok_clicked,
      "cb_do_close": self.cb_do_close,
      "cb_set_defaults": self.cb_set_defaults,
      "cb_toggle_dependents": self.cb_toggle_dependents,
      "on_rb_toggled": self.on_rb_toggled,
      "on_folder_changed": self.on_folder_changed,
      "on_txt_changed": self.on_txt_changed,
    })


  @debug()
  def _load_options(self, opts):

    options = dict(LABEL_DEFAULTS)
    options.update(opts)

    if not options["move_data_completed_path"]:
      options["move_data_completed_path"] = \
          self.defaults["move_data_completed_path"]

    for widget in self.option_widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options:
        widget_type = type(widget)
        if widget_type in OP_MAP:
          setter = getattr(widget, OP_MAP[widget_type][0])
          setter(options[name])

    rb = getattr(self.we, "rb_move_data_completed_to_%s" %
        options["move_data_completed_mode"])
    rb.set_active(True)

    if options["shared_limit_on"]:
      self.we.rb_shared_limit_on.set_active(True)
    else:
      self.we.rb_shared_limit_off.set_active(True)

    self.we.lbl_move_data_completed_path.set_tooltip_text(
        options["move_data_completed_path"])

    self.we.txt_move_data_completed_entry.set_text(
        options["move_data_completed_path"])

    if self.daemon_is_local:
      path = options["move_data_completed_path"]
      if os.path.exists(path):
        self.we.fcb_move_data_completed_select.set_current_folder(path)

    textview_set_text(self.we.tv_auto_queries,
        "\n".join(options["auto_queries"]))

    for widget in self.dependency_widgets:
      self.cb_toggle_dependents(widget)


  @debug()
  def _save_options(self):

    options = dict(LABEL_DEFAULTS)

    for widget in self.option_widgets:
      prefix, sep, name = widget.get_name().partition("_")
      if sep and name in options:
        widget_type = type(widget)
        if widget_type in OP_MAP:
          getter = getattr(widget, OP_MAP[widget_type][1])
          options[name] = getter()

    for rb in self.rgrp_move_data_completed:
      if rb.get_active():
        prefix, sep, mode = rb.get_name().rpartition("_")
        options["move_data_completed_mode"] = mode

        break

    lines = textview_get_text(self.we.tv_auto_queries).split("\n")
    options["auto_queries"] = [x.strip() for x in lines if x.strip()]

    options["max_upload_slots"] = int(options["max_upload_slots"])
    options["max_connections"] = int(options["max_connections"])

    options["tmp_auto_retroactive"] = \
        self.we.chk_auto_retroactive.get_active()
    options["tmp_auto_unlabeled"] = \
        self.we.chk_auto_unlabeled.get_active()

    client.labelplus.set_options(self.label_id, options)
