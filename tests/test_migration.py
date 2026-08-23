"""Tests for entity-registry migrations."""

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "clever_api"))

from clever.migration import migrate_entity_unique_ids


@dataclass
class FakeEntry:
    entity_id: str
    domain: str
    unique_id: str
    config_entry_id: str


class FakeRegistry:
    def __init__(self, entries: list[FakeEntry]) -> None:
        self.entries = {entry.entity_id: entry for entry in entries}

    def async_get_entity_id(
        self, domain: str, platform: str, unique_id: str
    ) -> str | None:
        del platform
        return next(
            (
                entry.entity_id
                for entry in self.entries.values()
                if entry.domain == domain and entry.unique_id == unique_id
            ),
            None,
        )

    def async_get(self, entity_id: str) -> FakeEntry | None:
        return self.entries.get(entity_id)

    def async_remove(self, entity_id: str) -> None:
        del self.entries[entity_id]

    def async_update_entity(self, entity_id: str, *, new_unique_id: str) -> None:
        self.entries[entity_id].unique_id = new_unique_id


class MigrationTests(unittest.TestCase):
    def test_scoped_duplicate_is_removed_before_legacy_entry_is_updated(self) -> None:
        legacy = FakeEntry("sensor.energy_this_month", "sensor", "kwh_this_month", "a")
        duplicate = FakeEntry(
            "sensor.energy_this_month_2", "sensor", "customer_kwh_this_month", "a"
        )
        registry = FakeRegistry([legacy, duplicate])

        migrate_entity_unique_ids(
            registry,
            [legacy, duplicate],
            "a",
            "clever_api",
            {("sensor", "kwh_this_month"): "customer_kwh_this_month"},
        )

        self.assertNotIn(duplicate.entity_id, registry.entries)
        self.assertEqual(
            registry.entries[legacy.entity_id].unique_id,
            "customer_kwh_this_month",
        )

    def test_scoped_collision_from_another_config_entry_is_untouched(self) -> None:
        legacy = FakeEntry("sensor.energy_this_month", "sensor", "kwh_this_month", "a")
        collision = FakeEntry(
            "sensor.energy_this_month_2", "sensor", "customer_kwh_this_month", "b"
        )
        registry = FakeRegistry([legacy, collision])

        migrate_entity_unique_ids(
            registry,
            [legacy],
            "a",
            "clever_api",
            {("sensor", "kwh_this_month"): "customer_kwh_this_month"},
        )

        self.assertEqual(registry.entries[legacy.entity_id].unique_id, "kwh_this_month")
        self.assertIs(registry.entries[collision.entity_id], collision)
