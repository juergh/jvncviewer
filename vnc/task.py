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

import logging
import threading


class _Task(threading.Thread):
    def __init__(self, func, *args):
        super(_Task, self).__init__()
        self.func = func
        self.args = args
        self.retval = None

    def run(self):
        logging.debug("Running background task: %s", self.func.__name__)
        self.retval = self.func(*self.args)


def run(func, *args):
    task = _Task(func, *args)
    task.start()
