from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    groq_api_key: str = ""
    gen_model: str = "llama-3.3-70b-versatile"
    fast_model: str = "llama-3.1-8b-instant"

    # Vector store — empty URL means local on-disk Qdrant (dev mode)
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_local_path: str = "./qdrant_local"
    collection: str = "ansh_corpus"

    # Embeddings — bge-small via fastembed (ONNX, no torch: fits small servers)
    embed_model: str = "BAAI/bge-small-en-v1.5"

    # Retrieval
    top_k: int = 6

    # API
    allowed_origins: str = "http://localhost:3000"
    rate_limit_per_min: int = 20

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
