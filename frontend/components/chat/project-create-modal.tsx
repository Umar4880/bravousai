"use client";

import type { FormEvent } from "react";

type ProjectCreateModalProps = {
  title: string;
  description: string;
  isOpen: boolean;
  isLoading?: boolean;
  onTitleChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onCancel: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function ProjectCreateModal({
  title,
  description,
  isOpen,
  isLoading = false,
  onTitleChange,
  onDescriptionChange,
  onCancel,
  onSubmit,
}: ProjectCreateModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="confirm-modal-layer">
      <form className="project-create-modal" role="dialog" aria-modal="true" onSubmit={onSubmit}>
        <p className="empty-eyebrow">New project</p>
        <h2>Create project</h2>
        <label>
          Name
          <input
            value={title}
            onChange={(event) => onTitleChange(event.target.value)}
            autoFocus
            disabled={isLoading}
          />
        </label>
        <label>
          Description
          <textarea
            value={description}
            onChange={(event) => onDescriptionChange(event.target.value)}
            rows={4}
            disabled={isLoading}
          />
        </label>
        <div className="confirm-modal-actions">
          <button
            className="ghost-button"
            type="button"
            onClick={onCancel}
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            className="danger-button"
            type="submit"
            disabled={!title.trim() || isLoading}
          >
            {isLoading ? (
              <>
                <span className="btn-spinner" aria-hidden="true" />
                Creating…
              </>
            ) : (
              "Create"
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
