"""Configuration management using environment variables."""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


def get_project_root() -> Path:
    """
    Get the project root directory (where data/ and src/ are located).

    This function finds the project root by looking for the 'data' directory
    starting from the current file's location.
    """
    # Start from this file: src/exocortex/core/config.py
    current_file = Path(__file__)
    # Go up to project root: src/exocortex/core -> src/exocortex -> src -> project_root
    project_root = current_file.parent.parent.parent.parent
    
    # Verify it's the right place by checking for data/ directory
    if (project_root / "data").exists():
        return project_root
    
    # Fallback: try going up one more level (in case we're in a different structure)
    potential_root = project_root.parent
    if (potential_root / "data").exists():
        return potential_root
    
    # Last resort: return the calculated root anyway
    return project_root


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    # OpenAI
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")

    # Telegram
    telegram_bot_token: Optional[str] = Field(None, env="TELEGRAM_BOT_TOKEN")
    telegram_target_chat_id: Optional[str] = Field(None, env="TELEGRAM_TARGET_CHAT_ID")

    # Google
    google_credentials_file: Optional[str] = Field(None, env="GOOGLE_CREDENTIALS_FILE")
    google_token_file: Optional[str] = Field(None, env="GOOGLE_TOKEN_FILE")
    google_calendar_id: Optional[str] = Field(None, env="GOOGLE_CALENDAR_ID")
    google_drive_root_folder_id: Optional[str] = Field(None, env="GOOGLE_DRIVE_ROOT_FOLDER_ID")

    # Database
    exocortex_db_path: str = Field("exocortex.db", env="EXOCORTEX_DB_PATH")

    # User profile
    user_profile_path: str = Field("data/user_profile.json", env="USER_PROFILE_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables

    def get_user_profile_path(self) -> Path:
        """Get the resolved user profile path relative to project root."""
        profile_path = Path(self.user_profile_path)
        if profile_path.is_absolute():
            return profile_path
        return get_project_root() / profile_path

    def get_db_path(self) -> Path:
        """Get the resolved database path relative to project root."""
        db_path = Path(self.exocortex_db_path)
        if db_path.is_absolute():
            return db_path
        return get_project_root() / db_path


# Load .env file if it exists (from project root)
project_root = get_project_root()
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()  # Try current directory as fallback

# Global config instance
config = Config()

