# -*- coding: utf-8 -*-
from __future__ import unicode_literals

try:
    import paho.mqtt.client as mqtt_client

    driver_ok = True
except ImportError:
    driver_ok = False

from math import isnan, isinf
from time import time
from datetime import datetime

import traceback
import logging
import re

logger = logging.getLogger(__name__)


def _default_decoder(value):
    return value[0]


class Device:
    """
    MQTT Broker (device) class
    """

    def __init__(self, device):
        self.device = device
        self._address = device.mqttbroker.address
        self._port = device.mqttbroker.port
        self._timeout = device.mqttbroker.timeout
        self._device_not_accessible = 0
        self.variables = {}
        self.data = (
            {}
        )  # holds the raw data for each topic, Value is None if no new data is there
        self.broker = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        self.broker.on_message = self.on_message
        self.broker.username = device.mqttbroker.username
        self.broker.password = device.mqttbroker.password
        self._connect()

    def _connect(self):
        """
        connect to the MQTT Broker
        """
        try:
            self.broker.connect(self._address, int(self._port), int(self._timeout))
            self.broker.loop_start()  # start the comunication thread
            try:
                for variable in self.device.variable_set.filter(active=1):
                    if not hasattr(variable, "mqttvariable"):
                        continue
                    self.variables[variable.pk] = variable
                    if variable.readable:
                        self.broker.subscribe(variable.mqttvariable.topic)  # value Topic
                        self.data[variable.mqttvariable.topic] = None
                        if variable.mqttvariable.timestamp_topic is not None:
                            self.broker.subscribe(
                                variable.mqttvariable.timestamp_topic
                            )  # timestamp Topic
                            self.data[variable.mqttvariable.timestamp_topic] = None
            except:
                logger.warning(traceback.format_exc())

            return True
        except TimeoutError:
            logger.info("Cannot connect to the MQTT broker : timeout.")
        except Exception as e:
            logger.warning(f"Failed to connect to the MQTT broker : {e}")
        return False

    def _disconnect(self):
        """
        close the connection to the MQTT Broker
        """
        self.broker.loop_stop()

    def request_data(self):
        """process the data that was recived from the broker since last call"""
        output = []
        keys_to_reset = []
        for variable_id, variable in self.variables.items():
            if self.data[variable.mqttvariable.topic] is not None:
                value = self.data[variable.mqttvariable.topic].decode("utf-8")
                value = variable.mqttvariable.parse_value(value)
                timestamp = time()

                if variable.mqttvariable.timestamp_topic is not None:
                    if self.data[variable.mqttvariable.timestamp_topic] is None:
                        logger.debug("mqtt request_data timestamp_topic is None")
                        continue

                    timestamp = self.data[variable.mqttvariable.timestamp_topic].decode(
                        "utf-8"
                    )
                    timestamp = variable.mqttvariable.parse_timestamp(
                        timestamp
                    )  # convert

                    keys_to_reset.append(variable.mqttvariable.timestamp_topic)

                self.data[variable.mqttvariable.topic] = (
                    None  # reset value for next loop, this is done here for the case that we recieved the value, but waiting for the timestamp
                )

                if variable.update_values([value], [timestamp]):
                    output.append(variable)
        for key in keys_to_reset:
            self.data[key] = None  # reset value for next loop
        return output

    def on_message(self, client, userdata, msg):
        """callback for new PUBLISH messages, is called on receive from Server"""
        logger.debug(msg.topic + " " + str(msg.payload))
        if msg.topic not in self.data:
            return
        self.data[msg.topic] = msg.payload
