#
# dnd.py
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

import gobject
import gtk


log = logging.getLogger(__name__)


class DragTarget(object):

  ACTIONS = (
    gtk.gdk.ACTION_COPY,
    gtk.gdk.ACTION_MOVE,
    gtk.gdk.ACTION_LINK,
    gtk.gdk.ACTION_ASK,
  )

  POSITIONS = (
    gtk.TREE_VIEW_DROP_BEFORE,
    gtk.TREE_VIEW_DROP_AFTER,
    gtk.TREE_VIEW_DROP_INTO_OR_BEFORE,
    gtk.TREE_VIEW_DROP_INTO_OR_AFTER,
  )


  def __init__(
    self,
    name,
    scope=0,
    info=0,
    action=gtk.gdk.ACTION_COPY,
    pos=POSITIONS,
    data_func=None,
    aux_func=None,
  ):

    self.name = name
    self.scope = scope
    self.info = info
    self.action = action
    self.pos = pos
    self.data_func = data_func
    self.aux_func = aux_func

    try:
      iter(self.pos)
    except TypeError:
      self.pos = (self.pos,)


  def __str__(self):

    return str((
      self.name,
      self.scope,
      self.info,
      self.action,
      self.pos,
      self.data_func,
      self.aux_func,
    ))


  @property
  def gtk_target(self):

    return (self.name, self.scope, self.info)


  def validate(self):

    if not isinstance(self.name, basestring):
      raise TypeError("'name' is not a string")

    if not self.name:
      raise ValueError("'name' is an empty string")

    if not isinstance(self.scope, int):
      raise TypeError("'scope' is not an integer")

    if not isinstance(self.info, int):
      raise TypeError("'info' is not an integer")

    if self.action not in self.ACTIONS:
      raise ValueError("'action' is not a valid action")

    if any(pos for pos in self.pos if pos not in self.POSITIONS):
      raise ValueError("invalid position in 'pos'")

    if not self.pos:
      raise ValueError("'pos' is empty")

    if not callable(self.data_func):
      raise TypeError("'data_func' is not callable")

    if self.aux_func and not callable(self.aux_func):
      raise TypeError("'aux_func' is not callable")


  def copy(self):

    return DragTarget(
      self.name,
      self.scope,
      self.info,
      self.action,
      self.pos,
      self.data_func,
      self.aux_func,
    )


