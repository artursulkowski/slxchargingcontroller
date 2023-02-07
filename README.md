# Salix Charging Controller
[Home Assistant](https://www.home-assistant.io/) integration component, part of [Salix Project](https://github.com/artursulkowski/salix)

Charging Controller controlls EV charger to:
* Achieve target SOC during charging session.

## Work status
**Please treat this as work in progress.**
Currently this isn't fully functional integration.


# Technical design
Integration is using [entities](https://developers.home-assistant.io/docs/core/entity/) already registered in HA to obtain information about EV battery SOC, current charging status.
At intergration's configuration user can select input entities which are fitting

Why use entities as intergration's input?
* Very flexible solution - can connect to multiple other integrations already exisiting in the system.
* Easy development - can use HA WebUI "States" to modify value of entity for testing and troubleshooting purpose.

Disadvantages:
* Requires a lot of manual configuration.
* Error prone.

## Input entities:

| Input     | Unit of Measurement | Device Class | Description  |
| ---| --- | --- | --- |
| EVSE Session Energy | kWh, Wh | any | amount of energy added during charging session |
| EVSE | any | plug | Status of charger's plug: On - pluged in, Off - unpluged |
| Car SOC | % | any | Car's battery SOC |
| Car SOC Update time | any | timestamp | Time in which Car SOC was read. In ideal world we could use [state.last_updated](https://www.home-assistant.io/docs/configuration/state_object/), but in case of [Hyundai-Kia-Connect](https://github.com/Hyundai-Kia-Connect/kia_uvo) real update time is stored in separate entity |


# Home Assistant tips & tricks

## (Development) How to add this integration
This integration git is clonned into HA `core/homeassistant/components/slxchargingcontroller` folder.
To make it visible at "add integration" page - I needed to add following entry into `core/homeassistant/generated/integrations.json`
``` json
"slxchargingcontroller": {
    "name": "Slx Charging Controller",
    "integration_type": "hub",
    "config_flow": true,
    "iot_class": "local_push"
},
```

## Creating test entitites -  configuration.yaml
Entries in configuration.yaml to create devices based on MQTT integration.
Entities are created even if MQTT integration isn't receiving any messages oveor given MQTT topic. I use this approach for creating testing entities (topic _dummy_)

``` yaml
mqtt:
  sensor:
    - name: "OpenEVSE charger"
      object_id: OpenEVSECharger
      state_topic: openevse/temp
      value_template: "{{ value | float / 10}}"
      unit_of_measurement: "°C"

    - name: "OpenEVSE charger2"
      object_id: OpenEVSECharger2
      state_topic: openevse/wh
      value_template: "{{ value | float / 1000}}"
      unit_of_measurement: "kWh"

    - name: "OpenEVSE Session Energy"
      object_id: openevsecharger_session_energy
      state_topic: openevse/session_energy
      value_template: "{{ value | float / 1000}}"
      unit_of_measurement: "kWh"

    - name: "Dummy SOC"
      object_id: dummy_measured_soc
      state_topic: dummy/soc
      value_template: "value"
      device_class: battery
      unit_of_measurement: "%"

    - name: "Dummy SOC timestamp"
      object_id: dummy_soc_timestamp
      state_topic: dummy/soctimestamp
      device_class: timestamp

  binary_sensor:
    - name: "Dummy Charger plugged"
      object_id: dummy_charger_plugged
      state_topic: dummy/plug
      value_template: "value"
      device_class: plug
```

