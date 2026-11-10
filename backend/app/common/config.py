from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "LexRag"
    ENVIRONMENT: str = "development"
    
    # API keys
    GEMINI_API_KEY: str
    DASHSCOPE_API_KEY: str
    
    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    
    POSTGRES_DB_CORPUS: str
    POSTGRES_DB_USERS: str
    POSTGRES_DB_MAIN: str
    
    DATABASE_URL_CORPUS: str
    DATABASE_URL_USERS: str
    DATABASE_URL_MAIN: str
    
    # Qdrant
    QDRANT_CORPUS_COLLECTION_NAME: str = "legal_docs"
    QDRANT_ACTS_COLLECTION_NAME: str = "legal_acts"
    DENSE_MODEL_NAME: str = "BAAI/bge-large-en-v1.5"
    SPARSE_MODEL_NAME: str = "Qdrant/bm25"
    QDRANT_INFERENCE_CUDA: bool = True
    QDRANT_URL: str
    # QDRANT__SERVICE__API_KEY: str
    
    
    # frontend
    # VITE_FRONTEND_API_URL: str
    
    # user and group identifier
    UID : int = 1000
    GID: int = 1000

    
    # debug settings
    @property
    def DEBUG(self) -> bool:
        return self.ENVIRONMENT == "development"
    
    # docker will inject env variables to container's enviornment and pydantic will read from the container's environment too
    
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parents[3] / ".env",
        extra="ignore"
    )
    
    def get_setting_value(self, var_name: str):
        return getattr(self, var_name, None)


# Create a global settings instance
settings = Settings() #type: ignore