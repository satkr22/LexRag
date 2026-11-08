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


class RouteConfig(StrictConfig):
    active_provider: str
    fallback_provider: str | None = None


class LLMConfig(StrictConfig):
    providers: dict[str, ProviderConfig]
    agent: RouteConfig
    rag: RouteConfig

    @model_validator(mode="after")
    def validate_providers(self):
        # 1. every configured provider block must be referenced by a route
        #    (this also catches typos in provider names)
        for route_name in ("agent", "rag"):
            route = getattr(self, route_name)
            for role in ("active_provider", "fallback_provider"):
                name = getattr(route, role)
                if name is None:
                    continue
                if name not in self.providers:
                    raise ValueError(
                        f"llm.{route_name}.{role}={name!r} is not defined "
                        f"under llm.providers"
                    )
        return self


class AgentConfig(StrictConfig):
    system_prompt: str
    recursion_limit: int = Field(default=200, ge=1)
    
    @model_validator(mode="after")
    def check_prompt_exists(self):
        p = Path(self.system_prompt)
        if not p.exists():
            raise ValueError(f"system prompt not found: {p}")
        return self


class AppConfig(StrictConfig):
    llm: LLMConfig
    agent: AgentConfig


def load_config() -> AppConfig:

    path = Path(__file__).parent / "config.yaml"

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file)

    if not isinstance(raw_config, dict):
        raise ValueError("Invalid YAML configuration.")
    


    return AppConfig.model_validate(raw_config)