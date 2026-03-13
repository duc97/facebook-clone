from __future__ import annotations

import uuid
from datetime import datetime

import strawberry


DateTimeScalar = strawberry.scalar(
    datetime,
    name="DateTime",
    description="ISO 8601 datetime string",
    serialize=lambda v: v.isoformat() if v else None,
    parse_value=lambda v: datetime.fromisoformat(v) if v else None,
)

UUIDScalar = strawberry.scalar(
    uuid.UUID,
    name="UUID",
    description="UUID string",
    serialize=lambda v: str(v),
    parse_value=lambda v: uuid.UUID(v),
)
