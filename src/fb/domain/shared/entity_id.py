from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntityId:
    value: uuid.UUID

    @classmethod
    def generate(cls) -> EntityId:
        return cls(value=uuid.uuid4())

    @classmethod
    def from_str(cls, id_str: str) -> EntityId:
        return cls(value=uuid.UUID(id_str))

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EntityId):
            return self.value == other.value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)
