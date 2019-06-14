"""This platform enables the possibility to control a MQTT alarm."""
import logging
import re
import time
import voluptuous as vol
import asyncio
import threading

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (
    CONF_CODE, CONF_DEVICE, CONF_NAME, CONF_VALUE_TEMPLATE,
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED, STATE_ALARM_PENDING, STATE_ALARM_ARMING, STATE_ALARM_TRIGGERED)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_PORT = 'serial_port'

CONF_CODE_ARM_REQUIRED = 'code_arm_required'
CONF_CODE_DISARM_REQUIRED = 'code_disarm_required'

DEFAULT_NAME = 'Jablotron Alarm'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SERIAL_PORT): cv.string,
    vol.Optional(CONF_CODE): cv.string,
    vol.Optional(CONF_CODE_ARM_REQUIRED, default=False): cv.boolean,
    vol.Optional(CONF_CODE_DISARM_REQUIRED, default=True): cv.boolean,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):

    async_add_entities([JablotronAlarm(hass,config)])

class JablotronAlarm(alarm.AlarmControlPanel):
    """Representation of a Jabltron alarm status."""

    def __init__(self, hass, config):
        """Init the Alarm Control Panel."""
        self._state = None
        self._sub_state = None
        self._name = config.get(CONF_NAME)
        self._file_path = config.get(CONF_SERIAL_PORT)
        self._available = False
        self._code = config.get(CONF_CODE)
        self._f = None
        self._hass = hass
        self._config = config
        self._model = 'Unknown'
        self._lock = threading.BoundedSemaphore()
        self._stop = threading.Event()

        try:         
            hass.bus.async_listen('homeassistant_stop', self.shutdown_threads)

            from concurrent.futures import ThreadPoolExecutor
            self._io_pool_exc = ThreadPoolExecutor(max_workers=5)    
            self._io_pool_exc.submit(self._startup_message)
            self._read_loop_future = self._io_pool_exc.submit(self._read_loop)

        except Exception as ex:
            _LOGGER.error('Unexpected error: %s', format(ex) )


    def shutdown_threads(self, event):

        _LOGGER.debug('handle_shutdown() called' )

        self._stop.set()

        _LOGGER.debug('exiting handle_shutdown()' )

