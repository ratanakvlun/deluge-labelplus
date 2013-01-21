#
# debug.py
#
# Copyright (C) 2013 Ratanak Lun <ratanakvlun@gmail.com>
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


import inspect
import os.path

from deluge.log import LOG as log

from constant import PLUGIN_NAME
from constant import MODULE_NAME


BASE = "/%s/" % MODULE_NAME
DEBUG_PATH = "common/debug.py"


def debug(show_args=False, show_result=False):


  def inner(func):


    def wrap(*args, **kwargs):

      if show_args:
        log.debug("[%s] %s%s%s%s...", PLUGIN_NAME,
            scope, func.func_name,
            args[1:] if is_instance else args,
            kwargs if kwargs else "")
      else:
        log.debug("[%s] %s%s()...", PLUGIN_NAME,
            scope, func.func_name)

      result = None
      try:
        result = func(*args, **kwargs)
        if show_result:
          log.debug("[%s] %s%s() result: %s", PLUGIN_NAME,
              scope, func.func_name, result)
        else:
          log.debug("[%s] %s%s() completed", PLUGIN_NAME,
              scope, func.func_name)
      except Exception:
        log.debug("[%s] %s%s() failed", PLUGIN_NAME,
              scope, func.func_name)
        raise

      return result


    varnames = func.func_code.co_varnames
    is_instance = len(varnames) > 0 and varnames[0] == "self"

    return wrap


  scope = ""
  frames = inspect.stack()
  for f in frames:
    prefix, sep, filepath = f[1].rpartition(BASE)
    if not sep or filepath == DEBUG_PATH: continue

    scope = "%s:%s " % (filepath, f[2])
    break

  del frames

  return inner
