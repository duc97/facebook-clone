from __future__ import annotations

import uuid
from datetime import datetime

from fb.presentation.graphql.scalars import DateTimeScalar, UUIDScalar


class TestDateTimeScalar:
    def test_serialize_datetime(self) -> None:
        """DateTimeScalar serializes datetime to ISO string."""
        sd = DateTimeScalar._scalar_definition
        dt = datetime(2026, 3, 12, 10, 30, 0)
        result = sd.serialize(dt)
        assert result == "2026-03-12T10:30:00"

    def test_serialize_none(self) -> None:
        """DateTimeScalar serializes None to None."""
        sd = DateTimeScalar._scalar_definition
        result = sd.serialize(None)
        assert result is None

    def test_parse_value(self) -> None:
        """DateTimeScalar parses ISO string to datetime."""
        sd = DateTimeScalar._scalar_definition
        result = sd.parse_value("2026-03-12T10:30:00")
        assert result == datetime(2026, 3, 12, 10, 30, 0)

    def test_parse_value_none(self) -> None:
        """DateTimeScalar returns None for None input."""
        sd = DateTimeScalar._scalar_definition
        result = sd.parse_value(None)
        assert result is None


class TestUUIDScalar:
    def test_serialize_uuid(self) -> None:
        """UUIDScalar serializes UUID to string."""
        sd = UUIDScalar._scalar_definition
        u = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        result = sd.serialize(u)
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_parse_value(self) -> None:
        """UUIDScalar parses string to UUID."""
        sd = UUIDScalar._scalar_definition
        result = sd.parse_value("550e8400-e29b-41d4-a716-446655440000")
        assert result == uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
