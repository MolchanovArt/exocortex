"""Data models using Pydantic."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """User profile model loaded from JSON."""

    id: str = Field(..., description="User identifier")
    name: str = Field(..., description="User name")
    roles: List[str] = Field(default_factory=list, description="User roles")
    current_projects: List[str] = Field(default_factory=list, description="Current projects")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    narrative: str = Field("", description="User narrative/summary")

    class Config:
        """Pydantic config."""

        extra = "allow"  # Allow extra fields in JSON

