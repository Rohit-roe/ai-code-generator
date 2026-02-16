"""Pydantic models for the AI Course Generator."""

from pydantic import BaseModel, Field
from typing import Optional


class CourseRequest(BaseModel):
    """User request to generate a course."""
    goal: str = Field(..., description="The learning goal, e.g. 'Learn Python programming'")
    model: Optional[str] = Field(default=None, description="Ollama model to use")


class WeekDetailsRequest(BaseModel):
    """Request to generate daily breakdown for a specific week."""
    goal: str
    week_number: int
    week_title: str
    concepts: list[str] = []
    model: Optional[str] = None


class DayDetailsRequest(BaseModel):
    """Request to generate details for a specific day."""
    goal: str
    day_title: str
    day_number: int
    duration_minutes: int = 60
    task_type: str = "theory"
    model: Optional[str] = None


class Resource(BaseModel):
    """A learning resource (YouTube video or web article)."""
    title: str
    url: str
    source: str  # "youtube" or "web"
    thumbnail: Optional[str] = None
    description: Optional[str] = None


class TopicClass(BaseModel):
    """A class/lesson covering a specific topic."""
    topic: str
    description: str
    subtopics: list[str]
    search_queries: list[str] = []
    resources: list[Resource] = []


# Legacy models kept for compatibility
class DailyTask(BaseModel):
    day: int
    title: str
    description: str = ""
    duration_minutes: int = 60
    task_type: str = "theory"
    table_of_contents: list[str] = []

class WeekGoal(BaseModel):
    week: int
    title: str
    goals: list[str]

class CoursePlan(BaseModel):
    title: str
    description: str
    duration_weeks: int = 0
    timeline: list[DailyTask] = []
    short_term_goals: list[WeekGoal] = []
    classes: list[TopicClass] = []
