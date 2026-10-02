from dataclasses import dataclass, field

from app.config.env import REPO_ROOT, env_str

# Anchored to the repository root so the file does not depend on the working directory.
DEFAULT_DATABASE_URL = f"sqlite:///{(REPO_ROOT / 'jallekha.db').as_posix()}"


@dataclass(frozen=True)
class DatabaseConfig:
    # Environment: DATABASE_URL (see .env.example).
    url: str = field(default_factory=lambda: env_str("DATABASE_URL", DEFAULT_DATABASE_URL))


DATABASE_CONFIG = DatabaseConfig()
