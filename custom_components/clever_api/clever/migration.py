"""Entity-registry migration helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def migrate_entity_unique_ids(
    registry: Any,
    registry_entries: Iterable[Any],
    config_entry_id: str,
    platform: str,
    migrations: Mapping[tuple[str, str], str],
) -> None:
    """Move scoped unique IDs to legacy entries while retaining entity IDs."""
    for registry_entry in registry_entries:
        new_unique_id = migrations.get(
            (registry_entry.domain, registry_entry.unique_id)
        )
        if new_unique_id is None:
            continue

        duplicate_entity_id = registry.async_get_entity_id(
            registry_entry.domain, platform, new_unique_id
        )
        if duplicate_entity_id == registry_entry.entity_id:
            continue
        if duplicate_entity_id is not None:
            duplicate_entry = registry.async_get(duplicate_entity_id)
            if (
                duplicate_entry is None
                or duplicate_entry.config_entry_id != config_entry_id
            ):
                # Never remove or take over an entity owned by another config entry.
                continue
            registry.async_remove(duplicate_entity_id)

        registry.async_update_entity(
            registry_entry.entity_id, new_unique_id=new_unique_id
        )
