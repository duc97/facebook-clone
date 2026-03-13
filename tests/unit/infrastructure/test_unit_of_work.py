from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fb.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork


class TestSqlAlchemyUnitOfWork:
    def test_session_raises_before_enter(self) -> None:
        """Accessing session before context manager raises RuntimeError."""
        factory = MagicMock()
        uow = SqlAlchemyUnitOfWork(factory)
        with pytest.raises(RuntimeError, match="UnitOfWork not started"):
            _ = uow.session

    async def test_enter_creates_session(self) -> None:
        """__aenter__ creates session from factory."""
        mock_session = AsyncMock()
        factory = MagicMock(return_value=mock_session)
        uow = SqlAlchemyUnitOfWork(factory)

        result = await uow.__aenter__()

        assert result is uow
        assert uow.session is mock_session
        factory.assert_called_once()

    async def test_exit_closes_session_on_success(self) -> None:
        """__aexit__ closes session when no exception."""
        mock_session = AsyncMock()
        factory = MagicMock(return_value=mock_session)
        uow = SqlAlchemyUnitOfWork(factory)

        await uow.__aenter__()
        await uow.__aexit__(None, None, None)

        mock_session.close.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

    async def test_exit_rollbacks_on_exception(self) -> None:
        """__aexit__ rolls back session when exception occurred."""
        mock_session = AsyncMock()
        factory = MagicMock(return_value=mock_session)
        uow = SqlAlchemyUnitOfWork(factory)

        await uow.__aenter__()
        await uow.__aexit__(ValueError, ValueError("fail"), None)

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    async def test_exit_clears_session(self) -> None:
        """__aexit__ sets session to None."""
        mock_session = AsyncMock()
        factory = MagicMock(return_value=mock_session)
        uow = SqlAlchemyUnitOfWork(factory)

        await uow.__aenter__()
        await uow.__aexit__(None, None, None)

        with pytest.raises(RuntimeError):
            _ = uow.session

    async def test_commit_delegates_to_session(self) -> None:
        """commit() calls session.commit()."""
        mock_session = AsyncMock()
        factory = MagicMock(return_value=mock_session)
        uow = SqlAlchemyUnitOfWork(factory)

        await uow.__aenter__()
        await uow.commit()

        mock_session.commit.assert_awaited_once()

    async def test_rollback_delegates_to_session(self) -> None:
        """rollback() calls session.rollback()."""
        mock_session = AsyncMock()
        factory = MagicMock(return_value=mock_session)
        uow = SqlAlchemyUnitOfWork(factory)

        await uow.__aenter__()
        await uow.rollback()

        mock_session.rollback.assert_awaited_once()

    async def test_context_manager_protocol(self) -> None:
        """UoW works as async context manager."""
        mock_session = AsyncMock()
        factory = MagicMock(return_value=mock_session)

        async with SqlAlchemyUnitOfWork(factory) as uow:
            assert uow.session is mock_session

        mock_session.close.assert_awaited_once()
