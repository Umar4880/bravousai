import uuid

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    user_id: uuid.UUID
    title: str = Field(min_length=1, max_length=160)
    description: str = ""
    instructions: str = ""


class ProjectUpdateRequest(BaseModel):
    user_id: uuid.UUID
    title: str | None = Field(default=None, max_length=160)
    description: str | None = None


class ProjectInstructionsRequest(BaseModel):
    user_id: uuid.UUID
    instructions: str = ""
