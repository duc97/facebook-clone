from __future__ import annotations

import pytest
from uuid import UUID

from fb.application.shared.use_case import UseCase
from fb.domain.shared.entity_id import EntityId


class TestUseCaseBase:
    def test_cannot_instantiate_abstract(self) -> None:
        """UseCase is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            UseCase()  # type: ignore[abstract]

    async def test_concrete_subclass_works(self) -> None:
        """Concrete UseCase subclass can be instantiated and used."""
        class AddOne(UseCase[int, int]):
            async def execute(self, input_data: int) -> int:
                return input_data + 1

        uc = AddOne()
        assert await uc.execute(5) == 6

    async def test_generic_type_params(self) -> None:
        """UseCase supports different input/output types."""
        class StringToLen(UseCase[str, int]):
            async def execute(self, input_data: str) -> int:
                return len(input_data)

        uc = StringToLen()
        assert await uc.execute("hello") == 5


class TestEntityIdGenerate:
    def test_generate_creates_valid_uuid(self) -> None:
        """EntityId.generate() creates a valid UUID."""
        eid = EntityId.generate()
        # Should be a valid UUID
        UUID(str(eid.value))

    def test_generate_creates_unique_ids(self) -> None:
        """EntityId.generate() creates unique IDs each time."""
        id1 = EntityId.generate()
        id2 = EntityId.generate()
        assert id1.value != id2.value

    def test_from_str_creates_entity_id(self) -> None:
        """EntityId.from_str() parses a UUID string."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        eid = EntityId.from_str(uuid_str)
        assert str(eid.value) == uuid_str

    def test_from_str_invalid_raises(self) -> None:
        """EntityId.from_str() raises on invalid UUID string."""
        with pytest.raises(ValueError):
            EntityId.from_str("not-a-uuid")

    def test_str_representation(self) -> None:
        """str() on EntityId returns UUID string."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        eid = EntityId.from_str(uuid_str)
        assert str(eid) == uuid_str

    def test_eq_with_same_value(self) -> None:
        """Two EntityIds with same UUID are equal."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        id1 = EntityId.from_str(uuid_str)
        id2 = EntityId.from_str(uuid_str)
        assert id1 == id2

    def test_eq_with_different_value(self) -> None:
        """Two EntityIds with different UUIDs are not equal."""
        id1 = EntityId.generate()
        id2 = EntityId.generate()
        assert id1 != id2

    def test_eq_with_non_entity_id(self) -> None:
        """EntityId compared with non-EntityId returns NotImplemented."""
        eid = EntityId.generate()
        assert eid != "not-an-entity-id"

    def test_hash_consistency(self) -> None:
        """Same EntityId values produce same hash."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        id1 = EntityId.from_str(uuid_str)
        id2 = EntityId.from_str(uuid_str)
        assert hash(id1) == hash(id2)

    def test_can_be_used_in_set(self) -> None:
        """EntityId can be used in sets and dicts."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        id1 = EntityId.from_str(uuid_str)
        id2 = EntityId.from_str(uuid_str)
        s = {id1, id2}
        assert len(s) == 1
