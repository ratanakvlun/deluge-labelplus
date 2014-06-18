/*
Script: labelplus.js
    The client-side javascript code for the LabelPlus plugin.

Copyright:
    (C) Ratanak Lun 2014 <ratanakvlun@gmail.com>
    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3, or (at your option)
    any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, write to:
        The Free Software Foundation, Inc.,
        51 Franklin Street, Fifth Floor
        Boston, MA  02110-1301, USA.

    In addition, as a special exception, the copyright holders give
    permission to link the code of portions of this program with the OpenSSL
    library.
    You must obey the GNU General Public License in all respects for all of
    the code used other than OpenSSL. If you modify file(s) with this
    exception, you may extend this exception to your version of the file(s),
    but you are not obligated to do so. If you do not wish to do so, delete
    this exception statement from your version. If you delete this exception
    statement from all source files in the program, then also delete it here.
*/


Ext.namespace('Deluge.plugins.labelplus.util');


if (typeof(console) === 'undefined') {
  console = {
    log: function() {}
  };
}

if (typeof(Object.keys) === 'undefined') {
  Object.keys = function(obj) {
    var keys = [];

    for (var i in obj) {
      if (obj.hasOwnProperty(i)) {
        keys.push(i);
      }
    }

    return keys;
  };
}


Deluge.plugins.labelplus.PLUGIN_NAME = 'LabelPlus';
Deluge.plugins.labelplus.MODULE_NAME = 'labelplus';
Deluge.plugins.labelplus.DISPLAY_NAME = _('LabelPlus');

Deluge.plugins.labelplus.STATUS_NAME =
  Deluge.plugins.labelplus.MODULE_NAME + '_name';


Deluge.plugins.labelplus.util.isReserved = function(id) {
  return (id == 'All' || id == 'None' || id == '');
};

Deluge.plugins.labelplus.util.getParent = function(id) {
  return id.substring(0, id.lastIndexOf(':'));
};


