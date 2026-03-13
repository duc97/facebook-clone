from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PostContent:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("Post content cannot be empty")
        if len(self.value) > 5000:
            raise ValueError("Post content exceeds 5000 characters")