class TreeViewDragSourceProxy(object):

  DRAG_BUTTON_MASK = gtk.gdk.BUTTON1_MASK | gtk.gdk.BUTTON3_MASK

  ACTIONS_MASK = (
    gtk.gdk.ACTION_COPY |
    gtk.gdk.ACTION_MOVE |
    gtk.gdk.ACTION_LINK
  )


  def __init__(self, treeview, icon_func=None, start_func=None, end_func=None):

    self.treeview = treeview
    self.icon_func = icon_func
    self.start_func = start_func
    self.end_func = end_func

    self._targets = {}

    self._drag_event = None
    self._drag_path_info = None

    self._old_rubber_banding = treeview.get_rubber_banding()
    treeview.set_rubber_banding(True)

    self._old_targets = treeview.drag_source_get_target_list() or ()
    treeview.enable_model_drag_source(
        self.DRAG_BUTTON_MASK, (), self.ACTIONS_MASK)

    self._handlers = [
      treeview.connect("button-press-event", self._do_drag_button_press),
      treeview.connect("button-release-event", self._do_drag_button_release),
      treeview.connect("motion-notify-event", self._do_drag_motion_check),

      treeview.connect("drag-begin", self._do_drag_begin),
      treeview.connect("drag-data-get", self._do_drag_data_get),
      treeview.connect("drag-data-delete", self._do_drag_data_delete),
      treeview.connect("drag-end", self._do_drag_end),
    ]

    log.debug("%s Created", self)


  def unload(self):

    for handler in self._handlers:

      if self.treeview.handler_is_connected(handler):
        self.treeview.disconnect(handler)

    self.treeview.set_rubber_banding(self._old_rubber_banding)

    self.treeview.drag_source_set_target_list(self._old_targets)
    self.treeview.unset_rows_drag_source()

    log.debug("%s Unloaded", self)


  def __str__(self):

    return "<%s %s>" % (self.__class__.__name__, hex(id(self)))


  def add_target(self, target):

    target.validate()

    self.remove_target(target.name)

    targets = self.treeview.drag_source_get_target_list() or []
    targets.append(target.gtk_target)
    self.treeview.drag_source_set_target_list(targets)

    self._targets[target.name] = target.copy()

    log.debug("%s Added target: %r", self, target.name)


  def remove_target(self, name):

    target = self._targets.get(name, None)
    if target:

      targets = self.treeview.drag_source_get_target_list() or []
      if target.gtk_target in targets:

        targets.remove(target.gtk_target)
        self.treeview.drag_source_set_target_list(targets)

      del self._targets[target.name]

      log.debug("%s Removed target: %r", self, name)


  def _do_drag_button_press(self, widget, event):

    pos = widget.convert_widget_to_tree_coords(*widget.get_pointer())
    if pos[1] < 0:
      return False

    log.debug("%s Do button-press at b(%d, %d), Button: %s",
        self, event.x, event.y, event.button)

    handled = False

    if self._drag_event:

      log.debug("%s Drag in progress; ignoring press event", self)

      handled = True

    else:

      selected_rows = widget.get_selection().get_selected_rows()[1]
      log.debug("%s Selected rows: %r", self, selected_rows)

      path_info = widget.get_path_at_pos(int(event.x), int(event.y))
      if not path_info:

        log.debug("%s No path at press position", self)

        widget.get_selection().unselect_all()
        widget.queue_draw()

      elif path_info[0] in selected_rows:

        log.debug("%s Starting drag", self)

        # Trap press event
        self._drag_event = event.copy()
        self._drag_path_info = path_info
        handled = True

    log.debug("%s Do button-press ended", self)

    return handled


  def _do_drag_button_release(self, widget, event):

    log.debug("%s Do button-release at b(%d, %d), Button: %s",
        self, event.x, event.y, event.button)
    log.debug("%s System generated: %s", self, bool(event.send_event))

    if (self._drag_event and
        self._drag_event.button == event.button and
        not event.send_event):

      log.debug("%s Drag aborted by user", self)

      # Do what press event would have done if not trapped
      widget.do_button_press_event(widget, self._drag_event)

      self._drag_event = None
      self._drag_path_info = None

    log.debug("%s Do button-release ended", self)


  def _do_drag_motion_check(self, widget, event):

    if not self.DRAG_BUTTON_MASK & event.state:
      return False

    if self._drag_event:

      x = int(event.x)
      y = int(event.y)

      log.debug("%s Do motion check at b(%d, %d)", self, x, y)

      if widget.drag_check_threshold(
          int(self._drag_event.x), int(self._drag_event.y), x, y):

        log.debug("%s Drag threshold reached", self)

        targets = widget.drag_source_get_target_list()
        if targets:
          context = widget.drag_begin(targets, self.ACTIONS_MASK,
              self._drag_event.button, event)

          log.debug("%s Drag icon function: %s", self, self.icon_func)

          if self.icon_func:

            try:
              context.set_icon_pixbuf(
                *self.icon_func(
                  widget,
                  int(self._drag_event.x),
                  int(self._drag_event.y),
                )
              )

            except:
              log.exception("%s Drag icon function failed", self)

      log.debug("%s Do motion check ended", self)


  def _do_drag_begin(self, widget, context):

    log.info("%s Do drag-begin", self)

    log.debug("%s Start function: %s", self, self.start_func)

    if self.start_func:

      try:
        self.start_func(widget, context)

      except:
        log.exception("%s Start function failed", self)

    log.debug("%s Do drag-begin ended", self)


  def _do_drag_data_get(self, widget, context, selection, info, timestamp):

    log.debug("%s Do drag-data-get", self)

    target = self._targets.get(selection.target, None)
    if target:

      log.debug("%s Data handler: %s", self, target.data_func)

      path = self._drag_path_info[0]
      col = self._drag_path_info[1]

      try:

        target.data_func(widget, path, col, selection, target.gtk_target)
        context.set_data("selection", selection.copy())

      except:
        log.exception("%s Do drag-data-get failed", self)

    log.debug("%s Do drag-data-get ended", self)

    return True


  def _do_drag_data_delete(self, widget, context):

    log.debug("%s Do drag-data-delete", self)

    selection = context.get_data("selection")

    if context.action == gtk.gdk.ACTION_MOVE:

      target = self._targets.get(selection.target, None)
      if target and target.action == context.action:

        log.debug("%s Data handler: %s", self, target.aux_func)

        if target.aux_func:
          path = self._drag_path_info[0]
          col = self._drag_path_info[1]

          try:
            target.aux_func(widget, path, col, selection, target.gtk_target)

          except:
            log.exception("%s Do drag-data-delete failed", self)

    log.debug("%s Do drag-data-delete ended", self)

    return True


  def _do_drag_end(self, widget, context):

    log.info("%s Do drag-end", self)

    self._drag_event = None
    self._drag_path_info = None
    context.set_data("selection", None)

    if context.action == gtk.gdk.ACTION_MOVE:
      widget.get_selection().unselect_all()
      widget.queue_draw()

    log.debug("%s End function: %s", self, self.end_func)

    if self.end_func:

      try:
        self.end_func(widget, context)

      except:
        log.exception("%s End function failed", self)

    log.debug("%s Do drag-end ended", self)

    return True


