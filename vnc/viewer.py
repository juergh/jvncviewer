#!/usr/bin/env python3
#
# Copyright (C) 2018  Juerg Haefliger <juergh@gmail.com>
# Copyright (C) 2006  Anthony Liguori <anthony@codemonkey.ws>
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

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkVnc', '2.0')

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GtkVnc

from vnc import task
from vnc.statusicon import StatusIcon, STATUS_OK, STATUS_ERROR, STATUS_UNKNOWN

GLib.threads_init()


class VNCViewer():
    def __init__(self, host, password, bmc=None):
        port = "5900"
        if ":" in host:
            host, port = host.split(':')

        self.host = host
        self.port = port
        self.password = password
        self.bmc = bmc

        self.reconnect = True
        self.connected = False
        self.power = None

        # Status icons
        self.connection_status = StatusIcon()
        self.connection_status.set_status(STATUS_ERROR)
        if bmc:
            self.power_status = StatusIcon()
            self.power_status.set_status(STATUS_UNKNOWN)

        # Menubar
        menubar = self._menubar(bmc)

        # VNC display
        self.vncdisplay = GtkVnc.Display()
        self.vncbox = Gtk.VBox()
        self.vncbox.set_size_request(720, 400)
        self.vncbox.add(self.vncdisplay)

        # Status bar
        statusbar = Gtk.HBox()
        statusbar.pack_start(Gtk.Label("Connection:"), False, False, 10)
        statusbar.pack_start(self.connection_status, False, False, 10)
        statusbar.pack_start(Gtk.Label("Power:"), False, False, 10)
        statusbar.pack_start(self.power_status, False, False, 10)

        # Layout
        layout = Gtk.VBox()
        layout.pack_start(menubar, False, False, 0)
        layout.pack_start(self.vncbox, True, True, 0)
        layout.pack_end(statusbar, False, False, 0)

        # Window
        self.window = Gtk.Window(title="jvncviewer - %s" % host)
        self.window.add(layout)
        self.window.connect("destroy", self.quit)
        self.window.show_all()

    def _menubar(self, bmc):
        #
        # 'File' menu
        #
        file_quit = Gtk.MenuItem("Quit")
        file_quit.connect("activate", self.quit)

        menu_file = Gtk.Menu()
        menu_file.append(file_quit)

        menuitem_file = Gtk.MenuItem("File")
        menuitem_file.set_submenu(menu_file)

        #
        # 'Send Key' menu
        #
        sendkey_cad = Gtk.MenuItem("Control-Alt-Delete")
        sendkey_cad.connect("activate", self._send_cad)
        sendkey_f12 = Gtk.MenuItem("F12")
        sendkey_f12.connect("activate", self._send_f12)

        menu_sendkey = Gtk.Menu()
        menu_sendkey.append(sendkey_cad)
        menu_sendkey.append(sendkey_f12)

        menuitem_sendkey = Gtk.MenuItem("Send Key")
        menuitem_sendkey.set_submenu(menu_sendkey)

        #
        # 'System' menu
        #
        system_reconnect = Gtk.MenuItem("Reconnect")
        system_reconnect.connect("activate", self._system_reconnect)

        menu_system = Gtk.Menu()
        menu_system.append(system_reconnect)

        if bmc:
            system_pon = Gtk.MenuItem("Power On")
            system_pon.connect("activate", self._system_pon)
            system_poff = Gtk.MenuItem("Power Off")
            system_poff.connect("activate", self._system_poff)
            system_pcycle = Gtk.MenuItem("Power Cycle")
            system_pcycle.connect("activate", self._system_pcycle)
            system_reset = Gtk.MenuItem("Reset")
            system_reset.connect("activate", self._system_reset)

            menu_system.append(system_pon)
            menu_system.append(system_poff)
            menu_system.append(system_pcycle)
            menu_system.append(system_reset)

        menuitem_system = Gtk.MenuItem("System")
        menuitem_system.set_submenu(menu_system)

        #
        # Menubar
        #
        menubar = Gtk.MenuBar()
        menubar.append(menuitem_file)
        menubar.append(menuitem_sendkey)
        menubar.append(menuitem_system)

        return menubar

    def _update_statusbar(self):
        if self.connected:
            self.connection_status.set_status(STATUS_OK)
        else:
            self.connection_status.set_status(STATUS_ERROR)

        if self.bmc:
            if not self.power:
                self.power_status.set_status(STATUS_UNKNOWN)
            elif self.power == self.bmc.POWER_STATE_OFF:
                self.power_status.set_status(STATUS_ERROR)
            elif self.power == self.bmc.POWER_STATE_ON:
                self.power_status.set_status(STATUS_OK)
            else:
                self.power_status.set_status(STATUS_UNKNOWN)

    # -------------------------------------------------------------------------
    # VNC/GTK signal handlers

    def _auth_credential(self, _src, _credList):   # pylint: disable=no-self-use
        logging.error("Server requires authentication")
        Gtk.main_quit()

    def _auth_failure(self, _src, msg):   # pylint: disable=no-self-use
        logging.error("Authentication failure: %s", msg.strip())
        Gtk.main_quit()

    def _connected(self, _src):
        logging.debug("Connected to server")
        self.connected = True
        self._update_statusbar()
        self._system_get_power_state()

    def _disconnected(self, _src):
        logging.debug("Disconnected from server")
        self.connected = False
        self._update_statusbar()

        if self.reconnect:
            # Automatically reconnect
            GLib.timeout_add(500, self.connect)

    def _error(self, _src, msg):   # pylint: disable=no-self-use
        logging.error("Error: %s", msg)

    def _initialized(self, _src):   # pylint: disable=no-self-use
        logging.debug("Connection initialized")

    def _size_allocate(self, _src, _rect):
        logging.debug("Size allocation")
        # HACK: Shrink the window so that is resizes automatically to the
        # size that the VNC display requests.
        self.window.resize(10, 10)

    # -------------------------------------------------------------------------
    # 'Send Key' menu signal handlers

    def _send_cad(self, _src):
        logging.debug("Send Control-Alt-Delete")
        self.vncdisplay.send_keys([Gdk.KEY_Control_L, Gdk.KEY_Alt_L,
                                   Gdk.KEY_Delete])
    def _send_f12(self, _src):
        logging.debug("Send F12")
        self.vncdisplay.send_keys([Gdk.KEY_F12])

    # -------------------------------------------------------------------------
    # System background methods
    # These are long running and need to be run in separate threads

    def __system_get_power_state(self):
        logging.debug("Getting system power state")
        self.power = self.bmc.get_power_state()
        logging.debug("System power state is: %s", self.power)
        GLib.idle_add(self._update_statusbar)

        if self.power not in self.bmc.POWER_STATES:
            GLib.timeout_add(2000, self._system_get_power_state)

    def __system_set_power_state(self, state):
        logging.debug("Setting system power state to: %s", state)

        # Per the Intel AMT spec, some power commands are rejected if there's
        # an active connection, so break it first and re-establish it again
        # afterwards. It's OK to sleep here since this method runs in the
        # background and won't block the UI.
        if state in (self.bmc.POWER_STATE_OFF, self.bmc.POWER_STATE_CYCLE):
            GLib.idle_add(self.disconnect, False)
            while self.connected:
                pass

        # Set the requested power state
        errno = self.bmc.set_power_state(state)
        if errno:
            # Retry once
            self.bmc.set_power_state(state)

        if state in (self.bmc.POWER_STATE_OFF, self.bmc.POWER_STATE_CYCLE):
            # Reconnect
            GLib.idle_add(self.connect)

        # Get the current power state and update the statusbar
        GLib.timeout_add(2000, self._system_get_power_state)

    # -------------------------------------------------------------------------
    # 'System' menu signal handlers

    def _system_get_power_state(self):
        task.run(self.__system_get_power_state)

    def _system_reconnect(self, _src):
        logging.debug("Reconnecting to %s:%s", self.host, self.port)
        self.disconnect(reconnect=True)

    def _system_pon(self, _src):
        task.run(self.__system_set_power_state, self.bmc.POWER_STATE_ON)

    def _system_poff(self, _src):
        task.run(self.__system_set_power_state, self.bmc.POWER_STATE_OFF)

    def _system_pcycle(self, _src):
        task.run(self.__system_set_power_state, self.bmc.POWER_STATE_CYCLE)

    def _system_reset(self, _src):
        task.run(self.__system_set_power_state, self.bmc.POWER_STATE_RESET)

    # -------------------------------------------------------------------------
    # Public methods

    def connect(self):
        logging.debug("Connecting to %s:%s", self.host, self.port)
        self.reconnect = True

        # Remove the previous VNC display from the window layout (in case of a
        # reconnect)
        self.vncbox.remove(self.vncdisplay)

        # Create the VNC display and add it to the window layout
        self.vncdisplay = GtkVnc.Display()
        self.vncbox.add(self.vncdisplay)
        self.vncdisplay.show()

        if self.password:
            self.vncdisplay.set_credential(GtkVnc.DisplayCredential.CLIENTNAME,
                                           "jvncviewer")
            self.vncdisplay.set_credential(GtkVnc.DisplayCredential.PASSWORD,
                                           self.password)

        self.vncdisplay.realize()

        self.vncdisplay.connect("size-allocate", self._size_allocate)
        self.vncdisplay.connect("vnc-auth-credential", self._auth_credential)
        self.vncdisplay.connect("vnc-auth-failure", self._auth_failure)
        self.vncdisplay.connect("vnc-connected", self._connected)
        self.vncdisplay.connect("vnc-disconnected", self._disconnected)
        self.vncdisplay.connect("vnc-error", self._error)
        self.vncdisplay.connect("vnc-initialized", self._initialized)

        self.vncdisplay.open_host(self.host, self.port)

    def disconnect(self, reconnect=True):
        logging.debug("Disconnecting from %s:%s", self.host, self.port)
        self.reconnect = reconnect
        self.vncdisplay.close()

    def quit(self, _src=None):   # pylint: disable=no-self-use
        logging.debug("Quitting")
        Gtk.main_quit()
