"""
Pydantic models for MCP tools.
"""

from typing import List
from pydantic import BaseModel, Field


class DiscussionTheme(BaseModel):
    """Represents a theme or topic within a discussion."""
    topic: str = Field(description="Name of the discussion theme")
    summary: str = Field(description="Concise summary of the theme, viewpoints, and evidence")
    stance_spectrum: str = Field(default="", description="How opinions vary across this theme")
    representative_comment_ids: List[int] = Field(
        default_factory=list, description="Example comment IDs relevant to this theme"
    )
    off_topic: bool = Field(default=False, description="True if this theme is off-topic from the story")


class StorySummary(BaseModel):
    """Structured summary of a Hacker News story and its discussion."""
    tl_dr: str = Field(description="Two-sentence top summary")
    story_overview: str = Field(description="Short overview of the story itself")
    key_points: List[str] = Field(default_factory=list, description="Key points and takeaways")
    discussion_themes: List[DiscussionTheme] = Field(
        default_factory=list, description="Themes across the discussion, including off-topic branches"
    )
    variety_present: bool = Field(description="Whether discussion splits into distinct topics or viewpoints")
    off_topic_themes: List[str] = Field(default_factory=list, description="Names of off-topic themes, if any")
    risks_or_concerns: List[str] = Field(default_factory=list, description="Risks or concerns raised")
    actionables: List[str] = Field(default_factory=list, description="Any concrete action items")
    sources: List[int] = Field(default_factory=list, description="Referenced comment IDs")
    truncated_input: bool = Field(description="True if input transcript was truncated due to size")