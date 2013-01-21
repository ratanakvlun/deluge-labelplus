#
# __init__.py
#
# Copyright (C) 2013 Ratanak Lun <ratanakvlun@gmail.com>
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
#
# Basic plugin template created by:
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
# Copyright (C) 2007-2009 Andrew Resch <andrewresch@gmail.com>
# Copyright (C) 2009 Damien Churchill <damoxc@gmail.com>
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


from twisted.internet import reactor

from deluge import component
from deluge.plugins.pluginbase import GtkPluginBase
from deluge.ui.client import client
import deluge.configmanager

from labelplus.common.constant import DISPLAY_NAME
from labelplus.common.constant import STATUS_PATH
from labelplus.common.constant import GTKUI_CONFIG
from labelplus.common.constant import GTKUI_DEFAULTS

from label_selection_menu import LabelSelectionMenu
from label_sidebar import LabelSidebar
from preferences import Preferences


MAX_RETRIES = 10
WAIT_TIME = 1.0


class GtkUI(GtkPluginBase):


  def __init__(self, plugin_name):

    super(GtkUI, self).__init__(plugin_name)
    self.initialized = False
    self.retries = 0


  def enable(self):

    client.labelplus.is_initialized().addCallback(self.cb_check)


  def cb_check(self, result):

    if result == True:
      self._do_load()
    elif self.retries < MAX_RETRIES:
      reactor.callLater(WAIT_TIME, self.enable)
      self.retries += 1


  def _do_load(self):

    self._config = deluge.configmanager.ConfigManager(
        GTKUI_CONFIG, defaults=GTKUI_DEFAULTS)

    component.get("TorrentView").add_text_column(DISPLAY_NAME,
        status_field=[STATUS_PATH])

    self.label_selection_menu = LabelSelectionMenu()
    self.sep = component.get("MenuBar").add_torrentmenu_separator()
    component.get("MenuBar").torrentmenu.append(self.label_selection_menu)

    self.label_sidebar = LabelSidebar()

    self.preferences = Preferences()

    self.initialized = True


  def disable(self):

    if self.initialized:
      self.initialized = False

      self._config.save()
      deluge.configmanager.close(self._config)

      component.get("TorrentView").remove_column(DISPLAY_NAME)

      component.get("MenuBar").torrentmenu.remove(self.sep)
      component.get("MenuBar").torrentmenu.remove(self.label_selection_menu)
      self.label_selection_menu.destroy()
      del self.label_selection_menu

      self.label_sidebar.unload()
      del self.label_sidebar

      self.preferences.unload()


  def update(self):

    if self.initialized:
      self.label_sidebar.update_counts()
