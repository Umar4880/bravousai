"use client";

import type { ResearchProject } from "./projects";

type ProjectDeleteModalProps = {
  project: ResearchProject;
  isMutating: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ProjectDeleteModal({
  project,
  isMutating,
  onCancel,
  onConfirm,
}: ProjectDeleteModalProps) {
  return (
    <div className="confirm-modal-layer">
      <div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-project-title">
        <p className="empty-eyebrow">Delete project</p>
        <h2 id="delete-project-title">{project.title || "Untitled project"}</h2>
        <p>This will permanently delete the project and all of its associated chats.</p>
        <div className="confirm-modal-actions">
          <button className="ghost-button" type="button" onClick={onCancel} disabled={isMutating}>
            Cancel
          </button>
          <button className="danger-button" type="button" onClick={onConfirm} disabled={isMutating}>
            {isMutating ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}
