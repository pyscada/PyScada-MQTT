# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyscada.models import Device
from pyscada.models import Variable
from datetime import datetime
from . import PROTOCOL_ID
import traceback

from django.db import models
import re
import logging

logger = logging.getLogger(__name__)


class MQTTBroker(models.Model):
    mqtt_broker = models.OneToOneField(Device, on_delete=models.CASCADE)
    address = models.CharField(max_length=400)
    port = models.PositiveIntegerField(
        default=1883, help_text="default ports for MQTT are 1883 and 8883"
    )
    timeout = models.PositiveIntegerField(default=60)
    username = models.CharField(max_length=255, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    protocol_id = PROTOCOL_ID

    def parent_device(self):
        try:
            return self.mqtt_broker
        except:
            return None

    def __str__(self):
        return self.mqtt_broker.short_name


class MQTTVariable(models.Model):
    mqtt_variable = models.OneToOneField(Variable, on_delete=models.CASCADE)
    topic = models.CharField(max_length=255)
    topic_parser = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="a regular expression for parsing the value, leave blank to just parse by float, int or bool",
    )
    timestamp_topic = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="the topic where the timstamp is published, leave blank to use the receive timestamp",
    )
    timestamp_parser = models.CharField(
        max_length=255,
        default="%i",
        help_text="a string of format codes strptime, or %i for isoformat",
    )

    protocol_id = PROTOCOL_ID

    def __str__(self):
        return self.mqtt_variable.name

    def parse_timestamp(self, input_value):
        """parses a timestamp value and return a utc timestamp"""
        if self.timestamp_parser == "%i":
            try:
                return datetime.fromisoformat(input_value).timestamp()
            except:
                logger.warning(traceback.format_exc())
                return None
        try:
            return datetime.strptime(self.timestamp_parser, input_value).timestamp()
        except:
            logger.warning(traceback.format_exc())
            return None

    def parse_value(self, input_value):
        """parses a given value and return it in the right format to be stored in the variable"""

        if self.mqtt_variable.value_class in [
            "FLOAT32",
            "UNIXTIMEF32",
            "FLOAT64",
            "UNIXTIMEF64",
            "FLOAT48",
        ]:  # convert to float
            converter = float
        elif self.mqtt_variable.value_class in [
            "INT64",
            "UINT64",
            "UNIXTIMEI64",
            "UNIXTIMEI64",
            "INT48",
            "UNIXTIMEI32",
            "INT32",
            "UINT32",
            "INT16",
            "UINT16",
            "INT8",
            "UINT8",
        ]:  # convert to int
            converter = int
        elif self.mqtt_variable.value_class in ["BOOLEAN"]:
            converter = bool
        else:
            return None

        if self.topic_parser is not None:
            try:
                input_value = re.match(self.topic_parser, input_value)
                if input_value is None:
                    return None
                input_value = input_value[0]
            except:
                logger.warning(traceback.format_exc())
                return None

        try:
            if type(input_value) is str and (input_value == 'unavailable' or input_value == 'null'):
                return None
            return converter(input_value)
        except:
            logger.warning(traceback.format_exc())
            return None


class ExtendedMQTTBroker(Device):
    class Meta:
        proxy = True
        verbose_name = "MQTT Broker"
        verbose_name_plural = "MQTT Brokers"


class ExtendedMQTTVariable(Variable):
    class Meta:
        proxy = True
        verbose_name = "MQTT Variable"
        verbose_name_plural = "MQTT Variables"
