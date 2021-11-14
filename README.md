# hassio_config_and_addons
Personal Home Assistant Setup

## System
- Raspberry Pi4 rev 1.2
  - running at 1800 mhz
  - booting from external 500 gb SSD
- Aeotec Zstick 5

### More unique/creative entities/automations possibly worth looking at:
- Climates using generic thermostat platform
  - Have two zone, one air handler hvac.  Master bedroom downstairs.  Downstairs zone 1 nest thermostat directly across hall from stairs to upstairs.  Vent in stairwall on ceiling connected to zone 2 thermostat blows air directly down the stairs, causing the thermostat to read much colder than it is in the summer, and much hotter than it is in the winter.
    - Shelly H&T on the headboard in the master bedroom to monitor temperature with ShellyForHASS component from hacs.  Have the shelly configured to send fahrenheit which causes problems, but HASS rounds the celsius temperature first, then converts it to fahrenheit.  Causing some loss of resolution.  
    - One template sensor reads shelly temp, converts to fahreheit if needed, otherwise reports the reported fahrenheit temperature.  Also triggers automation to record current timestamp in input date/time entity.
    - Ocassionally if shelly rebooted, entity would read 999 or -200 some.  Filter sensor to eliminate those, then another template sensor built to show the date/time entity in its attributes for the frontend.
    - Generic thermostats use this sensor as the current temp, if they become active then triggers an automation to the nest thermostat to make the target temp +/- 3 degrees (if heating/cooling) over the current temp read by the nest.  Ensures the nest always becomes active as there's some rounding in the nest integration and there's a tolerance built into the nest itself
    - Want to combine the AC and Heater entities into a single thermostat, on the to-do list
- Outdoor outlet with ESPhome for the shower
  - Plugged into the outlet is a normally closed solenoid valve (only open if power is received)
  - On either side of that are adapters to convert indoor plumbing pipe to GHT (hose size pipe) and then back to indoor plumbing so it's snug and doesn't leak (could only find solenoid valves made for GHT pipes)
  - All this sites right behind the shower head.  Leave the knob in the shower to the temperature I want it, and can turn it on/off at will.  Of course the bathroom exhaust fan turns on with it.  Master bath shower takes a good 3-4 minutes to heat up.  What started as a dumb what if idea is extremely convenient.
- Presence detection with 3 methods for redundancy
  - Input booleans for each person bridged to homekit.  Homekit geofence triggers these on/off.  Input booleans trigger mqtt publishing to some mqtt device tracker entities to be able to add to the person
  - IP monitoring device tracker
  - ARP cache monitoring with hacs iPhone Device Tracker integration device tracker
- Notifications from Arlo Pro 3s pulled in with hacs aarlo component
  - Notifications include both still images and clips attachments, along with timestamps and object detection (from Arlo itself)
- Whole home house audio using onkyo component, seperate installed raspotify, shairplay-sync, and owntone (aka forked daapd, to send audio to airplay on onkyo)
  - Zone 2 of the onkyo goes to a 'dumb' speaker selector in order to split the signal into 3 seperate channels
  - Global cache GC100 takes a positive wire from each of these before sending them onto the speakers themselves so that they can be controlled with HASS.  Have the back deck speaker, master bath speaker, and a front porch speaker
  - Combining the zone 2 switch, with GC100 relay switches, with the owntone switches so that one switch turns on airplay output to the back deck, etc.  Went a step further and made media players as well in order to make the airplay outputs directly selectable from iPhone's builtin interface
- Some zwave contact sensors on my dog's food containers to trigger automations so we know he's been fed already (black lab who will eat himself to death if he could)
- Auto on/off under cabinet lighting in the kitchen with zwave kitchen light switch and yeelink strips
- Water sensor in dog's bowl to tell if empty or not.  Works fine but once submerged for too long the sensor reads dry when it's still under water.  Need to find a way around that.
