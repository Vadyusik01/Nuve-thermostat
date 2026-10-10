Nuve Thermostat — Home Assistant Integration
A free and open-source Home Assistant custom integration for Nuve cloud thermostats and compatible contractor-branded HVAC apps (Nuve Home, Greenfoot Energy Solutions, and related brands).

This is an independent community project. It is not affiliated with, sponsored by, or endorsed by Nuve Controls LLC, Nuve Home, Greenfoot Energy Solutions, or any HVAC contractor.

Current release: 0.9.8

Features
Feature	Description
Account login	Email + password from the mobile app (Nuve or contractor brand).
Device discovery	Lists thermostats on the account (/getSn); pick one if several.
Climate	Read/write HVAC mode (off / heat / cool / auto) and target temperature.
Presets	Vacation and auxiliary/emergency heat (best-effort API mode ids 4 and 6).
Fan circulation	Separate Select entity: Auto, 10–50 min/hour, Always on (not HVAC fan_only).
Backlight	On/off, brightness, hue, saturation, shade index; HSV via cloud API.
Automatic mode colors	Optional palette: color follows HVAC state, active stages, fan, vacation.
Sensors	Temperature, humidity, stages, CO₂ status, Wi‑Fi, firmware, alerts (when API provides them).
Binary sensors	Online, vacation, hold, emergency, performance test.
Cloud polling	Shared runtime, token re-login on 401, staggered poll intervals.
Control is cloud-only (https://mobileapi.nuvehvac.com/api). There is no local LAN API in this integration.

Installation
HACS (custom repository)
HACS → Integrations → ⋮ → Custom repositories
URL: https://github.com/Vadyusik01/Nuve-thermostat
Category: Integration
Install Nuve Thermostat, restart Home Assistant
Settings → Devices & services → Add integration → Nuve Thermostat
Manual
Copy the folder so that this file exists:

/config/custom_components/nuve_thermostat/manifest.json
Restart Home Assistant

Add the integration and enter email + password from the mobile app

Serial number is discovered automatically. Production API URL is built-in.

Configuration
Field	Description
Email	Same as in the Nuve / contractor app
Password	Same as in the app
Credentials are stored in the Home Assistant config entry. Do not commit them to git or paste them into public issues.

Entities (typical)
Names depend on area/device registry; serial example 04_126_007226:

climate.nuve_<sn>
select.nuve_<sn>_fan_circulation
switch.nuve_<sn>_backlight
switch.nuve_<sn>_automatic_mode_backlight
number.nuve_<sn>_backlight_hue          # 0–360° in UI → API 0–1
number.nuve_<sn>_backlight_saturation
number.nuve_<sn>_backlight_brightness
number.nuve_<sn>_backlight_shade        # device-specific index; 0 often = white
light.nuve_<sn>_cooling_color           # palette for auto colors
light.nuve_<sn>_heating_color
…
sensor / binary_sensor diagnostics
Fan circulation is a Select entity, not an HVAC mode. Changing it does not change the temperature setpoint.

Automatic backlight priority (0.9.8)
When Automatic mode backlight is on:

Active equipment (bright): aux stage → aux; cooling stage → cool_active; heating stage → heat_active
Fan / recirculation (current_fan_status): overrides idle heat/cool (fan often runs during those modes)
Vacation preset: only while idle (no active heat/cool/aux stage)
Selected HVAC mode: dim cool / heat, then auto, off
Tune colors via the palette light entities (idle vs active).
For manual color tests, turn Automatic mode backlight off first.

Backlight notes
Hue: Home Assistant uses degrees 0–360; the Nuve API expects 0–1. The integration converts both ways.
Brightness / saturation: percent in HA; fractional 0–1 on the wire.
Shade index: not a smooth 0–100 “shadow”. Values near 0 often force white; small integers (about 1–5) change appearance. Prefer hue + saturation + brightness for normal color control.
POST backlight requires sn in the query string and in the JSON body (otherwise API 422 SN is empty).
Example services
# Fan 30 min/hour
action: select.select_option
target:
  entity_id: select.nuve_04_126_007226_fan_circulation
data:
  option: "30 min"
# HVAC cool
action: climate.set_hvac_mode
target:
  entity_id: climate.nuve_04_126_007226
data:
  hvac_mode: cool
# Hue in degrees (integration converts to API 0–1)
action: number.set_value
target:
  entity_id: number.nuve_04_126_007226_backlight_hue
data:
  value: 240
Changelog (0.4.0 → 0.9.8)
Intermediate builds were used for testing and were not all published on GitHub. This section is the consolidated history for a single public jump from 0.4.0 to 0.9.8.

0.4.0 — first public baseline
Config flow: email / password, device discovery via /getSn, contractor metadata
Climate: temperature + modes (API mode ids 1 cool, 2 heat, 3 auto, 5 off)
Fan circulation Select (/device/fan, mode + workingPerHour)
Sensors and binary diagnostics from /device/main-data
Cloud polling; documented HACS/manual install
0.5.x – 0.8.x — expansion (internal / pre-release)
Shared NuveRuntime: one login, shared coordinators (status / fan / backlight)
Backlight entities (switch, numbers, lights) and HSV API hooks
Automatic mode-color palette stored in HA Store
More diagnostic sensors; manifest documentation / issue tracker / codeowners
Staggered poll intervals (status faster than fan/backlight)
0.9.0
401 handling: re-login once and retry (lock to avoid stampedes)
set_mode: single working payload {"sn": sn, "id": mode_num}
Poll intervals: status 30s, fan 60s, backlight 90s
strings.json + English / Russian config flow translations
Climate setup logging reduced to debug
0.9.1 – 0.9.4
Attempts to fix backlight write path; vacation / aux presets (mode ids 4 / 6, best-effort from app analysis)
Richer mode_key (idle vs active cool/heat, fan, vacation)
Debug logging for stage → palette key
Known issue in some trees: backlight POST without query sn → 422 SN is empty
0.9.5
Critical: set_backlight sends sn as query param and JSON body (fixes 422 SN is empty)
ClimateEntityFeature.PRESET_MODE for vacation / aux presets
Fan no longer overrode selected cool/heat before user priority rules were finalized
Clearer default palette hues
0.9.6
Critical: API expects hue 0–1, not degrees. Write path divides by 360 when HA value > 1; read path multiplies fractional hue back to degrees for the UI
0.9.7
Avoid “always white” after hue fix: do not force-scale shadeIndex incorrectly; if saturation is 0 when setting hue, raise saturation so color is visible
0.9.8 (current)
Automatic backlight priority aligned with real use:
Active stages (bright aux / cool / heat)
Fan recirculation over idle heat/cool
Vacation only when idle
Selected HVAC mode (dim idle cool/heat)
Stable cloud climate + fan + backlight stack for daily use
Troubleshooting
Symptom	What to check
422 SN is empty on backlight	Use ≥ 0.9.5 (sn in query + body).
Hue does nothing / only white	Use ≥ 0.9.6 for hue scale; set saturation 100; turn auto colors off while testing.
Auto colors “stuck”	Toggle Automatic mode backlight off/on; optional delete .storage/nuve_thermostat.<entry_id>.mode_backlight.
Fan color never shows during heat/cool	Expected before 0.9.8 if stages idle and fan on—upgrade; confirm current_fan_status in debug mode_key lines.
Integration not found after copy	Path must be /config/custom_components/nuve_thermostat/ (not a nested nuve-0.9.x/ folder only).
Cannot connect	App email/password; HA log for login errors; do not post tokens or passwords.
Enable debug:

logger:
  logs:
    custom_components.nuve_thermostat: debug
Limitations
Depends on Nuve cloud availability and API behavior (may change by account, brand, or server flags).
Not a substitute for professional HVAC service; emergency/diagnostic flags are informational.
Vacation / aux mode ids are best-effort; confirm against your device if presets misbehave.
No local control path (no LAN HTTP API used by this integration).
Shade index semantics are device-specific; prefer hue/saturation/brightness for color.
Privacy and security
The integration talks only to Nuve’s cloud API. Credentials live in the HA config entry. Redact serials, Wi‑Fi names, tokens, and full API payloads before sharing logs. Never publish passwords or Bearer tokens.

Support
Issues: GitHub Issues
Include HA version, integration version (manifest / 0.9.8), app brand, and a redacted log
License / disclaimer
Provided as-is, without warranty. Use at your own risk. All product and company names belong to their respective owners and are used only to describe compatibility.

Maintainer: @Vadyusik01
Repository: github.com/Vadyusik01/Nuve-thermostat