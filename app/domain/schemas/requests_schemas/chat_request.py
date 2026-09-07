import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

_ARTIFACT_PREFIX_RE = re.compile(r"^/artifact\s*", re.IGNORECASE)


class ChatRequest(BaseModel):
    user_id: uuid.UUID
    project_id: uuid.UUID | None = None
    query: str = Field(min_length=1)
    mode: Literal["instant", "extended"] = "instant"
    conversation_id: uuid.UUID | None = None

    # Set by model_validator — True when user prefixed query with /artifact
    wants_artifact: bool = False
    # The query with the /artifact prefix stripped (same as query when not present)
    clean_query: str = ""

    @model_validator(mode="after")
    def _parse_artifact_prefix(self) -> "ChatRequest":
        if _ARTIFACT_PREFIX_RE.match(self.query):
            self.wants_artifact = True
            self.clean_query = _ARTIFACT_PREFIX_RE.sub("", self.query).strip()
        else:
            self.wants_artifact = False
            self.clean_query = self.query
        return self
