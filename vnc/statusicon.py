#!/usr/bin/env python3
#
# Copyright (C) 2018  Juerg Haefliger <juergh@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.0 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA

import os

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk

STATUS_OK = "green"
STATUS_WARNING = "yellow"
STATUS_ERROR = "red"
STATUS_UNKNOWN = "blue"

_status_list = (STATUS_OK, STATUS_WARNING, STATUS_ERROR, STATUS_UNKNOWN)


class StatusIcon(Gtk.Image):
    def __init__(self, size=16):
        super(StatusIcon, self).__init__()

        self._pixbuf = {}
        for status in _status_list:
            tmp = Gtk.Image()
            tmp.set_from_file(os.path.join(os.path.dirname(__file__),
                                           os.pardir, "icons",
                                           status + ".png"))
            self._pixbuf[status] = tmp.get_pixbuf().scale_simple(size, size, 2)

    def set_status(self, status):
        if status in _status_list:
            self.set_from_pixbuf(self._pixbuf[status])
