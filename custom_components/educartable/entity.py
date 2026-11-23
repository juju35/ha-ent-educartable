"""Base entity of the Educartable integration: one device for the family account, one per pupil."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EducartableCoordinator


def account_device(coordinator: EducartableCoordinator) -> DeviceInfo:
    entry = coordinator.config_entry
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="EDUMOOV",
        model="Educartable",
        entry_type=DeviceEntryType.SERVICE,
    )


def pupil_device(coordinator: EducartableCoordinator, pupil: dict) -> DeviceInfo:
    entry = coordinator.config_entry
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{pupil['id']}")},
        name=pupil["name"],
        manufacturer="EDUMOOV",
        model="Educartable",
        entry_type=DeviceEntryType.SERVICE,
        via_device=(DOMAIN, entry.entry_id),
    )


class EducartableEntity(CoordinatorEntity[EducartableCoordinator]):
    """An entity attached to the family-account device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EducartableCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = account_device(coordinator)

    @property
    def base_attributes(self) -> dict:
        data = self.coordinator.data
        return {
            "config_entry_id": self.coordinator.config_entry.entry_id,
            "stale": list(data.stale) if data else [],
        }


class EducartablePupilEntity(CoordinatorEntity[EducartableCoordinator]):
    """An entity attached to a pupil's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EducartableCoordinator, pupil: dict, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._pupil_id = pupil["id"]
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{pupil['id']}_{key}"
        self._attr_device_info = pupil_device(coordinator, pupil)
