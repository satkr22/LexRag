from typing import Literal, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.config.settings import LLMConfig, ProviderConfig, RouteConfig
from app.common.config import settings


PROVIDER_FACTORIES: dict[str, type[BaseChatModel]] = {
    "openai":  ChatOpenAI,
    "gemini":  ChatGoogleGenerativeAI,
    "rag":     ChatGoogleGenerativeAI,
    "default": ChatGoogleGenerativeAI,
    "default-rag": ChatGoogleGenerativeAI,
}

# provider name -> raw built model
_MODELS: dict[str, BaseChatModel] = {}

# provider name -> model with tools bound
_AGENT_MODELS: dict[str, Runnable] = {}


def _build_single_model(provider_name: str, cfg: ProviderConfig) -> BaseChatModel:
    factory = PROVIDER_FACTORIES.get(provider_name)
    if factory is None:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")

    auth = cfg.authentication
    api_key = settings.get_setting_value(auth.env_var)
    if not api_key:
        raise RuntimeError(f"Missing environment variable: {auth.env_var}")

    kwargs = dict(cfg.init_kwargs)
    if auth.constructor_arg in kwargs:
        raise ValueError("Do not place API keys inside init_kwargs.")
    kwargs[auth.constructor_arg] = api_key

    try:
        return factory(**kwargs)
    except TypeError as exc:
        raise ValueError(
            f"Invalid constructor configuration for '{provider_name}'."
        ) from exc


def _get_model(provider_name: str, config: LLMConfig) -> BaseChatModel:
    if provider_name not in _MODELS:
        _MODELS[provider_name] = _build_single_model(
            provider_name, config.providers[provider_name]
        )
    return _MODELS[provider_name]


def _get_agent_model(
    provider_name: str, config: LLMConfig, tools: Sequence[BaseTool]
) -> Runnable:
    if provider_name not in _AGENT_MODELS:
        _AGENT_MODELS[provider_name] = _get_model(provider_name, config).bind_tools(tools)
    return _AGENT_MODELS[provider_name]


def build_chat_model(
    config: LLMConfig,
    route: Literal["agent", "rag"] = "agent",
    tools: Sequence[BaseTool] | None = None,
) -> Runnable:
    route_cfg: RouteConfig = getattr(config, route)

    if route == "agent" and not tools:
        raise ValueError("route='agent' requires tools")
    if route == "rag" and tools:
        raise ValueError("route='rag' must not receive tools")

    if route == "agent":
        chain = [_get_agent_model(route_cfg.active_provider, config, tools)] # type: ignore
        if route_cfg.fallback_provider:
            chain.append(_get_agent_model(route_cfg.fallback_provider, config, tools)) # type: ignore
    else:
        chain = [_get_model(route_cfg.active_provider, config)]
        if route_cfg.fallback_provider:
            chain.append(_get_model(route_cfg.fallback_provider, config))

    if len(chain) == 1:
        return chain[0]
    return chain[0].with_fallbacks(chain[1:])