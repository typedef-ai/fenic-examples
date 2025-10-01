"""
Fenic session management for HN data operations.
"""

import os
from pathlib import Path
from typing import Optional

from fenic.api.session import Session
from fenic.api.session.config import SessionConfig, SemanticConfig, OpenAILanguageModel


class SessionManager:
    """Manages the Fenic session for data operations."""
    
    _instance: Optional['SessionManager'] = None
    _session: Optional[Session] = None
    
    def __new__(cls) -> 'SessionManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_session(self) -> Session:
        """Get or create the Fenic session."""
        if self._session is None:
            # Create data directory if it doesn't exist
            # Use path relative to src/hn_agent (this file's directory)
            # So data goes in src/assets/data
            data_dir = Path(__file__).parent.parent / "assets" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            # db_path is the directory - Fenic appends "{app_name}.duckdb"
            # Build config with semantic support if API key available
            config_kwargs = {
                "app_name": "hn_agent",
                "db_path": str(data_dir)
            }
            
            # Add OpenAI if API key is available
            if os.getenv("OPENAI_API_KEY"):
                config_kwargs["semantic"] = SemanticConfig(
                    language_models={
                        "gpt4": OpenAILanguageModel(
                            model_name="gpt-4o-mini",
                            rpm=100,
                            tpm=100000
                        )
                    }
                )
            
            config = SessionConfig(**config_kwargs)
            self._session = Session.get_or_create(config)
            
        return self._session


def get_session() -> Session:
    """Get the Fenic session for data operations."""
    return SessionManager().get_session()