"""Platform for sensor integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .coordinator import RememberTheMilkCoordinator

SERVICE_UPDATE_STATE_TASKS = "update_state_tasks"
SERVICE_SCHEMA_UPDATE_STATE_TASKS = vol.Schema({vol.Required("list_id"): cv.string})
DOMAIN = "remember_the_milk"
_LOGGER = logging.getLogger(__name__)


class TodoItemStatus:
    """Enumeration of the possible status values for a todo item."""

    COMPLETED = "completed"
    NEEDS_ACTION = "needsAction"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Remember the Milk Sensor platform."""
    if discovery_info is None:
        return

    account_name = discovery_info.get("account_name")
    if account_name is None:
        _LOGGER.error("No account name found in discovery_info")
        return

    coordinator: RememberTheMilkCoordinator = hass.data[DOMAIN].get(account_name)
    if coordinator is None:
        _LOGGER.error("No coordinator found for account %s", account_name)
        return

    sensor_entities = [RememberTheMilkSensor(coordinator)]

    async_add_entities(sensor_entities, True)

    async def handle_update_state_tasks(call: ServiceCall) -> None:
        """Handle the service call to update the state of the sensor."""
        list_id = call.data.get("list_id")
        if not list_id:
            _LOGGER.error("Service call missing 'list_id' parameter")
            return

        sensor_entities[0].update_state(list_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_STATE_TASKS,
        handle_update_state_tasks,
        schema=SERVICE_SCHEMA_UPDATE_STATE_TASKS,
    )


class RememberTheMilkSensor(SensorEntity):
    """Representation of a RememberTheMilk sensor."""

    def __init__(self, coordinator: RememberTheMilkCoordinator) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._state = None
        self._attributes = {}
        self._task_list_id = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "RememberTheMilk Sensor"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._attributes

    def update_state(self, task_list_id):
        """Update the task_list_id."""
        self._task_list_id = task_list_id
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        all_task_lists = []
        task_list_items = []

        if self._coordinator.data is None:
            return

        task_lists = await self._coordinator.async_get_task_lists()
        if task_lists is None or self._coordinator.data is None:
            return

        all_task_lists = [
            {"id": task_list.id, "name": task_list.name} for task_list in task_lists
        ]

        task_list_id = self._task_list_id
        task_list_ids = [task_list.id for task_list in self._coordinator.data]
        first_task_list_id = task_list_ids[0] if len(task_list_ids) else None

        if task_list_id not in task_list_ids:
            task_list_id = first_task_list_id

        if task_list_id:
            for task_list in self._coordinator.data:
                if task_list.id != task_list_id:
                    continue
                todo_items = [
                    [
                        taskseries.task.added,
                        {
                            "summary": taskseries.name,
                            "uid": taskseries.id + "_" + taskseries.task.id,
                            "status": TodoItemStatus.COMPLETED
                            if taskseries.task.completed
                            else TodoItemStatus.NEEDS_ACTION,
                            "due": taskseries.task.due,
                            "description": taskseries.notes.note.value
                            if len(list(taskseries.notes)) > 0
                            else "",
                        },
                    ]
                    for taskseries in task_list
                ]
                # Sort by added time
                todo_items.sort(key=lambda x: x[0])
                task_list_items = [item[1] for item in todo_items]

        self._attributes = {"task_lists": all_task_lists, "items": task_list_items}
        self._state = task_list_id

        statistics = self._coordinator.get_statistics()
        self._attributes.update({"statistics": statistics})
