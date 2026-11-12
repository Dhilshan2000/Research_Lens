import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # Groq API configuration
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_FILTER_MODEL: str = os.getenv("GROQ_FILTER_MODEL", "llama-3.1-8b-instant")

    # Crawler configuration
    DEFAULT_CRAWL_DEPTH: int = int(os.getenv("DEFAULT_CRAWL_DEPTH", "1"))
    DEFAULT_MAX_PAGES: int = int(os.getenv("DEFAULT_MAX_PAGES", "15"))
    CRAWL_TIMEOUT_SECONDS: int = int(os.getenv("CRAWL_TIMEOUT_SECONDS", "10"))
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 ResearchLens/1.0"
    )

    # Embedding and Vector store configuration
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "5"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "600"))  # approx 500-800 tokens
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))  # approx 10-20% overlap

    # Relevance filtering threshold
    RELEVANCE_THRESHOLD: float = float(os.getenv("RELEVANCE_THRESHOLD", "6.0"))

    # Directories
    DATA_DIR: Path = BASE_DIR / "data"
    CACHE_DIR: Path = BASE_DIR / "data" / "cache"
    EXPORTS_DIR: Path = BASE_DIR / "data" / "exports"


# Ensure necessary runtime directories exist
Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
Config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
Config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

