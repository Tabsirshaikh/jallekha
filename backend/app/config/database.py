from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    url: str = "sqlite:///./jallekha.db"


DATABASE_CONFIG = DatabaseConfig()
