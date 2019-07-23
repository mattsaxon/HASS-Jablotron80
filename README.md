# HASS-Jablotron80

Home Assistant platform to control Jablotron 80 alarm control panel via serial connection.

For 100 series devices please see other repo here https://github.com/plaksnor/HASS-JablotronSystem

** Model 80 tested with RPi using a JA-82T USB/Serial cable to a JA-82K control panel **

## Supported devices
- Probably any Jablron Oasis 80 series control panel
- Whilst I would have expected this to work with other USB/serial cables, I haven't had confirmation of others that the JA-82T working yet. I'd be happy to work through issues with anyone having trouble.

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

Note 1: Because my serial cable presents as a HID device the format is /dev/hidraw[x], others that present as serial may be at /dev/ttyUSB0 or similar. Use the following command line to identity the appropriate device

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

## Other Info

There is a thread discussing this integration [here](https://community.home-assistant.io/t/jablotron-ja-80-series-and-ja-100-series-alarm-integration/113315/3), however for issues, please raise the issue in this GitHub repo. 

## Future

I'm very happy to work with others to enhance this component and get others installation working.

Please raise an issue [here](https://github.com/mattsaxon/HASS-Jablotron80/issues)  
