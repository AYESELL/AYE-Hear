from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PostgreSQLConnectionSettings:
    dsn: str


class PostgreSQLStore:
    def __init__(self, settings: PostgreSQLConnectionSettings) -> None:
        self.settings = settings

    def describe_backend(self) -> str:
        return "PostgreSQL"