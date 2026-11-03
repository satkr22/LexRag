from langchain_core.language_models import BaseChatModel

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.config.settings import LLMConfig
from app.common.config import settings

# supported provider adapters.
PROVIDER_FACTORIES = {
    "openai": ChatOpenAI,
    "gemini": ChatGoogleGenerativeAI,
    "default": ChatGoogleGenerativeAI,
    "query-rewriter": ChatGoogleGenerativeAI,
}


def build_chat_model(config: LLMConfig) -> BaseChatModel:

    provider_name = config.active_provider

    # resolve provider factory
    factory = PROVIDER_FACTORIES.get(provider_name, "default") 

    if factory is None:
        raise ValueError(
            f"Unsupported LLM provider: {provider_name}"
        )

    # retrieve provider-specific settings
    provider_config = config.providers[provider_name]

    # retrieve API key from environment
    auth_config = provider_config.authentication
    api_key = settings.get_setting_value(auth_config.env_var)

    if not api_key:
        raise RuntimeError(
            f"Missing environment variable: {auth_config.env_var}"
        )

    # read all constructor arguments from YAML
    kwargs = dict(provider_config.init_kwargs)

    # prevent duplicate authentication arguments
    if auth_config.constructor_arg in kwargs:
        raise ValueError(
            "Do not place API keys inside init_kwargs. "
            "Configure authentication separately."
        )

    # inject secret into provider constructor
    kwargs[auth_config.constructor_arg] = api_key

    try:
        model = factory(**kwargs)

    except TypeError as exc:
        raise ValueError(
            f"Invalid constructor configuration for provider "
            f"'{provider_name}'. Check init_kwargs."
        ) from exc

    return model