class TreeViewDragDestProxy(object):

  AUTOSCROLL_TIMEOUT = 150
  AUTOSCROLL_MARGIN = 15

  AUTOEXPAND_TIMEOUT = 500


  def __init__(self, treeview):

    self.treeview = treeview
    self._targets = {}

    self._scroll_timeout = None
    self._expand_timeout = None
    self._expand_row = None

    self._old_targets = treeview.drag_dest_get_target_list() or ()
    treeview.enable_model_drag_dest((), 0)

    self._handlers = [
      treeview.connect("drag-motion", self._do_drag_motion),
      treeview.connect("drag-leave", self._do_drag_leave),
      treeview.connect("drag-data-received", self._do_drag_data_received),
      treeview.connect("drag-drop", self._do_drag_drop),
      treeview.connect("drag-end", self._do_drag_end),
    ]

    log.debug("%s Created", self)


  def unload(self):

    for handler in self._handlers:

      if self.treeview.handler_is_connected(handler):
        self.treeview.disconnect(handler)

    self._disable_auto()

    self.treeview.drag_dest_set_target_list(self._old_targets)
    self.treeview.unset_rows_drag_dest()

    log.debug("%s Unloaded", self)


  def __str__(self):

    return "<%s %s>" % (self.__class__.__name__, hex(id(self)))


  def add_target(self, target):

    target.validate()
    self.remove_target(target.name)

    targets = self.treeview.drag_dest_get_target_list() or []
    targets.append(target.gtk_target)
    self.treeview.drag_dest_set_target_list(targets)

    self._targets[target.name] = target.copy()

    log.debug("%s Added target: %r", self, target.name)


  def remove_target(self, name):

    target = self._targets.get(name, None)
    if target:

      targets = self.treeview.drag_dest_get_target_list() or []
      if target.gtk_target in targets:

        targets.remove(target.gtk_target)
        self.treeview.drag_dest_set_target_list(targets)

      del self._targets[target.name]

      log.debug("%s Removed target: %r", self, name)


  def _enable_autoscroll(self):

    if not self._scroll_timeout:
      self._scroll_timeout = gobject.timeout_add(
          self.AUTOSCROLL_TIMEOUT, self._do_autoscroll)


  def _disable_autoscroll(self):

    if self._scroll_timeout:

      gobject.source_remove(self._scroll_timeout)
      self._scroll_timeout = None


  def _do_autoscroll(self):

    pos = self.treeview.get_pointer()
    pos = self.treeview.convert_widget_to_tree_coords(*pos)
    visible = self.treeview.get_visible_rect()

    value = self.treeview.get_hadjustment().value
    upper = self.treeview.get_hadjustment().upper
    inc = self.treeview.get_hadjustment().step_increment

    left_margin = visible.x + self.AUTOSCROLL_MARGIN
    right_margin = visible.x + visible.width - self.AUTOSCROLL_MARGIN

    if pos[0] < left_margin:

      inc = inc + left_margin - pos[0]
      self.treeview.get_hadjustment().clamp_page(value-inc, upper)

    elif pos[0] > right_margin:

      inc = inc + pos[0] - right_margin
      self.treeview.get_hadjustment().clamp_page(value+inc, upper)

    value = self.treeview.get_vadjustment().value
    upper = self.treeview.get_vadjustment().upper
    inc = self.treeview.get_vadjustment().step_increment

    top_margin = visible.y + self.AUTOSCROLL_MARGIN
    bottom_margin = visible.y + visible.height - self.AUTOSCROLL_MARGIN

    if pos[1] < top_margin:

      inc = inc + top_margin - pos[1]
      self.treeview.get_vadjustment().clamp_page(value-inc, upper)

    elif pos[1] > bottom_margin:

      inc = inc + pos[1] - bottom_margin
      self.treeview.get_vadjustment().clamp_page(value+inc, upper)

    return True


  def _enable_autoexpand(self):

    if not self._expand_timeout:
      self._expand_timeout = gobject.timeout_add(
          self.AUTOEXPAND_TIMEOUT, self._do_autoexpand)


  def _disable_autoexpand(self):

    if self._expand_timeout:

      gobject.source_remove(self._expand_timeout)
      self._expand_timeout = None
      self._expand_row = None


  def _do_autoexpand(self):

    pos = self.treeview.get_pointer()
    pos = self.treeview.convert_widget_to_bin_window_coords(*pos)
    path_info = self.treeview.get_path_at_pos(*pos)

    if path_info:

      if self._expand_row == path_info[0]:

        if not self.treeview.row_expanded(self._expand_row):
          self.treeview.expand_row(self._expand_row, False)

      else:
        self._expand_row = path_info[0]

    return True


  def _enable_auto(self):

    self._enable_autoscroll()
    self._enable_autoexpand()


  def _disable_auto(self):

    self._disable_autoscroll()
    self._disable_autoexpand()


  def _find_target(self, widget, context):

    src = context.get_source_widget()
    same = widget is src

    for name in context.targets:

      target = self._targets.get(name, None)
      if target and (
        target.action & context.actions or
        target.action == gtk.gdk.ACTION_ASK
      ):

        if (target.scope == 0 or
            target.scope & gtk.TARGET_SAME_WIDGET and same or
            target.scope & gtk.TARGET_SAME_APP and src or
            target.scope & gtk.TARGET_OTHER_WIDGET and src and not same or
            target.scope & gtk.TARGET_OTHER_APP and not src):

          if src and not same:

            targets = src.drag_source_get_target_list() or ()
            for t in targets:

              if t[0] == target.name:

                if t[1] & gtk.TARGET_SAME_WIDGET:
                  target = None

                break

          return target


  def _do_drag_motion(self, widget, context, x, y, timestamp):

    log.debug("%s Do drag-motion at w(%d, %d)", self, x, y)

    self._enable_auto()

    valid = False

    row_info = widget.get_dest_row_at_pos(x, y)
    if row_info:

      target = self._find_target(widget, context)
      if target:

        path = row_info[0]
        pos = row_info[1] if row_info[1] in target.pos else target.pos[0]

        coords = widget.convert_widget_to_bin_window_coords(x, y)
        col = widget.get_path_at_pos(*coords)[1]

        log.debug("%s Target info: %s", self, target.gtk_target)
        log.debug("%s Target action: %s", self, target.action)
        log.debug("%s Dest path: %s, %s", self, path, pos)
        log.debug("%s Dest column: %r %s", self, col.get_title(), col)

        if target.aux_func:

          log.debug("%s Sending peek request", self)

          context.set_data("request_info", (path, col, pos))
          context.set_data("request_type", "peek")

          widget.drag_get_data(context, target.name, timestamp)

        else:

          context.drag_status(target.action, timestamp)
          widget.set_drag_dest_row(path, pos)

        valid = True

    if not valid:

      log.debug("%s Drop zone: Invalid", self)

      context.drag_status(0, timestamp)

    log.debug("%s Do drag-motion ended", self)

    return True


  def _do_drag_leave(self, widget, context, timestamp):

    log.debug("%s Do drag-leave", self)

    self._disable_auto()

    log.debug("%s Do drag-leave ended", self)


  def _do_drag_data_received(self,
      widget, context, x, y, selection, info, timestamp):

    request_info = context.get_data("request_info")
    request_type = context.get_data("request_type")
    context.set_data("request_info", None)
    context.set_data("request_type", None)

    widget.emit_stop_by_name("drag-data-received")

    log.debug("%s Do drag-data-received", self)

    result = False

    try:

      if selection.get_length() > -1:

        target = self._targets.get(selection.target)

        if request_type == "get":

          log.debug("%s Data handler: %s", self, target.data_func)

          result = target.data_func(widget, request_info[0], request_info[1],
              request_info[2], selection, target.gtk_target,
              context, timestamp)

        elif request_type == "peek":

          log.debug("%s Data handler: %s", self, target.aux_func)

          result = target.aux_func(widget, request_info[0], request_info[1],
              request_info[2], selection, target.gtk_target)

        result = result or False

    except:
      log.exception("%s Do drag-data-received failed", self)

    finally:

      if request_type == "get":

        delete = result and context.action == gtk.gdk.ACTION_MOVE
        context.finish(result, delete, timestamp)

        log.debug("%s Success: %s, Should delete: %s", self, result, delete)

      elif request_type == "peek" and result:

        log.debug("%s Drop zone: Valid", self)

        context.drag_status(target.action, timestamp)
        widget.set_drag_dest_row(request_info[0], request_info[2])

      else:

        log.debug("%s Drop zone: Invalid", self)

        context.drag_status(0, timestamp)

      log.debug("%s Do drag-data-received ended", self)

    return True


  def _do_drag_drop(self, widget, context, x, y, timestamp):

    log.info("%s Do drag-drop at w(%d, %d)", self, x, y)

    drop_finished = False

    row_info = widget.get_dest_row_at_pos(x, y)
    if row_info:

      target = self._find_target(widget, context)
      if target:

        path = row_info[0]
        pos = row_info[1] if row_info[1] in target.pos else target.pos[0]

        coords = widget.convert_widget_to_bin_window_coords(x, y)
        col = widget.get_path_at_pos(*coords)[1]

        log.debug("%s Target info: %s", self, target.gtk_target)
        log.debug("%s Target action: %s", self, target.action)
        log.debug("%s Dest path: %s, %s", self, path, pos)
        log.debug("%s Dest column: %r %s", self, col.get_title(), col)

        log.debug("%s Sending data request", self)

        context.set_data("request_info", (path, col, pos))
        context.set_data("request_type", "get")

        widget.drag_get_data(context, target.name, timestamp)

        drop_finished = True

    if not drop_finished:

      log.debug("%s Do drag-drop failed", self)

      context.finish(False, False, timestamp)

    log.debug("%s Do drag-drop ended", self)

    return True


  def _do_drag_end(self, widget, context):

    log.info("%s Do drag-end", self)

    self._disable_auto()

    log.debug("%s Do drag-end ended", self)
