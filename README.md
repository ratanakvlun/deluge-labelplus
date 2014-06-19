LabelPlus
==========

LabelPlus is a plugin for [Deluge](http://deluge-torrent.org) that
can be used to organize torrents by assigning labels to them. It was
based on Label 0.2 by Martijn Voncken, but adds much more functionality.

This is mainly a GtkUI plugin. It adds a status column, a torrent
submenu, a sidebar tree, and a status bar area. WebUI support is minimal
with only a status column and label assignment context menu.

Features
--------
- Sublabels
- Less restrictive label names
- Ability to rename labels
- Relative move completed paths
- Auto-labeling based on torrent name or tracker
- Limit torrent speed by label

Compatibility
-------------
- Requires at least Deluge 1.3.3
- Requires at least GTK+ 2.16
- There may be issues with plugins that:
  - Add columns: There is a Deluge bug that does not properly update
    indexes when a column is removed (e.g. by a disabled plugin)
  - Add tabs to the sidebar: LabelPlus adds a tab and connects various
    handlers that make interaction between sidebar tabs more fluid
  - Add drag and drop: LabelPlus overrides any existing drag and drop
    settings
  - Modify add torrent dialog: LabelPlus adds its own field at the end
    of the add torrent dialog options
  - Use button events in torrent view: LabelPlus uses button events to
    implement double-click features and creates context menu on empty views
- If any move preference is set, there may be issues with plugins that:
  - Use `TorrentAddedEvent`: LabelPlus uses this event to automatically set
    labels on added torrents and may move the data as a result
  - Use `torrent_finished_alert`: LabelPlus uses this alert to move a
    torrent if it has been rechecked
