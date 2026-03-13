from __future__ import annotations

from typing import Any

from strawberry.fastapi import BaseContext

from fb.container import Container


class GraphQLContext(BaseContext):
    def __init__(
        self,
        container: Container,
        current_user_id: str | None = None,
        current_user_email: str | None = None,
        request: Any = None,
    ) -> None:
        self.container = container
        self.current_user_id = current_user_id
        self.current_user_email = current_user_email
        self._request = request

    @property
    def is_authenticated(self) -> bool:
        return self.current_user_id is not None

    @property
    def req(self) -> Any:
        """Get the request object (from BaseContext or stored)."""
        return self._request or getattr(self, "request", None)