#    @property
#    def unique_id(self):
#        """Return a unique ID."""
#        return 'alarm_control_panel.jablotron.test'

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def available(self):
        return self._available

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        code = self._code
        if code is None:
            return None
        if isinstance(code, str) and re.search('^\\d+$', code):
            return alarm.FORMAT_NUMBER
        return alarm.FORMAT_TEXT

    async def _update_loop(self):

        while True:
            await self._update_required.wait()
            self.async_schedule_update_ha_state()
            self._update_required.clear()

    async def _update(self):

            self.async_schedule_update_ha_state()

    def _read_loop(self):

        try:

            while not self._stop.is_set():

                self._lock.acquire()

                self._f = open(self._file_path, 'rb', 64)

                new_state = self._read()

                if new_state != self._state:
                    _LOGGER.info("Jablotron state change: %s to %s", self._state, new_state )
                    self._state = new_state

                    asyncio.run_coroutine_threadsafe(self._update(), self._hass.loop)                   

                self._f.close()

                self._lock.release()

                time.sleep(1) # read state once every second, no need for more!

        except Exception as ex:
            _LOGGER.error('Unexpected error: %s', format(ex) )

        finally:
            _LOGGER.debug('exiting read_loop()' )

    def _read(self):

        ja82codes = {
            b'@': STATE_ALARM_DISARMED,
            b'A': STATE_ALARM_ARMED_HOME, # Set (Zone A)
            b'B': STATE_ALARM_ARMED_NIGHT, # Set (Zone A & B)
            b'C': STATE_ALARM_ARMED_AWAY, # Set (Zone A, B & C)
            b'Q': STATE_ALARM_PENDING, # Setting (Zone A)
            b'R': STATE_ALARM_PENDING, # Setting (Zones A & B)
            b'S': STATE_ALARM_ARMING, # Setting (Full)
            b'G': STATE_ALARM_TRIGGERED, 
            b'\xff': "Heartbeat?", # 25 second heatbeat
            b'\xed': "Heartbeat?",
            b'\xe7': "?",
            b'\xe3': "?",
            b'\xb7': "?",
            b'\xb4': "?",
            b'\xba': "?",
            b'\x80': "Key Press",
            b'\x81': "Key Press",
            b'\x82': "Key Press",
            b'\x83': "Key Press",
            b'\x84': "Key Press",
            b'\x85': "Key Press",
            b'\x86': "Key Press",
            b'\x87': "Key Press",
            b'\x88': "Key Press",
            b'\x89': "Key Press",
            b'\x8e': "Key Press",
            b'\x8f': "Key Press"
        }

        try:
            while True:

                packet = self._f.read(64)

                if not packet:
                    _LOGGER.warn("No packets")
                    self._available = False
                    return 'No Signal'   

                self._available = True

                if packet[:1] == b'\x82': # all JA-82 packets begin x82 

                    self._model = 'Jablotron JA-80 Series'
                    byte_two = int.from_bytes(packet[1:2], byteorder='big', signed=False)
                    
                    if byte_two >= 1 and byte_two <= 8: # all 2nd packets I have seen are between 1 and 7 

                        state = ja82codes.get(packet[2:3]) # the state is in the 3rd packet

                        if state is None:
                            _LOGGER.debug("Unknown status packet is %s", packet[:8])

                        elif state != "Heartbeat?" and state !="Key Press" and state !="?" :
                            return state

                    else:
                        _LOGGER.warn("Unknown packet is %s", packet[:8])

                else:         
                    _LOGGER.error("The data stream is not recongisable as a JA-82 control panel. Please raise an issue at https://github.com/mattsaxon/HASS-Jablotron80/issues with this packet info [%s]", packet)
                    self._stop.set()


        except (IndexError, FileNotFoundError, IsADirectoryError,
                UnboundLocalError, OSError):
            _LOGGER.warning("File or data not present at the moment: %s",
                            self._file_path)
            return 'Failed'

        except Exception as ex:
            _LOGGER.error('Unexpected error: %s', format(ex) )
            return 'Failed'



    async def async_alarm_disarm(self, code=None):
        """Send disarm command.

        This method is a coroutine.
        """
        send_code = ""

        if self._config[CONF_CODE_DISARM_REQUIRED]:
            if code == "":
                code = self._code
            send_code = code

        payload = "*0"
        self._sendKeys(send_code, payload)

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command.

        This method is a coroutine.
        """
        send_code = ""
        if self._config[CONF_CODE_ARM_REQUIRED]:
            send_code = code

        action = "*2"
        self._sendKeys(send_code, action)

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command.

        This method is a coroutine.
        """
        send_code = ""
        if self._config[CONF_CODE_ARM_REQUIRED]:
            send_code = code

        action = "*1"
        self._sendKeys(send_code, action)

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command.

        This method is a coroutine.
        """
        send_code = ""
        if self._config[CONF_CODE_ARM_REQUIRED]:
            send_code = code

        action = "*3"
        self._sendKeys(send_code, action)

    def _sendKeys(self, code, action):
        """Send via serial port."""
        payload = action

        _LOGGER.debug("sending %s", payload)

        if code is not None:
            payload += code
        
        key_map = {
            "0": b'\x80',
            "1": b'\x81',
            "2": b'\x82',
            "3": b'\x83',
            "4": b'\x84',
            "5": b'\x85',
            "6": b'\x86',
            "7": b'\x87',
            "8": b'\x88',
            "9": b'\x89',
            "#": b'\x8e',
            "?": b'\x8e',
            "*": b'\x8f'
        }

        try:
            self._lock.acquire()

            packet_no = 0
            for c in payload:
                packet_no +=1
                packet = b'\x00\x02\x01' + key_map.get(c)
                _LOGGER.debug('sending packet %i, message: %s', packet_no, packet)
                self._sendPacket(packet)

        except Exception as ex:
                    _LOGGER.error('Unexpected error: %s', format(ex) )

        finally:
            self._lock.release()


    def _sendPacket(self, packet):
        f = open(self._file_path, 'wb')
        f.write(packet)
        time.sleep(0.1) # lower reliability without this delay
        f.close()        

    def _startup_message(self):
        """ Send Start Message to panel"""

        try:
            # self._lock.acquire()

            _LOGGER.debug('Sending startup message')
            self._sendPacket(b'\x00\x00\x01\x01')
            _LOGGER.debug('Successfully sent startup message')

        finally:
            pass
            #self._lock.release()
