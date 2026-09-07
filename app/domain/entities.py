import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    username: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(256),
        unique=True,
        index=True,
        nullable=False,
    )

    password: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Project(Base):
    __tablename__ = "projects"

    __table_args__ = (
        Index("ix_projects_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    instructions: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="projects",
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    files: Mapped[list["ProjectFile"]] = relationship(
        "ProjectFile",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectFile(Base):
    __tablename__ = "project_files"

    __table_args__ = (
        Index("ix_project_files_project_created", "project_id", "created_at"),
        Index("ix_project_files_user_project_status", "user_id", "project_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    safe_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="application/octet-stream",
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    storage_bucket: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uploaded",
    )

    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="files",
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="conversations",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    workflow_records: Mapped[list["WorkflowRecord"]] = relationship(
        "WorkflowRecord",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    research_plans: Mapped[list["ResearchPlanRecord"]] = relationship(
        "ResearchPlanRecord",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    fetched_urls: Mapped[list["FetchedUrl"]] = relationship(
        "FetchedUrl",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    __table_args__ = (
        Index(
            "ix_artifacts_conversation_updated",
            "conversation_id",
            "updated_at",
        ),
        Index(
            "ix_artifacts_conversation_type_updated",
            "conversation_id",
            "artifact_type",
            "updated_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    artifact_type: Mapped[str] = mapped_column(
        String(48),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    short_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    original_user_query: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    parent_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="artifacts",
    )

    parent_artifact: Mapped[Optional["Artifact"]] = relationship(
        "Artifact",
        remote_side=[id],
        back_populates="revisions",
        foreign_keys=[parent_artifact_id],
    )

    revisions: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="parent_artifact",
        foreign_keys=[parent_artifact_id],
    )

    versions: Mapped[list["ArtifactVersion"]] = relationship(
        "ArtifactVersion",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )

    workflow_records: Mapped[list["WorkflowRecord"]] = relationship(
        "WorkflowRecord",
        back_populates="artifact",
    )


class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"

    __table_args__ = (
        Index("ix_artifact_versions_artifact_version", "artifact_id", "version", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    plan_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    spec_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    html_body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    css: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    javascript: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    validation_report: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    artifact: Mapped["Artifact"] = relationship(
        "Artifact",
        back_populates="versions",
    )


class WorkflowRecord(Base):
    __tablename__ = "workflow_records"

    __table_args__ = (
        # 1. Standard B-Tree Composite Indexes (Your existing ones)
        Index(
            "ix_workflow_records_conversation_created",
            "conversation_id",
            "created_at",
        ),
        Index(
            "ix_workflow_records_plan_json_gin",
            "plan_json",
            postgresql_using="gin", # This explicitly tells Postgres to use GIN instead of B-Tree
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    intent: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="instant",
    )

    plan_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    execution_path: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    current_step_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="completed",
    )

    route_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="workflow_records",
    )

    artifact: Mapped[Optional["Artifact"]] = relationship(
        "Artifact",
        back_populates="workflow_records",
    )

    research_plans: Mapped[list["ResearchPlanRecord"]] = relationship(
        "ResearchPlanRecord",
        back_populates="workflow_record",
    )

    fetched_urls: Mapped[list["FetchedUrl"]] = relationship(
        "FetchedUrl",
        back_populates="workflow_record",
    )


class ResearchPlanRecord(Base):
    __tablename__ = "research_plans"

    __table_args__ = (
        Index(
            "ix_research_plans_conversation_created",
            "conversation_id",
            "created_at",
        ),
        Index(
            "ix_research_plans_plan_json_gin",
            "plan_json",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    workflow_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    topic: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    research_depth: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="normal",
    )

    plan_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    synthesized_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="research_plans",
    )

    workflow_record: Mapped[Optional["WorkflowRecord"]] = relationship(
        "WorkflowRecord",
        back_populates="research_plans",
    )

    fetched_urls: Mapped[list["FetchedUrl"]] = relationship(
        "FetchedUrl",
        back_populates="research_plan",
        cascade="all, delete-orphan",
    )


class FetchedUrl(Base):
    __tablename__ = "fetched_urls"

    __table_args__ = (
        Index(
            "ix_fetched_urls_conversation_created",
            "conversation_id",
            "created_at",
        ),
        Index(
            "ix_fetched_urls_research_plan_created",
            "research_plan_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    workflow_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    research_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_plans.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    title: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    source: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    published_date: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )

    snippet: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    fetched_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    relevance: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="fetched_urls",
    )

    workflow_record: Mapped[Optional["WorkflowRecord"]] = relationship(
        "WorkflowRecord",
        back_populates="fetched_urls",
    )

    research_plan: Mapped[Optional["ResearchPlanRecord"]] = relationship(
        "ResearchPlanRecord",
        back_populates="fetched_urls",
    )
