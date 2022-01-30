# HASS-Jablotron80

Unmaintained Home Assistant platform to control Jablotron 80 alarm control panel via serial connection.

For 80 series see https://github.com/tahvane1/jablotron80

For 100 series devices please see other repo here https://github.com/plaksnor/HASS-JablotronSystem

** Model 80 tested with RPi using a JA-82T USB/Serial cable to a JA-82K control panel **

## Supported devices
- Probably any Jablotron Oasis 80 series control panel
- Whilst I would have expected this to work with other USB/serial cables, I haven't had confirmation of others that the JA-82T working yet. I'd be happy to work through issues with anyone having trouble.

## Installation
To use this platform, copy alarm_control_panel.py to "<home assistant config dir>/custom_components/Jablotron80/" and add the config below to configuration.yaml

```
alarm_control_panel:
  - platform: Jablotron80
    serial_port: [serial port path]    
    code: [code to send to physical panel and code to enter into HA UI]
    code_panel_arm_required: [True if you need a code to be sent to physical panel on arming, Default False]
    code_panel_disarm_required: [True if you need a code to be sent to physical panel on disarming, Default True]
    code_arm_required: [True if you want a code to need to be entered in HA UI prior to arming, Default False]
    code_disarm_required: [True if you want a code to need to be entered in HA UI prior to disarming, Default True]
    sensor_names: [Optional mapping from sensor ID to name for more user friendly triggered information]
```

Example:
```
alarm_control_panel:
  - platform: Jablotron80
    serial_port: /dev/hidraw0     
    code: !secret alarm_code
    code_panel_arm_required: False
    code_panel_disarm_required: True
    code_arm_required: False
    code_disarm_required: False
    sensor_names: 
      1: "Front door"
      2: "Garden door"
      3: "Bedroom"
```

Note 1: Because my serial cable presents as a HID device the format is /dev/hidraw[x], others that present as serial may be at /dev/ttyUSB0 or similar. Use the following command line to identity the appropriate device

```
$ dmesg | grep usb
$ dmesg | grep hid
```

Note 2: if you supply a code, this is used as the default code to arm/disarm it

## Usage in automation
With the following automation setup, you'll get a notification when alarm is triggerd with the id and name (if you configured sensor_names) of the sensor that triggered it.

```
  trigger:
  - entity_id: alarm_control_panel.jablotron_alarm
    platform: state
    to: triggered
  condition: []
  action:
  - data_template:
      message: ALARM! {{ trigger.to_state.attributes.triggered_by }}
    service: notify.notify
```

## Debug

If you have issues with this, I'd be happy to work with you on improving the code

Please post details of the issue with the appropriate logs entries

Change configuration.yaml to include:

```
logger:
  logs:
    custom_components.jablotron: debug
```

## Other Info

There is a thread discussing this integration [here](https://community.home-assistant.io/t/jablotron-ja-80-series-and-ja-100-series-alarm-integration/113315/3), however for issues, please raise the issue in this GitHub repo. 

## What if my HA instance isn't near my alarm control panel?

A number of users have had this issue and there is so far one option confirmed as being able to create a workaround for this.

1. [USB over IP](https://derushadigital.com/other%20projects/2019/02/19/RPi-USBIP-ZWave.html)

Note: See also [issue 2](https://github.com/mattsaxon/HASS-Jablotron80/issues/8)

Further work to use MQTT may be undertaken at somepoint, see [issue 6](https://github.com/mattsaxon/HASS-Jablotron80/issues/6) 

## Future

I'm very happy to work with others to enhance this component and get others installation working.

Please raise an issue [here](https://github.com/mattsaxon/HASS-Jablotron80/issues)  
