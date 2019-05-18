# HASS-Jablotron80

Home Assistant platform to control Jablotron 80 control panel via serial connection.

** Tested with RPi using a JA-82T USB/Serial cable to a JA-82K control panel **

## Supported devices
- Probably any JA-80 series control panel
- Whilst I would have expected this to work with other USB/serial cables, the only user I'm aware of with a JA-80T is not currently working
- For JA-100 series devices, this component can report status, but not set/unset the system

## Installation
To use this platform, copy alarm_control_panel.py to "<home assistant config dir>/custom_components/jablotron/" and add the config below to configuration.yaml

```
alarm_control_panel:
  - platform: jablotron
    serial_port: [serial port path]    
```

Example:
```
alarm_control_panel:
  - platform: jablotron
    serial_port: /dev/hidraw0     
    code: !secret alarm_code
    code_arm_required: False
    code_disarm_required: True
```

Note 1: Because my serial cable presents as a HID device there format is /dev/hidraw[x], others that present as serial may be at /dev/ttyUSB0 or similar. Use the following command line to identity the appropriate device

```
$ dmesg | grep usb
$ dmesg | grep hid
```


Note 2: if you supply a code, this is used as the default code to arm/disarm it

## Debug

If you have issues with this, I'd be happy to work with you on improving the code

Please post details of the issue with the appropriate logs entries

Change configuration.yaml to include:

```
logger:
  logs:
    custom_components.jablotron: debug
```

## Future

Will depend on feedback I receive as to if others are interested in using, or collaborating on improving this.
