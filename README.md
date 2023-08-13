# Salix Charging Controller
[Home Assistant](https://www.home-assistant.io/) integration component, part of [Salix Project](https://github.com/artursulkowski/salix)

SLX Charging Controller controls EVSE (aka. charger) based on car battery state of charge (SOC). It makes decision about when charging should be enabled to:
* Immediatelly charge your car to avoid battery staying in low SOC
* Stop charging before battery is fully charged to avoid accelerated degradation.

For operation, SLX Charging Controller requires other Home Assistant integrations:
* Car's integration - to check battery SOC
* EVSE integration - to control charging process

For supported integration, configuration process is simplified. However, manual integration using entities is also possible.

**Supported car's integrations:**
| Car integration | Brand | Comment  |
| --- | --- | ---|
| [kia_uvo](https://github.com/Hyundai-Kia-Connect/kia_uvo) | Kia( UVO) <br> Hyundai (Bluelink) | Tested with: <br> Hyundai Kona|
| Manual Configuration <br> <sub> TODO link to description| N/A | You can select entity with SOC|
| Planned:  [BMW Connected Drive](https://www.home-assistant.io/integrations/bmw_connected_drive/)|BMW| (planned) |

**Supported EVSE integrations:**
| EVSE integration | Brand | Comment  |
| --- | --- | ---|
| [OpenEVSE](https://github.com/firstof9/openevseo) | [OpenEVSE](https://www.openevse.com/) | Tested |
| Manual Configuration <br> <sub> TODO link to description | N/A | You can select entity with SOC|

## How it works
Exemplary scenario:
1. You are connecting quite discharged car to the charger (e.g. SOC is 8%)
1. SLXCharging controller - checks SOC
1. Because SOC it is below `SOC Limit Min` (20%).
Charging starts immediatelly with full power.
1. Charging contrinues untill SOC reaches 20%.
1. Then charger is switched to PVCharge mode (charging from excess energy produced).
1. SLX Charging Controller monitors battery SOC and if it exceeds SOC Limit Max (e.g. 80%), charger is switched to STOPPED mode (no charging active).

## How you control it
Integration have few entities you can use to control it:

### Entity: Charge Method
This entity allows you to control in which mode SLX Charging Controller is working.
You can select ECO mode for charging using excess solar energy produced at house (EVSE must support it).
You can also switch to FAST mode which will make sure your car is charged immediatelly to requires SOC.

| Charge Method <br> value   | Description  |
| ---| --- |
| ECO <br> <sup> default</sup> | Keeps SOC between `SOC Limit Min` and `SOC Limit Max`<br> Uses both normal charging (full power available) and PVCharge (charging with excess energy)|
| FAST | Runs normal charging until car reaches `SOC targer` |
| Car SOC | descriwew |


### SOC entities
You can easily modify values

| SOC related entities   | Description  |
| ---| --- |
| SOC Limit Min <br> <sup> default = 20% </sup> | Minimum SOC that system tries to keep <br> Regardless of selected mode (Even in ECO)|
SOC Limit Max <br> <sup> default = 80% </sup> | Maximum SOC kept when charging in ECO mode <br> can be overwritten by SOC target |
SOC target <br> <sup> default = 20% </sup> | In `Charge Method` = `FAST` charging is run until SOC = `SOC target` is reached <br> In `Charge Method` = `ECO` you can temporarily increase maximum SOC    |


### Output entities
Integration also delivers few

If car's SOC is below



## How to install

TODO:
- describe installation process.


## How to configure


## Automatic setup

## manual setup

TODO:

- what kind of entities are accepted.
- what is the Update time.

## Known issues?
- Early development

# Want to contribute?
To be described
