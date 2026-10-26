"""Entity-Relation store tool for maintaining a knowledge graph."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .base import Tool


class EntityStore:
    """In-memory store for entities and their relations.

    Schema:
        Entity: { id, type, properties, relations, created, updated }
        Relation: { from_id, relation_type, to_id, properties }
    """

    def __init__(self):
        self._entities: dict[str, dict[str, Any]] = {}
        self._relations: list[dict[str, Any]] = []

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # --- Entity operations ---

    def create_entity(
        self, entity_type: str, properties: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        entity_id = str(uuid.uuid4())
        now = self._now()
        entity = {
            "id": entity_id,
            "type": entity_type,
            "properties": properties or {},
            "relations": [],
            "created": now,
            "updated": now,
        }
        self._entities[entity_id] = entity
        return entity

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        return self._entities.get(entity_id)

    def update_entity(
        self, entity_id: str, properties: dict[str, Any]
    ) -> dict[str, Any] | None:
        entity = self._entities.get(entity_id)
        if entity is None:
            return None
        entity["properties"].update(properties)
        entity["updated"] = self._now()
        return entity

    def delete_entity(self, entity_id: str) -> bool:
        if entity_id not in self._entities:
            return False
        del self._entities[entity_id]
        self._relations = [
            r
            for r in self._relations
            if r["from_id"] != entity_id and r["to_id"] != entity_id
        ]
        for entity in self._entities.values():
            entity["relations"] = [
                r
                for r in entity["relations"]
                if r["from_id"] != entity_id and r["to_id"] != entity_id
            ]
        return True

    def list_entities(
        self, entity_type: str | None = None
    ) -> list[dict[str, Any]]:
        entities = list(self._entities.values())
        if entity_type:
            entities = [e for e in entities if e["type"] == entity_type]
        return entities

    # --- Relation operations ---

    def add_relation(
        self,
        from_id: str,
        relation_type: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any] | str:
        if from_id not in self._entities:
            return f"Error: entity '{from_id}' not found"
        if to_id not in self._entities:
            return f"Error: entity '{to_id}' not found"

        relation = {
            "from_id": from_id,
            "relation_type": relation_type,
            "to_id": to_id,
            "properties": properties or {},
        }
        self._relations.append(relation)
        self._entities[from_id]["relations"].append(relation)
        self._entities[from_id]["updated"] = self._now()
        return relation

    def get_relations(
        self,
        entity_id: str | None = None,
        relation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        results = self._relations
        if entity_id:
            results = [
                r
                for r in results
                if r["from_id"] == entity_id or r["to_id"] == entity_id
            ]
        if relation_type:
            results = [
                r for r in results if r["relation_type"] == relation_type
            ]
        return results

    def remove_relation(
        self, from_id: str, relation_type: str, to_id: str
    ) -> bool:
        before = len(self._relations)
        self._relations = [
            r
            for r in self._relations
            if not (
                r["from_id"] == from_id
                and r["relation_type"] == relation_type
                and r["to_id"] == to_id
            )
        ]
        if from_id in self._entities:
            self._entities[from_id]["relations"] = [
                r
                for r in self._entities[from_id]["relations"]
                if not (
                    r["relation_type"] == relation_type and r["to_id"] == to_id
                )
            ]
            self._entities[from_id]["updated"] = self._now()
        return len(self._relations) < before


class EntityStoreTool(Tool):
    """Tool for agents to manage an entity-relation knowledge graph.

    Supports creating, reading, updating, and deleting entities
    and the relations between them.
    """

    def __init__(self, store: EntityStore | None = None):
        self.store = store or EntityStore()
        super().__init__(
            name="entity_store",
            description=(
                "Manage an entity-relation knowledge graph. "
                "Create entities with typed properties and connect "
                "them via named relations. Useful for tracking people, "
                "concepts, tasks, and their relationships."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "create_entity",
                            "get_entity",
                            "update_entity",
                            "delete_entity",
                            "list_entities",
                            "add_relation",
                            "get_relations",
                            "remove_relation",
                        ],
                        "description": "The operation to perform",
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "Entity ID (for get/update/delete/relations)",
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "Entity type (for create/list, e.g. 'person', 'task')",
                    },
                    "properties": {
                        "type": "object",
                        "description": "Key-value properties for the entity or relation",
                    },
                    "from_id": {
                        "type": "string",
                        "description": "Source entity ID (for relation operations)",
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Relation type (e.g. 'depends_on', 'created_by')",
                    },
                    "to_id": {
                        "type": "string",
                        "description": "Target entity ID (for relation operations)",
                    },
                },
                "required": ["operation"],
            },
        )

    async def execute(self, operation: str, **kwargs) -> str:
        handlers = {
            "create_entity": self._create_entity,
            "get_entity": self._get_entity,
            "update_entity": self._update_entity,
            "delete_entity": self._delete_entity,
            "list_entities": self._list_entities,
            "add_relation": self._add_relation,
            "get_relations": self._get_relations,
            "remove_relation": self._remove_relation,
        }
        handler = handlers.get(operation)
        if handler is None:
            return f"Error: unknown operation '{operation}'"
        return handler(**kwargs)

    def _create_entity(
        self,
        entity_type: str = "",
        properties: dict[str, Any] | None = None,
        **_,
    ) -> str:
        if not entity_type:
            return "Error: entity_type is required"
        entity = self.store.create_entity(entity_type, properties)
        return json.dumps(entity, indent=2)

    def _get_entity(self, entity_id: str = "", **_) -> str:
        if not entity_id:
            return "Error: entity_id is required"
        entity = self.store.get_entity(entity_id)
        if entity is None:
            return f"Error: entity '{entity_id}' not found"
        return json.dumps(entity, indent=2)

    def _update_entity(
        self,
        entity_id: str = "",
        properties: dict[str, Any] | None = None,
        **_,
    ) -> str:
        if not entity_id:
            return "Error: entity_id is required"
        if not properties:
            return "Error: properties are required for update"
        entity = self.store.update_entity(entity_id, properties)
        if entity is None:
            return f"Error: entity '{entity_id}' not found"
        return json.dumps(entity, indent=2)

    def _delete_entity(self, entity_id: str = "", **_) -> str:
        if not entity_id:
            return "Error: entity_id is required"
        if self.store.delete_entity(entity_id):
            return f"Entity '{entity_id}' deleted"
        return f"Error: entity '{entity_id}' not found"

    def _list_entities(self, entity_type: str = "", **_) -> str:
        entities = self.store.list_entities(entity_type or None)
        if not entities:
            return "No entities found"
        return json.dumps(entities, indent=2)

    def _add_relation(
        self,
        from_id: str = "",
        relation_type: str = "",
        to_id: str = "",
        properties: dict[str, Any] | None = None,
        **_,
    ) -> str:
        if not all([from_id, relation_type, to_id]):
            return "Error: from_id, relation_type, and to_id are required"
        result = self.store.add_relation(
            from_id, relation_type, to_id, properties
        )
        if isinstance(result, str):
            return result
        return json.dumps(result, indent=2)

    def _get_relations(
        self,
        entity_id: str = "",
        relation_type: str = "",
        **_,
    ) -> str:
        relations = self.store.get_relations(
            entity_id or None, relation_type or None
        )
        if not relations:
            return "No relations found"
        return json.dumps(relations, indent=2)

    def _remove_relation(
        self,
        from_id: str = "",
        relation_type: str = "",
        to_id: str = "",
        **_,
    ) -> str:
        if not all([from_id, relation_type, to_id]):
            return "Error: from_id, relation_type, and to_id are required"
        if self.store.remove_relation(from_id, relation_type, to_id):
            return f"Relation '{from_id} --{relation_type}--> {to_id}' removed"
        return "Error: relation not found"
