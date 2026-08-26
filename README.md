# Nuve Thermostat — Home Assistant Integration

A free and open-source **Home Assistant custom integration** for Nuve cloud thermostats and compatible contractor-branded HVAC applications, including Nuve Home and Greenfoot Energy Solutions.

The integration connects Home Assistant to the Nuve cloud service and provides automatic thermostat discovery, climate control, fan-circulation scheduling, environmental data, and diagnostic entities.

> This is an independent community project. It is not affiliated with, sponsored by, or endorsed by Nuve Controls LLC, Nuve Home, Greenfoot Energy Solutions, or any HVAC contractor.

**Current release:** `0.4.0`

Version 0.4.0 is the initial public release.

## Features

| Feature | Description |
|---|---|
| Automatic discovery | Enter only your Nuve account email and password. Available thermostats are discovered automatically. |
| Climate control | Read and change supported operating modes and target temperature. |
| Fan circulation | Select Auto, 10, 20, 30, 40, or 50 minutes per hour, or Always on. |
| Contractor information | Display the contractor or company associated with the thermostat when provided by the Nuve service. |
| Environmental data | Current temperature, humidity, and CO₂ status when provided by the API. |
| HVAC diagnostics | Online status, heating stage, cooling stage, auxiliary stage, fan status, emergency state, vacation mode, hold state, and performance-test state when available. |
| Connectivity information | Wi-Fi name, Wi-Fi signal strength, client ID, firmware information, and timezone when provided by the service. |
| Alerts | Report active device alerts when provided by the account and API. |

## Nuve thermostat apps and contractor brands

Nuve thermostats may be distributed through the general Nuve Home application or through contractor-branded applications. Depending on the installer, HVAC company, and region, the same Nuve thermostat platform may appear under different application names.

The following Nuve-related thermostat applications and contractor brands have been identified in Google Play. Many of these applications are published by Nuve Controls LLC and use the Nuve cloud ecosystem. The list is provided to help users find the integration when their thermostat is branded differently; it is not an official compatibility guarantee.

<details>
<summary>View the full list of identified Nuve-related apps and brands</summary>

Nuve Home, Greenfoot Energy Solutions, Topline Home, Sierra Comfort Control, Three Guys, Veteran Heating & Cooling, Cozy Thermostat, RIA Thermostat, RR Total Comfort Thermostat, Thermall Heating & Cooling, Air Conditioning Experts, Right Away Home, Advanced Texas Air, Comfort Buddy, Innovative Home, Air Control Home Services, Comfort Techs, Thermal Comfort Solutions, Mechanical Heating & Cooling, AGE Heating & Cooling, New Era Home, Cantu's Air Home App, At Your Service Heat & Cool, Real Time Bros, Rolando's HVAC, A/C Control, Beach & Sons, AccuTech Pulse, EBreeze, Riv Comfort, Spartan Comfort, Larson Star, TeeTemp, Air Titans, Thermodynamix Connect, Chris Heating & Cooling, Rebel Aire, 365 HVAC, Cunningham Connect, Cozy Home Services, Product Air, Air Concepts Home, Thermo Direct, Expert HVAC, Integrity Air, Rapid Heat & Air, Absolute Comfort HVAC, Marathon Home, Comfort Tech Home, Total Comfort, 74 Degrees Home, Around The Clock Home, R3 Air, Air Depot, Cool Air Today, Valo Home, Manuel & Son's Services Co, AAA Home Controls, A-1 Heating and Cooling, ACES Heating & Cooling, The Heating & Cooling Guys, Chuck's A/C, Apollo Home, Fresno Heating & Cooling, Best Virginia HVAC, Breeze Home, Climate Control Home, Frontera Refrigeration Home, Air Kustoms Connect, Latitude Connect, Conditioned Air Solutions, CELCO HOME, Dalton's Home, Tuck & Howell, AIR, INC, Jamison Smart Stat, LV Heating & Cooling, Qozy, Peak Home, Logan Services, and Aire Serv.

</details>

The application name depends on the HVAC contractor or installer. Compatibility is determined by the Nuve cloud account and connected thermostat, not by the application name alone. If your thermostat is controlled by another contractor-branded Nuve application, please open an issue with the application name and a redacted diagnostic log.

## Installation through HACS

### Custom repository installation

Until this repository is included in the default HACS catalog, install it as a custom repository:

1. Open **HACS → Integrations** in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Add this repository URL:

   ```text
   https://github.com/Vadyusik01/Nuve-thermostat
   ```

4. Select **Integration** as the repository type.
5. Add the repository and install **Nuve Thermostat**.
6. Restart Home Assistant.
7. Open **Settings → Devices & services → Add integration** and search for **Nuve Thermostat**.

### Manual installation

Download the `0.4.0` release from GitHub and copy the following directory into the Home Assistant configuration directory:

```text
/config/custom_components/nuve_thermostat/
```

The final path must contain:

```text
/config/custom_components/nuve_thermostat/manifest.json
```

Restart Home Assistant after copying the files.

## Configuration

Open **Settings → Devices & services → Add integration**, search for **Nuve Thermostat**, and enter only the credentials used by the Nuve or contractor-branded mobile application.

| Field | Description |
|---|---|
| Email | Email address used for the Nuve application account. |
| Password | Password used for the Nuve application account. |

The integration logs in, requests the list of devices associated with the account, and discovers available thermostats automatically. If multiple thermostats are available, Home Assistant asks you to select one. The serial number should not normally be entered manually.

## Entities

The integration creates a Climate entity for heating and cooling control. It also creates a separate **Fan circulation** Select entity.

