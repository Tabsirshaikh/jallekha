from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    name: str = "JalLekha API"
    version: str = "0.1.0"
    environment: str = "development"


APP_CONFIG = AppConfig()
