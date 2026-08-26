# Nuve Thermostat — Home Assistant Integration

A community-maintained **Home Assistant custom integration** for Nuve cloud thermostats and compatible contractor-branded applications, including Nuve Home and Greenfoot Energy Solutions.

The integration connects Home Assistant to the Nuve cloud service and provides automatic thermostat discovery, climate control, fan-circulation scheduling, and diagnostic entities.

> This project is an independent community integration for Home Assistant. It is not affiliated with, sponsored by, or endorsed by Nuve Controls LLC, Nuve Home, Greenfoot Energy Solutions, or any HVAC contractor.

## Features

| Feature | Description |
|---|---|
| Automatic discovery | Enter only your Nuve account email and password; available thermostats are discovered automatically. |
| Climate control | Read and change supported operating modes and target temperature. |
| Fan circulation | Select Auto, 10, 20, 30, 40, 50 minutes per hour, or Always on. |
| Contractor information | Display the contractor/company associated with the thermostat. |
| Environmental data | Current temperature, humidity, and CO₂ status when provided by the Nuve API. |
| HVAC diagnostics | Online status, heating stage, cooling stage, auxiliary stage, fan status, emergency state, vacation mode, hold state, and performance-test state. |
| Connectivity information | Wi‑Fi name, Wi‑Fi signal strength, client ID, firmware information, and timezone when provided by the service. |
| Alerts | Report the number of active device alerts when provided by the account and API. |

## Supported applications and brands

Nuve distributes compatible thermostats through both the general Nuve Home application and contractor-branded applications. The Android package name does not determine compatibility; the Nuve account and cloud API access determine which devices are available.

Known application brands include Nuve Home, Greenfoot Energy Solutions, Topline Home, Sierra Comfort Control, Semper Fi Edge, One Hour Air, Peak Home, Logan Services, Aire Serv, The Eco Plumbers, and other contractor-branded Nuve applications.

This list is not an official compatibility guarantee. If another branded application uses the Nuve cloud platform, please open an issue with the application name and a redacted diagnostic log.

## Installation through HACS

### Custom repository installation

Until this repository is included in the default HACS catalog, install it as a custom repository:

1. Open **HACS → Integrations** in Home Assistant.
2. Open the three-dot menu and select **Custom repositories**.
3. Add this repository URL:

   ```text
   https://github.com/vadyusik01/nuve-thermostat
   ```

4. Select **Integration** as the repository type.
5. Add the repository and install **Nuve Thermostat — Home Assistant Integration**.
6. Restart Home Assistant.
7. Open **Settings → Devices & services → Add integration** and search for **Nuve Thermostat**.

### Manual installation

Download the latest release and copy this directory into the Home Assistant configuration directory:

```text
/config/custom_components/nuve_thermostat/
```

The final path must contain:

```text
/config/custom_components/nuve_thermostat/manifest.json
```

Restart Home Assistant after copying the files.

## Configuration

Open **Settings → Devices & services → Add integration**, search for **Nuve Thermostat**, and enter only:

| Field | Description |
|---|---|
| Email | Email address used for the Nuve application account. |
| Password | Password used for the Nuve application account. |

The integration logs in, requests the list of devices associated with the account, and selects the available thermostat automatically. If multiple thermostats are available, Home Assistant asks you to select one. The serial number should not normally be entered manually.

## Entities

The integration creates a Climate entity for heating and cooling control. It also creates a separate **Fan circulation** Select entity. Fan circulation is intentionally not represented as an HVAC `fan_only` mode because Nuve uses a per-hour circulation schedule rather than a conventional HVAC operating mode.

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

Confirm that the installed package contains `climate.py`, `select.py`, `sensor.py`, and `binary_sensor.py`. Restart Home Assistant after updating the files. Look for errors containing `select.py` in **Settings → System → Logs**. The Fan circulation entity is a Select entity and may not appear directly inside the Climate card; check **Settings → Devices & services → Nuve Thermostat → Entities** or **Developer Tools → States**.

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

Diagnostic logs may contain device serial numbers, contractor information, Wi‑Fi names, client IDs, timestamps, and API error details. Redact these values before sharing logs publicly. Never share passwords, Bearer tokens, refresh tokens, cookies, or complete authentication payloads.

## Limitations

The integration depends on the availability and behavior of the Nuve cloud API. API endpoints, authentication behavior, device permissions, alert formats, and available fields may vary by account, contractor, application brand, or server-side feature flags. A cloud outage or API change can temporarily affect control and monitoring.

The integration is not a replacement for professional HVAC service. Emergency and diagnostic indicators are informational and should not be used as the sole basis for safety-critical decisions.

## Compatibility reports and support

Please use [GitHub Issues](https://github.com/vadyusik01/nuve-thermostat/issues) for bug reports and feature requests. Include the Home Assistant version, integration version, Nuve application or contractor brand, a description of the failed action, and a redacted log excerpt.

Do not include passwords, access tokens, refresh tokens, cookies, or unredacted personal information.

## License and trademarks

This repository is intended to be released under the MIT License unless a different license is added by the repository owner. Add a `LICENSE` file before publishing a stable release.

Nuve, Nuve Home, Greenfoot Energy Solutions, and the names and logos of HVAC contractors are trademarks or trade names of their respective owners. This repository does not grant permission to use those trademarks or logos. Brand assets included in this project must be used only with appropriate permission or under an applicable nominative fair-use basis. Remove or replace any logo for which permission has not been obtained.

## Maintainer

Maintained by [@vadyusik01](https://github.com/vadyusik01).

Repository: [github.com/vadyusik01/nuve-thermostat](https://github.com/vadyusik01/nuve-thermostat)

## Disclaimer

This is an independent open-source project. Use it at your own risk. The maintainer is not responsible for service interruptions, incorrect data, HVAC equipment behavior, account issues, or damage resulting from use of the integration.
