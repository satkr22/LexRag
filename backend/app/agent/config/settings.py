import yaml
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthenticationConfig(StrictConfig):
    env_var: str
    constructor_arg: str = "api_key"


class ProviderConfig(StrictConfig):
    authentication: AuthenticationConfig
    init_kwargs: dict[str, Any] = Field(default_factory=dict)


class LLMConfig(StrictConfig):
    active_provider: Literal["gemini", "openai", "query-rewriter", "default"]
    providers: dict[str, ProviderConfig]

    @model_validator(mode="after")
    def validate_providers(self):

        supported = {"gemini", "openai", "query-rewriter", "default"}

        unknown = set(self.providers) - supported

        if unknown:
            raise ValueError(
                f"Unsupported providers configured: {unknown}"
            )

        if self.active_provider not in self.providers:
            raise ValueError(
                f"Configuration missing for active provider: "
                f"{self.active_provider}"
            )


        return self


class AgentConfig(StrictConfig):
    system_prompt: str
    recursion_limit: int = Field(default=20, ge=1)


class AppConfig(StrictConfig):
    llm: LLMConfig
    agent: AgentConfig


def load_config(
    config_path: str | Path = "config.yaml",
) -> AppConfig:

    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file)

    if not isinstance(raw_config, dict):
        raise ValueError("Invalid YAML configuration.")

    return AppConfig.model_validate(raw_config)