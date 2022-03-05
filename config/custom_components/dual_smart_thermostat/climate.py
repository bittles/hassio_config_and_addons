"""Adds support for generic thermostat units."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_PRESET_MODE,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT_COOL,
    PRESET_AWAY,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OPEN,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity


from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

DEFAULT_TOLERANCE = 0.3
DEFAULT_NAME = "Dual Smart"
DEFAULT_MAX_FLOOR_TEMP = 28.0

CONF_HEATER = "heater"
CONF_COOLER = "cooler"
CONF_SENSOR = "target_sensor"
CONF_FLOOR_SENSOR = "floor_sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_MAX_FLOOR_TEMP = "max_floor_temp"
CONF_TARGET_TEMP = "target_temp"
CONF_TARGET_TEMP_HIGH = "target_temp_high"
CONF_TARGET_TEMP_LOW = "target_temp_low"
CONF_AC_MODE = "ac_mode"
CONF_MIN_DUR = "min_cycle_duration"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_KEEP_ALIVE = "keep_alive"
CONF_INITIAL_HVAC_MODE = "initial_hvac_mode"
CONF_AWAY_TEMP = "away_temp"
CONF_PRECISION = "precision"
CONF_OPENINGS = "openings"
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HEATER): cv.entity_id,
        vol.Optional(CONF_COOLER): cv.entity_id,
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_FLOOR_SENSOR): cv.entity_id,
        vol.Optional(CONF_AC_MODE): cv.boolean,
        vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MIN_DUR): vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_FLOOR_TEMP, default=DEFAULT_MAX_FLOOR_TEMP): vol.Coerce(
            float
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
        vol.Optional(CONF_TARGET_TEMP_HIGH): vol.Coerce(float),
        vol.Optional(CONF_TARGET_TEMP_LOW): vol.Coerce(float),
        vol.Optional(CONF_KEEP_ALIVE): vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(CONF_INITIAL_HVAC_MODE): vol.In(
            [HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF, HVAC_MODE_HEAT_COOL]
        ),
        vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_OPENINGS): [cv.entity_id],
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the smart dual thermostat platform."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    name = config.get(CONF_NAME)
    heater_entity_id = config.get(CONF_HEATER)
    cooler_entity_id = config.get(CONF_COOLER)
    sensor_entity_id = config.get(CONF_SENSOR)
    sensor_floor_entity_id = config.get(CONF_FLOOR_SENSOR)
    opening_entities = config.get(CONF_OPENINGS)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    max_floor_temp = config.get(CONF_MAX_FLOOR_TEMP)
    target_temp = config.get(CONF_TARGET_TEMP)
    target_temp_high = config.get(CONF_TARGET_TEMP_HIGH)
    target_temp_low = config.get(CONF_TARGET_TEMP_LOW)
    ac_mode = config.get(CONF_AC_MODE)
    min_cycle_duration = config.get(CONF_MIN_DUR)
    cold_tolerance = config.get(CONF_COLD_TOLERANCE)
    hot_tolerance = config.get(CONF_HOT_TOLERANCE)
    keep_alive = config.get(CONF_KEEP_ALIVE)
    initial_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)
    away_temp = config.get(CONF_AWAY_TEMP)
    precision = config.get(CONF_PRECISION)
    unit = hass.config.units.temperature_unit

    async_add_entities(
        [
            DualSmartThermostat(
                name,
                heater_entity_id,
                cooler_entity_id,
                sensor_entity_id,
                sensor_floor_entity_id,
                opening_entities,
                min_temp,
                max_temp,
                max_floor_temp,
                target_temp,
                target_temp_high,
                target_temp_low,
                ac_mode,
                min_cycle_duration,
                cold_tolerance,
                hot_tolerance,
                keep_alive,
                initial_hvac_mode,
                away_temp,
                precision,
                unit,
            )
        ]
    )


class DualSmartThermostat(ClimateEntity, RestoreEntity):
    """Representation of a Generic Thermostat device."""

    def __init__(
        self,
        name,
        heater_entity_id,
        cooler_entity_id,
        sensor_entity_id,
        sensor_floor_entity_id,
        opening_entities,
        min_temp,
        max_temp,
        max_floor_temp,
        target_temp,
        target_temp_high,
        target_temp_low,
        ac_mode,
        min_cycle_duration,
        cold_tolerance,
        hot_tolerance,
        keep_alive,
        initial_hvac_mode,
        away_temp,
        precision,
        unit,
    ):
        """Initialize the thermostat."""
        self._name = name
        self.heater_entity_id = heater_entity_id
        self.cooler_entity_id = cooler_entity_id
        self.sensor_entity_id = sensor_entity_id
        self.sensor_floor_entity_id = sensor_floor_entity_id
        self.opening_entities = opening_entities
        self.ac_mode = ac_mode
        self.min_cycle_duration = min_cycle_duration
        self._cold_tolerance = cold_tolerance
        self._hot_tolerance = hot_tolerance
        self._keep_alive = keep_alive
        self._hvac_mode = initial_hvac_mode
        self._saved_target_temp = target_temp or away_temp
        self._saved_target_temp_high = target_temp_high
        self._saved_target_temp_low = target_temp_low
        self._temp_precision = precision
        if self.heater_entity_id and self.cooler_entity_id:
            self._hvac_list = [
                HVAC_MODE_OFF,
                HVAC_MODE_HEAT_COOL,
            ]
        elif self.ac_mode:
            self._hvac_list = [HVAC_MODE_COOL, HVAC_MODE_OFF]
        else:
            self._hvac_list = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
        self._active = False
        self._cur_temp = None
        self._cur_floor_temp = None
        self._temp_lock = asyncio.Lock()
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._max_floor_temp = max_floor_temp
        self._target_temp = target_temp
        self._target_temp_high = target_temp_high
        self._target_temp_low = target_temp_low
        self._unit = unit
        self._support_flags = (
            SUPPORT_TARGET_TEMPERATURE_RANGE if cooler_entity_id else SUPPORT_FLAGS
        )
        if away_temp:
            self._support_flags = (
                SUPPORT_TARGET_TEMPERATURE_RANGE if cooler_entity_id else SUPPORT_FLAGS
            ) | SUPPORT_PRESET_MODE
        self._away_temp = away_temp
        self._is_away = False

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.sensor_entity_id],
                self._async_sensor_changed,
            )
        )

        if self.opening_entities and len(self.opening_entities):
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    self.opening_entities,
                    self._async_opening_changed,
                )
            )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.heater_entity_id],
                self._async_switch_changed,
            )
        )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.cooler_entity_id],
                self._async_cooler_changed,
            )
        )

        if self.sensor_floor_entity_id is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self.sensor_floor_entity_id],
                    self._async_sensor_floor_changed,
                )
            )

        if self._keep_alive:
            if self.cooler_entity_id:
                self.async_on_remove(
                    async_track_time_interval(
                        self.hass, self._async_control_heat_cool, self._keep_alive
                    )
                )
            else:
                self.async_on_remove(
                    async_track_time_interval(
                        self.hass, self._async_control_heating, self._keep_alive
                    )
                )

        @callback
        def _async_startup(event):
            """Init on startup."""
            sensor_state = self.hass.states.get(self.sensor_entity_id)
            if self.sensor_floor_entity_id:
                floor_sensor_state = self.hass.states.get(self.sensor_floor_entity_id)
            else:
                floor_sensor_state = None

            if sensor_state and sensor_state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                self._async_update_temp(sensor_state)

            if floor_sensor_state and floor_sensor_state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                self._async_update_floor_temp(floor_sensor_state)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        # Check If we have an old state
        old_state = await self.async_get_last_state()
        if old_state is not None:
            # If we have no initial temperature, restore
            if self._target_temp is None:
                # If we have a previously saved temperature
                if old_state.attributes.get(ATTR_TEMPERATURE) is None:
                    if self.ac_mode:
                        self._target_temp = self.max_temp
                    else:
                        self._target_temp = self.min_temp
                    _LOGGER.warning(
                        "Undefined target temperature, falling back to %s",
                        self._target_temp,
                    )
                else:
                    self._target_temp = float(old_state.attributes[ATTR_TEMPERATURE])
            if old_state.attributes.get(ATTR_PRESET_MODE) == PRESET_AWAY:
                self._is_away = True
            if not self._hvac_mode and old_state.state:
                self._hvac_mode = old_state.state

        else:
            # No previous state, try and restore defaults
            if self._target_temp is None:
                if self.ac_mode:
                    self._target_temp = self.max_temp
                else:
                    self._target_temp = self.min_temp
            _LOGGER.warning(
                "No previously saved temperature, setting to %s", self._target_temp
            )

        # Set default state to off
        if not self._hvac_mode:
            self._hvac_mode = HVAC_MODE_OFF

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def precision(self):
        """Return the precision of the system."""
        if self._temp_precision is not None:
            return self._temp_precision
        return super().precision
    
    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        # Since this integration does not yet have a step size parameter
        # we have to re-use the precision as the step size for now.
        return self.precision
    
    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._cur_temp

    @property
    def current_floor_temperature(self):
        """Return the sensor temperature."""
        return self._cur_floor_temp

    @property
    def hvac_mode(self):
        """Return current operation."""
        return self._hvac_mode

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._hvac_mode == HVAC_MODE_OFF:
            return CURRENT_HVAC_OFF
        if not self._is_device_active:
            return CURRENT_HVAC_IDLE
        if self.ac_mode:
            return CURRENT_HVAC_COOL
        if self._is_cooler_active:
            return CURRENT_HVAC_COOL
        return CURRENT_HVAC_HEAT

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature."""
        return self._target_temp_high

    @property
    def target_temperature_low(self):
        """Return the  lower bound temperature."""
        return self._target_temp_low

    @property
    def floor_temperature_limit(self):
        """Return the  lower bound temperature."""
        return self._max_floor_temp

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._hvac_list

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        return PRESET_AWAY if self._is_away else PRESET_NONE

    @property
    def preset_modes(self):
        """Return a list of available preset modes or PRESET_NONE if _away_temp is undefined."""
        return [PRESET_NONE, PRESET_AWAY] if self._away_temp else PRESET_NONE

    async def async_call_mode(self, hvac_mode):
        """Call climate mode based on current mode"""
        _LOGGER.info("Setting hvac mode: %s", hvac_mode)
        if hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
            await self._async_control_heating(force=True)
        elif hvac_mode == HVAC_MODE_COOL:
            self._hvac_mode = HVAC_MODE_COOL
            await self._async_control_heating(force=True)
        elif hvac_mode == HVAC_MODE_HEAT_COOL:
            self._hvac_mode = HVAC_MODE_HEAT_COOL
            await self._async_control_heat_cool(force=True)
        elif hvac_mode == HVAC_MODE_OFF:
            self._hvac_mode = HVAC_MODE_OFF
            if self._is_device_active:
                await self._async_heater_turn_off()
                if self.cooler_entity_id:
                    await self._async_cooler_turn_off()
        else:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
        return

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        await self.async_call_mode(hvac_mode)
        # Ensure we update the current operation after changing the mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp_low = kwargs.get("target_temp_low")
        temp_high = kwargs.get("target_temp_high")
        temp = kwargs.get("target_temp") or kwargs.get("temperature")

        if temp is None and temp_high is None and temp_low is None:
            return
        if temp is not None:
            self._target_temp = temp
        if temp_high is not None:
            self._target_temp_high = temp_high
        if temp_low is not None:
            self._target_temp_low = temp_low

        await self.async_call_mode(self._hvac_mode)
        self.async_write_ha_state()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._min_temp is not None:
            return self._min_temp

        # get default temp from super class
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._max_temp is not None:
            return self._max_temp

        # Get default temp from super class
        return super().max_temp

    async def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        new_state = event.data.get("new_state")
        _LOGGER.info("Sensor change: %s", new_state)
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        self._async_update_temp(new_state)
        await self._async_trigger_control()
        self.async_write_ha_state()

    async def _async_sensor_floor_changed(self, event):
        """Handle floor temperature changes."""
        new_state = event.data.get("new_state")
        _LOGGER.info("Sensor floor change: %s", new_state)
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        self._async_update_floor_temp(new_state)
        await self._async_trigger_control()
        self.async_write_ha_state()

    async def _async_opening_changed(self, event):
        """Handle opening changes."""
        new_state = event.data.get("new_state")
        _LOGGER.info("Opening changed: %s", new_state)
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return

        await self._async_trigger_control()
        self.async_write_ha_state()

    async def _async_trigger_control(self):
        if self.cooler_entity_id is not None:
            await self._async_control_heat_cool(force=True)
        else:
            await self._async_control_heating(force=True)

    @callback
    def _async_switch_changed(self, event):
        """Handle heater switch state changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        self.async_write_ha_state()

    callback

    def _async_cooler_changed(self, event):
        """Handle cooler switch state changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        self.async_write_ha_state()

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._cur_temp = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    @callback
    def _async_update_floor_temp(self, state):
        """Update ermostat with latest floor temp state from floor temp sensor."""
        try:
            self._cur_floor_temp = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from floor temp sensor: %s", ex)

    async def _async_control_heating(self, time=None, force=False):
        """Check if we need to turn heating on or off."""
        async with self._temp_lock:
            if not self._active and None not in (self._cur_temp, self._target_temp):
                self._active = True
                _LOGGER.info(
                    "Obtained current and target temperature. "
                    "Dual smart thermostat active. %s, %s",
                    self._cur_temp,
                    self._target_temp,
                )

            if not self._active or self._hvac_mode == HVAC_MODE_OFF:
                return

            if not force and time is None:
                # If the `force` argument is True, we
                # ignore `min_cycle_duration`.
                # If the `time` argument is not none, we were invoked for
                # keep-alive purposes, and `min_cycle_duration` is irrelevant.
                if self.min_cycle_duration:
                    if self._is_device_active:
                        current_state = STATE_ON
                    else:
                        current_state = HVAC_MODE_OFF
                    long_enough = condition.state(
                        self.hass,
                        self.heater_entity_id,
                        current_state,
                        self.min_cycle_duration,
                    )
                    if not long_enough:
                        return

            too_cold = self._target_temp >= self._cur_temp + self._cold_tolerance
            too_hot = self._cur_temp >= self._target_temp + self._hot_tolerance

            if self._is_device_active:
                if (
                    (self.ac_mode and too_cold)
                    or (not self.ac_mode and too_hot)
                    or (not self.ac_mode and self._is_floor_hot)
                    or self._is_opening_open
                ):
                    _LOGGER.info("Turning off heater %s", self.heater_entity_id)
                    await self._async_heater_turn_off()
                elif (
                    time is not None
                    and not self._is_opening_open
                    and not self._is_floor_hot
                ):
                    # The time argument is passed only in keep-alive case
                    _LOGGER.info(
                        "Keep-alive - Turning on heater (from active) %s",
                        self.heater_entity_id,
                    )
                    await self._async_heater_turn_on()
            else:
                if (self.ac_mode and too_hot and not self._is_opening_open) or (
                    not self.ac_mode
                    and too_cold
                    and not self._is_opening_open
                    and not self._is_floor_hot
                ):
                    _LOGGER.info(
                        "Turning on heater (from inactive) %s", self.heater_entity_id
                    )
                    await self._async_heater_turn_on()
                elif time is not None or self._is_opening_open or self._is_floor_hot:
                    # The time argument is passed only in keep-alive case
                    _LOGGER.info(
                        "Keep-alive - Turning off heater %s", self.heater_entity_id
                    )
                    await self._async_heater_turn_off()

    async def _async_control_heat_cool(self, time=None, force=False):
        """Check if we need to turn heating on or off."""
        async with self._temp_lock:
            if not self._active and None not in (
                self._cur_temp,
                self._target_temp_high,
                self._target_temp_low,
            ):
                self._active = True
            if not self._active or self._hvac_mode == HVAC_MODE_OFF:
                return

            if not force and time is None:
                # If the `force` argument is True, we
                # ignore `min_cycle_duration`.
                # If the `time` argument is not none, we were invoked for
                # keep-alive purposes, and `min_cycle_duration` is irrelevant.
                if self.min_cycle_duration:
                    if self._is_device_active:
                        current_state = STATE_ON
                    else:
                        current_state = HVAC_MODE_OFF
                    long_enough = condition.state(
                        self.hass,
                        self.heater_entity_id,
                        self.cooler_entity_id,
                        current_state,
                        self.min_cycle_duration,
                    )
                    if not long_enough:
                        return

            too_cold = self._target_temp_low >= self._cur_temp + self._cold_tolerance
            too_hot = self._cur_temp >= self._target_temp_high + self._hot_tolerance

            if self._is_opening_open:
                await self._async_heater_turn_off()
                await self._async_cooler_turn_off()
            elif self._is_floor_hot:
                await self._async_heater_turn_off()
            else:
                await self.async_heater_cooler_toggle(too_cold, too_hot)

            if time is not None:
                # The time argument is passed only in keep-alive case
                _LOGGER.info(
                    "Keep-alive - Toggling on heater cooler %s, %s",
                    self.heater_entity_id,
                    self.cooler_entity_id,
                )
                await self.async_heater_cooler_toggle(too_cold, too_hot)

    async def async_heater_cooler_toggle(self, too_cold, too_hot):
        """Toggle heater cooler based on device state"""
        if too_cold:
            if not self._is_opening_open:
                await self._async_heater_turn_on()
            await self._async_cooler_turn_off()
        elif too_hot:
            if not self._is_opening_open:
                await self._async_cooler_turn_on()
            await self._async_heater_turn_off()
        else:
            await self._async_heater_turn_off()
            await self._async_cooler_turn_off()

    @property
    def _is_opening_open(self):
        """If the binary opening is currently open."""
        _is_open = False
        if self.opening_entities:
            for opening in self.opening_entities:

                if self.hass.states.is_state(
                    opening, STATE_OPEN
                ) or self.hass.states.is_state(opening, STATE_ON):
                    _is_open = True

            return _is_open
        else:
            return False

    @property
    def _is_floor_hot(self):
        """If the floor temp is above limit."""
        if (
            (self.sensor_floor_entity_id is not None)
            and (self._max_floor_temp is not None)
            and (self._cur_floor_temp is not None)
        ):
            if self._cur_floor_temp >= self._max_floor_temp:
                return True

            return False
        else:
            return False

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        return self.hass.states.is_state(self.heater_entity_id, STATE_ON) or (
            self.cooler_entity_id
            and self.hass.states.is_state(self.cooler_entity_id, STATE_ON)
        )

    @property
    def _is_cooler_active(self):
        """If the toggleable cooler device is currently active."""
        if self.cooler_entity_id and self.hass.states.is_state(
            self.cooler_entity_id, STATE_ON
        ):
            return True
        else:
            return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    async def _async_heater_turn_on(self):
        """Turn heater toggleable device on."""
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_ON, data, context=self._context
        )

    async def _async_heater_turn_off(self):
        """Turn heater toggleable device off."""
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_OFF, data, context=self._context
        )

    async def _async_cooler_turn_on(self):
        """Turn cooler toggleable device on."""
        if not self._is_cooler_active:
            data = {ATTR_ENTITY_ID: self.cooler_entity_id}
            await self.hass.services.async_call(
                HA_DOMAIN, SERVICE_TURN_ON, data, context=self._context
            )

    async def _async_cooler_turn_off(self):
        """Turn cooler toggleable device off."""
        if self._is_cooler_active:
            data = {ATTR_ENTITY_ID: self.cooler_entity_id}
            await self.hass.services.async_call(
                HA_DOMAIN, SERVICE_TURN_OFF, data, context=self._context
            )

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode."""
        if preset_mode == PRESET_AWAY and not self._is_away:
            self._is_away = True
            self._saved_target_temp = self._target_temp
            self._target_temp = self._away_temp
            await self._async_control_heating(force=True)
        elif preset_mode == PRESET_NONE and self._is_away:
            self._is_away = False
            self._target_temp = self._saved_target_temp
            await self._async_control_heating(force=True)

        self.async_write_ha_state()
