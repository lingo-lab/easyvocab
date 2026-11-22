"""API keys and other settings, read from the environment or a `.env` file."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment settings: `FIREWORKS_API_KEY`, `NEBIUS_API_KEY`, `OPENAI_API_KEY`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    fireworks_api_key: SecretStr | None = None
    nebius_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    def key(self, name: str) -> str | None:
        """Plain value of an API key field such as `fireworks_api_key`, or None if unset."""
        secret = getattr(self, name)
        return secret.get_secret_value() if secret else None