Fan circulation is intentionally not represented as an HVAC `fan_only` mode because Nuve uses a per-hour circulation schedule rather than a conventional HVAC operating mode. Changing the fan-circulation setting does not change the heating or cooling target temperature.

Typical entities include:

```text
climate.nuve_<serial_number>
select.nuve_<serial_number>_fan_circulation
sensor.nuve_<serial_number>_current_temperature
sensor.nuve_<serial_number>_humidity
sensor.nuve_<serial_number>_heating_stage
sensor.nuve_<serial_number>_cooling_stage
binary_sensor.nuve_<serial_number>_device_online
binary_sensor.nuve_<serial_number>_heat_pump_emergency
```

Entity IDs may differ depending on the Home Assistant entity registry and the selected device.

## Example service calls

Set fan circulation to 30 minutes per hour:

```yaml
service: select.select_option
target:
  entity_id: select.nuve_04_126_007226_fan_circulation
data:
  option: "30 min"
```

Set the Climate operating mode to cooling:

```yaml
service: climate.set_hvac_mode
target:
  entity_id: climate.nuve_04_126_007226
data:
  hvac_mode: cool
```

## Dashboard example

```yaml
type: entities
title: Nuve Thermostat
entities:
  - entity: climate.nuve_04_126_007226
    name: Climate
  - entity: select.nuve_04_126_007226_fan_circulation
    name: Fan circulation
  - entity: sensor.nuve_04_126_007226_humidity
    name: Humidity
  - entity: sensor.nuve_04_126_007226_heating_stage
    name: Heating stage
  - entity: sensor.nuve_04_126_007226_cooling_stage
    name: Cooling stage
  - entity: binary_sensor.nuve_04_126_007226_device_online
    name: Device online
  - entity: binary_sensor.nuve_04_126_007226_heat_pump_emergency
    name: Heat-pump emergency
```

## Troubleshooting

### The thermostat is not discovered

Verify that the email and password work in the official Nuve or contractor-branded application. Check the Home Assistant log for authentication or API errors. Do not post your password, access token, refresh token, or complete unredacted API responses.

### The Fan circulation entity is missing

Confirm that the installed package contains `climate.py`, `select.py`, `sensor.py`, and `binary_sensor.py`. Restart Home Assistant after updating the files. Look for errors containing `select.py` in **Settings → System → Logs**.

The Fan circulation entity is a Select entity and may not appear directly inside the Climate card. Check **Settings → Devices & services → Nuve Thermostat → Entities** or **Developer Tools → States**.

### A duplicate entity error appears

Do not install two copies of the same `nuve_thermostat` domain at the same time. Home Assistant loads:

```text
/config/custom_components/nuve_thermostat/
```

A directory named `nuve_thermostat_backup` is not loaded as an integration, but duplicate Config Entries for the same thermostat can still cause duplicate entity errors. Keep one Config Entry per thermostat.

### API errors occur when changing fan circulation

The Nuve fan endpoint requires both `mode` and `workingPerHour`. If the endpoint changes or returns a new validation error, open a GitHub issue with the error message after removing credentials and tokens.

## Privacy and security

This integration communicates with the Nuve cloud service. It does not provide local thermostat control. Login credentials are stored by Home Assistant in the Config Entry and must not be committed to GitHub or pasted into public issue reports.

Diagnostic logs may contain device serial numbers, contractor information, Wi-Fi names, client IDs, timestamps, and API error details. Redact these values before sharing logs publicly. Never share passwords, Bearer tokens, refresh tokens, cookies, or complete authentication payloads.

## Limitations

The integration depends on the availability and behavior of the Nuve cloud API. API endpoints, authentication behavior, device permissions, alert formats, and available fields may vary by account, contractor, application brand, or server-side feature flags. A cloud outage or API change can temporarily affect control and monitoring.

The integration is not a replacement for professional HVAC service. Emergency and diagnostic indicators are informational and should not be used as the sole basis for safety-critical decisions.

## Compatibility reports and support

Please use [GitHub Issues](https://github.com/Vadyusik01/Nuve-thermostat/issues) for bug reports and feature requests. Include the Home Assistant version, integration version, Nuve application or contractor brand, a description of the failed action, and a redacted log excerpt.

Do not include passwords, access tokens, refresh tokens, cookies, or unredacted personal information.

## Project status, trademarks, and contributions

This is a free, independent community project for Home Assistant users. The integration is provided for development, testing, and compatibility research and is not affiliated with or endorsed by Nuve Controls LLC, Nuve Home, Greenfoot Energy Solutions, or any HVAC contractor.

Everyone is welcome to review the project, report bugs, suggest improvements, and submit Pull Requests. Contributions must not contain credentials, private information, proprietary application files, or confidential API data.

All trademarks, product names, company names, and logos mentioned in this repository belong to their respective owners. They are referenced only to describe possible compatibility and help users identify the correct Home Assistant integration.

The project is provided as-is, without warranties or guarantees. Cloud availability, API behavior, device permissions, and compatibility may change without notice.

The current release is intended for community evaluation and development. Additional licensing information may be added in a future release.

## Maintainer

Maintained by [@vadyusik01](https://github.com/vadyusik01).

Repository: [github.com/Vadyusik01/Nuve-thermostat](https://github.com/Vadyusik01/Nuve-thermostat)

## Disclaimer

This is an independent open-source project. Use it at your own risk. The maintainer is not responsible for service interruptions, incorrect data, HVAC equipment behavior, account issues, or damage resulting from use of the integration.
