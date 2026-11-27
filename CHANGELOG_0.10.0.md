# Nuve Thermostat 0.10.0

## What is the equipment doing + built-in runtime counters

Until now the climate entity only showed the *selected* mode, and its
`hvac_action` ignored the aux stage and fan-only circulation — periodic
ventilation looked like "idle". Runtime totals lived in an external
sensor package. Both are now built in.

### Current activity
- New enum sensor **Current activity**: `heating`, `cooling`, `aux_heat`,
  `fan` (fan circulation with no stage running), `idle`, `off` — derived
  from the real stage/fan fields with the same priority as the automatic
  backlight (aux → cooling → heating → fan → idle/off).
- `climate.hvac_action` uses the same derivation: aux reports as
  `heating`, fan-only circulation now reports as `fan` instead of `idle`.

### Runtime counters (persisted in HA storage, survive restarts)
For each of heating / cooling / auxiliary heating / fan circulation:
- **`<X> runtime total`** — accumulated hours, `total_increasing`.
- **`<X> runtime today`** — hours since local midnight.

Counting follows the 30 s status poll; each interval is credited to the
channels active in it (capped at 180 s per interval so stalls/restarts
cannot inflate totals). Fan circulation counts only while no stage is
running, so fan hours are not double-counted inside heating/cooling.
Counters start from zero on first run of 0.10.0 — no history backfill.

### Current activity polish
- The sensor icon is dynamic and equipment-agnostic — it follows the
  activity (fire / radiator / snowflake / fan / power-sleep / power)
  instead of naming a specific equipment type.
- Activity states are translated (English / Russian), so cards show
  "Auxiliary heating" / "Дополнительный нагрев" instead of the raw
  `aux_heat` code.
- The sensor carries the raw stage/fan fields as attributes
  (`current_heating_stage`, `current_cooling_stage`, `current_aux_stage`,
  `current_fan_status`), so it is visible *why* it reports its state.

### Fixes
- Backlight hue / brightness / saturation are rounded to 0.1 after the
  0–1 rescale — the hue number no longer shows long binary floats such
  as 49.060773480663.
