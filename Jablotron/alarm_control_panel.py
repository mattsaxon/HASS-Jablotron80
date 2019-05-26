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
        self._data_flowing = threading.Event()

        try:         
            hass.bus.async_listen('homeassistant_stop', self.shutdown_threads)

            from concurrent.futures import ThreadPoolExecutor
            self._io_pool_exc = ThreadPoolExecutor(max_workers=5)    
            self._read_loop_future = self._io_pool_exc.submit(self._read_loop)
            self._watcher_loop_future = self._io_pool_exc.submit(self._watcher_loop)
            self._io_pool_exc.submit(self._startup_message)

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

    def _watcher_loop(self):

        while not self._stop.is_set():
            
            if not self._data_flowing.wait(2):
                _LOGGER.warn("Data has not been received for 2 seconds, retry startup message")
                self._startup_message()         
            else:
               _LOGGER.debug("Data is flowing, wait 5 seconds before checking again")
               time.sleep(5)

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

                time.sleep(1)

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

        ja101codes = {
            b'\x01': STATE_ALARM_DISARMED, # unsure which zone
            b'\x21': STATE_ALARM_DISARMED, # unsure which zone
            b'\x83': STATE_ALARM_ARMING, # Setting (Full)
            b'\xa3': STATE_ALARM_ARMING, # unsure which zone
            b'\x82': STATE_ALARM_ARMING, # Setting (Partial - at home)
            b'\x03': STATE_ALARM_ARMED_AWAY, # Set (Full)
            b'\x23': STATE_ALARM_ARMED_AWAY,  # unsure which zone
            b'\x02': STATE_ALARM_ARMED_HOME,  # Set (Partial - at home)
            b'\x7f': STATE_ALARM_TRIGGERED  #alarm activated! (this code is for 4405, not for 5122!) 
        }
               
        try:
            while True:

                self._data_flowing.clear()
                packet = self._f.read(64)
                self._data_flowing.set()

                if not packet:
                    _LOGGER.warn("No packets")
                    self._available = False
                    return 'No Signal'   

                self._available = True

                if packet[:2] == b'\x82\x01': # Jablotron JA-82
                    self._model = 'Jablotron JA-80 Series'
                    state = ja82codes.get(packet[2:3])

                    if state is None:
                        _LOGGER.debug("Unknown status packet is x82 x01 %s", packet[2:3])

                    elif state != "Heartbeat?" and state !="Key Press":
                        break

                elif packet[:2] == b'\x51\x22' or packet[:2] == b'\x44\x05': # Jablotron JA-101 
                    self._model = 'Jablotron JA-100 Series'
                    state = ja101codes.get(packet[2:3])

                    if state is None:
                        _LOGGER.debug("Unknown status packet is x51 x22 %s", packet[2:3])

                    elif state != "Heartbeat?" and state !="Key Press":
                        self._startup_message() # let's try sending another startup message here!
                        break
                        
                elif packet[:2] == b'\x52\x07': # PIR 1 data?
                    _LOGGER.debug("PIR 1 data? %s", packet[0:5])

                elif packet[:2] == b'\x52\x09': # PIR 2 data?
                    _LOGGER.debug("PIR 2 data? %s", packet[0:5])
                      
                elif packet[:2] == b'\x90\x19': # Unknown packet, but also receiving from JA-101
                    _LOGGER.debug("Unknown packet: %s", packet[0:5])
                      
                elif packet[:1] == b'\x82': 
                    pass # recognised, but as yet undeciphered JA-82 packets 

#                    if packet[1:2] == b'\x07': # debugging for additional JA-82 info
#                        if ja82codes.get(packet[2:3]) is None:  
#                            _LOGGER.debug("Unknown Data attribute for 07 type packet is: %s", packet[2:7])

                elif packet[:1] == b'\xd0' or packet[:1] == b'\xd2' or packet[:1] == b'\xd8':
                    pass # recognised, but as yet undeciphered JA-101 packets 

                else:         
                    _LOGGER.debug("Unknown packet: %s", packet)
