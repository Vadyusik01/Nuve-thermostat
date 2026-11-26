# Nuve Thermostat 0.9.9

## Entity categories (configuration vs controls)

Per-mode backlight colour entities are colour *presets* (settings), not real
lights. They are implemented on the light platform only because Home
Assistant's colour picker exists there — but as plain lights they polluted
the Lighting sections, area light groups and the device page Controls list.

- Mode colour entities (`*_color`), backlight numbers (hue / brightness /
  shade) and the "Automatic mode backlight" switch are now marked
  `entity_category = config`: on the device page they live under
  **Configuration**, and the auto-generated dashboard skips them.
- Real controls are unchanged: climate, the Backlight on/off switch,
  fan circulation select, sensors.

Note: the domain stays `light` (needed for the colour picker), so an
area-wide "turn off all lights" can still reach the colour presets.
Exclude them from voice assistants if that matters.