Deluge.plugins.labelplus.Plugin = Ext.extend(Deluge.Plugin, {

  name: Deluge.plugins.labelplus.PLUGIN_NAME,

  onEnable: function() {
    this.registerTorrentStatus(Deluge.plugins.labelplus.STATUS_NAME,
      Deluge.plugins.labelplus.DISPLAY_NAME,
      {
        colCfg: {
          sortable: true
        }
      }
    );

    this.waitForClient(10);
  },

  onDisable: function() {
    if (this._rootMenu) {
      this._rootMenu.destroy();
      delete this._rootMenu;
    }

    this.deregisterTorrentStatus(Deluge.plugins.labelplus.STATUS_NAME);

    console.log('%s disabled', Deluge.plugins.labelplus.PLUGIN_NAME);
  },

  waitForClient: function(triesLeft) {
    if (triesLeft < 1) {
      console.log('%s RPC configuration timed out',
        Deluge.plugins.labelplus.PLUGIN_NAME);
      return;
    }

    if (deluge.login.isVisible() || !deluge.client.core ||
        !deluge.client.labelplus) {
      var self = this;
      var t = deluge.login.isVisible() ? triesLeft : triesLeft-1;
      setTimeout(function() { self.waitForClient.apply(self, [t]); }, 1000);
    } else {
      this._pollInit();
    }
  },

  _pollInit: function() {
    deluge.client.labelplus.is_initialized({
      success: this._checkInit,
      scope: this
    });
  },

  _checkInit: function(result) {
    console.log('Waiting for %s core to be initialized...',
      Deluge.plugins.labelplus.PLUGIN_NAME);

    if (result) {
      console.log('%s core is initialized',
        Deluge.plugins.labelplus.PLUGIN_NAME);

      deluge.client.labelplus.get_label_updates_dict({
        success: this._finishInit,
        scope: this
      });
    } else {
      var self = this;
      setTimeout(function() { self._pollInit.apply(self); }, 3000);
    }
  },

  _finishInit: function(result) {
    if (result) {
      this._doUpdate(result);
      this._updateLoop();

      console.log('%s enabled', Deluge.plugins.labelplus.PLUGIN_NAME);
    }
  },

  _doUpdate: function(result) {
    if (!result) {
      return;
    }

    this._lastUpdated = result.timestamp;

    if (this._rootMenu) {
      this._rootMenu.destroy();
      delete this._rootMenu;
    }

    var menu = new Ext.menu.Menu({ ignoreParentClicks: true });
    menu.add({
      text: _('Set Label'),
      menu: this._createMenuFromData(result.data)
    });

    this._rootMenu = deluge.menus.torrent.add({
      text: Deluge.plugins.labelplus.DISPLAY_NAME,
      menu: menu
    });
  },

  _updateLoop: function() {
    deluge.client.labelplus.get_label_updates_dict(this._lastUpdated, {
      success: function(result) {
        this._doUpdate(result);
        var self = this;
        setTimeout(function() { self._updateLoop.apply(self); }, 1000);
      },
      scope: this
    });
  },

  _getSortedKeys: function(data) {
    var sortedKeys = Object.keys(data).sort(function(a, b) {
      var aReserved = Deluge.plugins.labelplus.util.isReserved(a);
      var bReserved = Deluge.plugins.labelplus.util.isReserved(b);

      if (aReserved && bReserved) {
        return a < b ? -1 : a > b;
      } else if (aReserved) {
        return -1;
      } else if (bReserved) {
        return 1;
      }

      var aParent = Deluge.plugins.labelplus.util.getParent(a);
      var bParent = Deluge.plugins.labelplus.util.getParent(b);

      if (aParent == bParent) {
        return data[a].name < data[b].name ? -1 : data[a].name > data[b].name;
      } else {
        return aParent < bParent ? -1 : aParent > bParent;
      }
    });

    return sortedKeys;
  },

  _buildLabelMap: function(sortedKeys, data) {
    var map = {};

    for (var i = 0; i < sortedKeys.length; i++) {
      var id = sortedKeys[i];
      var parent = Deluge.plugins.labelplus.util.getParent(id);

      if (parent == '') {
        map[id] = [];
      } else if (parent in map) {
        map[parent].push(id);
        map[id] = [];
      }
    }

    return map;
  },

  _createMenuFromData: function(data) {
    var keys = this._getSortedKeys(data);
    var labelMap = this._buildLabelMap(keys, data);

    var menu = new Ext.menu.Menu({ ignoreParentClicks: true });
    var submenus = {};

    menu.addMenuItem({
      text: _('None'),
      label: 'None',
      handler: this._menuItemClicked,
      scope: this
    });
    menu.add({ xtype: 'menuseparator' });

    for (var i = 0; i < keys.length; i++) {
      var id = keys[i];

      if (Deluge.plugins.labelplus.util.isReserved(id)) {
        continue;
      }

      if (id in labelMap) {
        var name = data[id].name;
        var submenu = false;

        if (labelMap[id].length > 0) {
          submenu = new Ext.menu.Menu({ ignoreParentClicks: true });
          submenu.addMenuItem({
            text: name,
            label: id,
            handler: this._menuItemClicked,
            scope: this
          });
          submenu.add({ xtype: 'menuseparator' });

          submenus[id] = submenu;
        }

        var parent = Deluge.plugins.labelplus.util.getParent(id);
        if (parent in submenus) {
          if (submenu) {
            submenus[parent].add({
              text: name,
              menu: submenu
            });
          } else {
            submenus[parent].addMenuItem({
              text: name,
              label: id,
              handler: this._menuItemClicked,
              scope: this
            });
          }
        } else {
          if (submenu) {
            menu.add({
              text: name,
              menu: submenu
            });
          } else {
            menu.addMenuItem({
              text: name,
              label: id,
              handler: this._menuItemClicked,
              scope: this
            });
          }
        }
      }
    }

    return menu;
  },

  _menuItemClicked: function(item, e) {
    var ids = deluge.torrents.getSelectedIds();

    deluge.client.labelplus.set_torrent_labels(ids, item.label, {
      success: function() {},
      scope: this
    });
  }
});

Deluge.registerPlugin(Deluge.plugins.labelplus.PLUGIN_NAME,
  Deluge.plugins.labelplus.Plugin);