#                    _LOGGER.error("Unrecognised data stream, device type likely not a JA-82 or JA101 control panel. Please raise an issue at https://github.com/mattsaxon/HASS-Jablotron80/issues with this packet info [%s]", packet)
#                    self._stop.set() 


        except (IndexError, FileNotFoundError, IsADirectoryError,
                UnboundLocalError, OSError):
            _LOGGER.warning("File or data not present at the moment: %s", self._file_path)
            return 'Failed'

        except Exception as ex:
            _LOGGER.error('Unexpected error: %s', format(ex) )
            return 'Failed'


        return state

    async def async_alarm_disarm(self, code=None):
        _LOGGER.debug("Send disarm command")
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
        _LOGGER.debug("Send arm home command")
        """Send arm home command.

        This method is a coroutine.
        """
        send_code = ""
        if self._config[CONF_CODE_ARM_REQUIRED]:
            send_code = code

        action = "*2"
        self._sendKeys(send_code, action)

    async def async_alarm_arm_away(self, code=None):
        _LOGGER.debug("Send arm away command")
        """Send arm away command.

        This method is a coroutine.
        """
        send_code = ""
        if self._config[CONF_CODE_ARM_REQUIRED]:
            send_code = code

        action = "*1"
        self._sendKeys(send_code, action)

    async def async_alarm_arm_night(self, code=None):
        _LOGGER.debug("Send arm night command")
        """Send arm night command.

        This method is a coroutine.
        """
        send_code = ""
        if self._config[CONF_CODE_ARM_REQUIRED]:
            send_code = code

        action = "*3"
        self._sendKeys(send_code, action)

    def _sendKeys(self, code, action):
        _LOGGER.debug("Sending keys")
        """Send via serial port."""
        payload = action

        _LOGGER.debug("sending %s", payload)

        if code is not None:
            payload += code
        
        _LOGGER.debug("Using keys for model %s", self._model)
        if self._model == 'Jablotron JA-80 Series':
            switcher = {
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
           
        elif self._model == 'Jablotron JA-100 Series':
            switcher = {
                "0": b'\x30',
                "1": b'\x31',
                "2": b'\x32',
                "3": b'\x33',
                "4": b'\x34',
                "5": b'\x35',
                "6": b'\x36',
                "7": b'\x37',
                "8": b'\x38',
                "9": b'\x39'
            }
        else:
            switcher = {}

        try:
            self._lock.acquire()

            if self._model == 'Jablotron JA-80 Series':

                packet_no = 0
                for c in payload:
                    packet_no +=1
                    packet = b'\x00\x02\x01' + switcher.get(c)
                    _LOGGER.debug('sending packet %i, message: %s', packet_no, packet)
                    self._sendPacket(packet)
              
            elif self._model == 'Jablotron JA-100 Series':

                packet_code = b''
                for c in code:
                    packet_code = packet_code + switcher.get(c)

                packet = b'\x80\x08\x03\x39\x39\x39' + packet_code
                _LOGGER.debug("Submitting alarmcode...")
                self._sendPacket(packet)

                if action == "*0":
                    packet = b'\x80\x02\x0d\x90'
                    _LOGGER.info('Disarm.')
                    _LOGGER.debug('sending packet: %s', packet)
                    self._sendPacket(packet)
                elif action == "*1":
                    packet = b'\x80\x02\x0d\xa0'
                    _LOGGER.info('Arm away.')
                    _LOGGER.debug('sending packet: %s', packet)
                    self._sendPacket(packet)
                elif action == "*2":
                    packet = b'\x80\x02\x0d\xb0'
                    _LOGGER.info('Arm at home.')
                    _LOGGER.debug('sending packet: %s', packet)
                    self._sendPacket(packet)
                elif action == "*3":
                    _LOGGER.warn('Arm night, but no actions defined yet! Use arm away instead, until arm night packets have been sniffed.')
                else:
                    _LOGGER.info("Unknown action: %s", action)
            else:
                _LOGGER.error('Unknown device, no actions defined.')

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

        if self._model == 'Jablotron JA-80 Series':
            try:
                self._lock.acquire()

                _LOGGER.debug('Sending startup message')
                self._sendPacket(b'\x00\x00\x01\x01')
                _LOGGER.debug('Successfully sent startup message')

            finally:
                self._lock.release()

        else:
            _LOGGER.debug('Sending startup message')
            self._sendPacket(b'\x00\x00\x01\x01')
            _LOGGER.debug('Successfully sent startup message')
