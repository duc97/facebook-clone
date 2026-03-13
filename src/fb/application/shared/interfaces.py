from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class UnitOfWork(Protocol):
    async def __aenter__(self) -> UnitOfWork:
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...
