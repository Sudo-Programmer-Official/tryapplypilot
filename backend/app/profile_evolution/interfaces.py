from __future__ import annotations

from typing import Protocol

from .conversation import ProfileEvolutionSession


class ProfileEvolutionStore(Protocol):
    async def get_session(self, user_id: str) -> ProfileEvolutionSession | None:
        ...

    async def save_session(self, session: ProfileEvolutionSession) -> ProfileEvolutionSession:
        ...
