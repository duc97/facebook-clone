from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


class UseCase(ABC, Generic[InputType, OutputType]):
    @abstractmethod
    async def execute(self, input_data: InputType) -> OutputType:
        ...
