#
# reference_tracker.py
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


import gc
import logging
import weakref


class ReferenceTracker(object):

  def __init__(self, logger_name=None):

    self._refs = {}

    if not logger_name:
      logger_name = __name__

    self.logger = logging.getLogger(logger_name)


  def register(self, obj, name=""):

    def on_reference_lost(ref):

      self.logger.debug("<%s> is dead", self._refs[ref])
      del self._refs[ref]


    ref = weakref.ref(obj, on_reference_lost)
    ref_str = " ".join(str(ref).split(" ")[4:])[:-1]

    if name:
      ref_str += " (%r)" % name

    self._refs[ref] = ref_str
    self.logger.debug("<%s> is registered", ref_str)

    return ref


  def report(self, collect=True):

    if gc.isenabled() and collect:
      count = len(self._refs)
      self.logger.info("Running garbage collector...")
      gc.collect()
      self.logger.info("References collected: %s", count-len(self._refs))

    if len(self._refs) > 0:
      self.logger.info("Remaining reference count: %s", len(self._refs))
      for ref in self._refs:
        self.logger.debug("<%s> is alive", self._refs[ref])
    else:
      self.logger.info("No remaining references to report")


  def clear(self):

    self._refs.clear()
