# Nuve Thermostat 0.9.8

## Automatic backlight priority (user rules)

1. **Active stages** (bright): aux → cool_active → heat_active  
2. **Fan / recirculation** — overrides idle heat/cool (fan often runs during those modes)  
3. **Vacation** — only when idle (no active stage; fan already handled above)  
4. **Selected HVAC**: cool / heat (dim), auto, off  

Idle heat/cool stay dimmer; active compressor/heat stage uses *_active (brighter).
