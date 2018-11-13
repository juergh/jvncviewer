#!/usr/bin/env python3
#
# Intel AMT wsman driver
# Inspired by OpenStack's Ironic AMT driver from ironic-staging-drivers.
#
# Copyright (C) 2018  Juerg Haefliger <juergh@gmail.com>
# Copyright (C) 2018  OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import time

import pywsman

from amt import utils, wsman


# AMT power states
POWER_STATE_ON = 2
POWER_STATE_CYCLE = 5
POWER_STATE_OFF = 8
POWER_STATE_RESET = 10
POWER_STATE_NMI = 11
POWER_STATE_INVALID = 99

POWER_STATES = (POWER_STATE_ON, POWER_STATE_CYCLE, POWER_STATE_OFF,
                POWER_STATE_RESET, POWER_STATE_NMI)

_power_state_map = {
    POWER_STATE_ON: "on",
    POWER_STATE_CYCLE: "cycle",
    POWER_STATE_OFF: "off",
    POWER_STATE_RESET: "reset",
    POWER_STATE_NMI: "nmi",
}

_CIM_Schema = "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/"
_CIM_AssociatedPowerManagementService = _CIM_Schema + "CIM_AssociatedPowerManagementService"
_CIM_PowerManagementService = _CIM_Schema + "CIM_PowerManagementService"
_CIM_ComputerSystem = _CIM_Schema + "CIM_ComputerSystem"


def power_state_from_string(state):
    """
    Translate a power state string
    """
    for key, val in _power_state_map.items():
        if state == val:
            return key
    return POWER_STATE_INVALID


def power_string_from_state(state):
    """
    Translate a power state
    """
    return _power_state_map.get(state, "invalid")


def is_int(val):
    """
    Check if a value is an int
    """
    try:
        int(val)
    except ValueError:
        return False
    return True


def _request_power_state_change_input(state):
    """
    Generate a wsman xmldoc for requesting a power state change
    """
    method_input = "RequestPowerStateChange_INPUT"
    address = "http://schemas.xmlsoap.org/ws/2004/08/addressing"
    anonymous = address + "/role/anonymous"
    wsman = "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
    namespace = _CIM_PowerManagementService

    doc = pywsman.XmlDoc(method_input)
    root = doc.root()
    root.set_ns(namespace)
    root.add(namespace, "PowerState", str(state))

    child = root.add(namespace, "ManagedElement", None)
    child.add(address, "Address", anonymous)

    grand_child = child.add(address, "ReferenceParameters", None)
    grand_child.add(wsman, "ResourceURI", _CIM_ComputerSystem)

    g_grand_child = grand_child.add(wsman, "SelectorSet", None)

    g_g_grand_child = g_grand_child.add(wsman, "Selector", "ManagedSystem")
    g_g_grand_child.attr_add(wsman, "Name", "Name")

    return doc


def _get_power_state(client):
    """
    Get the power state from the wsman client
    """
    logging.debug("Getting power state")

    client.wake_up()

    namespace = _CIM_AssociatedPowerManagementService
    errno, errstr, doc = client.get(namespace)
    if errno:
        logging.error("Failed to get power state: %s (%s)", errstr, errno)
        return errno

    state = utils.xml_find(doc, namespace, "PowerState").text
    if is_int(state) and int(state) in POWER_STATES:
        return int(state)

    logging.warning("Invalid power state: %s", state)
    return POWER_STATE_INVALID


def _set_power_state(client, state):
    """
    Set the power state of the wsman client
    """
    logging.debug("Setting power state to: %s", state)

    client.wake_up()

    options = pywsman.ClientOptions()
    options.add_selector("Name", "Intel(r) AMT Power Management Service")

    doc = _request_power_state_change_input(state)
    errno, errstr, _retdoc = client.invoke(_CIM_PowerManagementService,
                                           "RequestPowerStateChange", data=doc,
                                           options=options)
    if errno:
        logging.error("Failed to set power state: %s (%s)", errstr, errno)
    return errno


class AMTPower():
    """
    Intel AMT power driver

    The power states as defined by AMT:
      2: Power On                   10: Master Bus Reset
      3: Sleep - Light              11: Diagnostic Interrupt (NMI)
      4: Sleep - Deep               12: Power Off - Soft Graceful
      5: Power Cycle (Off - Soft)   13: Power Off - Hard Graceful
      6: Power Off - Hard           14: Master Bus Reset Graceful
      7: Hibernate (Off - Soft)     15: Power Cycle (Off - Soft Graceful)
      8: Power Off - Soft           16: Power Cycle (Off - Hard Graceful)
      9: Power Cycle (Off - Hard)
    """
    def __init__(self, host, username, password):
        self.POWER_STATE_ON = POWER_STATE_ON
        self.POWER_STATE_CYCLE = POWER_STATE_CYCLE
        self.POWER_STATE_OFF = POWER_STATE_OFF
        self.POWER_STATE_RESET = POWER_STATE_RESET
        self.POWER_STATE_NMI = POWER_STATE_NMI
        self.POWER_STATE_INVALID = POWER_STATE_INVALID
        self.POWER_STATES = POWER_STATES

        self.client = wsman.WsManClient(host, username, password)

    def get_power_state(self):
        """
        Get the power state from the host
        """
        return _get_power_state(self.client)

    def set_power_state(self, state, wait=False, timeout=10):
        """
        Set the power state of the host
        """
        if state not in POWER_STATES:
            logging.error("Invalid power state: %s", state)
            return -1

        retval = _set_power_state(self.client, state)
        if retval or not wait:
            return retval

        now = time.time()
        while time.time() < (now + timeout):
            time.sleep(1)
            current_state = _get_power_state(self.client)
            if current_state == state:
                return 0

        logging.debug("Timed out waiting for requested power state")
        return -1
