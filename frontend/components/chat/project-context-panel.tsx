"use client";

import { useState } from "react";
import type { AuthUser, ConversationSummary } from "../../lib/api";
import type { ChatMeta } from "./types";
import type { ResearchProject } from "./projects";

type ProjectContextPanelProps = {
  authUser: AuthUser | null;
  conversations: ConversationSummary[];
  meta: ChatMeta;
  activeConversationId: string | null;
  pendingCount: number;
  project: ResearchProject;
  onInstructionsChange: (value: string) => void;
  onFilesAdded: (files: File[]) => Promise<void>;
  onFileDelete: (fileId: string) => void;
};

export function ProjectContextPanel({
  authUser,
  conversations,
  meta,
  activeConversationId,
  pendingCount,
  project,
  onInstructionsChange,
  onFilesAdded,
  onFileDelete,
}: ProjectContextPanelProps) {
  const [isInstructionsModalOpen, setIsInstructionsModalOpen] = useState(false);
  const [draftInstructions, setDraftInstructions] = useState(project.instructions);
  const [isUploading, setIsUploading] = useState(false);

  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId);
  const capacityUsed = Math.min(Math.max(project.files.length * 8, 0), 100);

  return (
    <>
      <aside className="project-context-panel" aria-label="Project context">
      <section className="context-section">
        <div className="context-section-header">
          <h2>Instructions</h2>
          <button 
            type="button" 
            aria-label="Edit project instructions"
            onClick={() => {
              setDraftInstructions(project.instructions);
              setIsInstructionsModalOpen(true);
            }}
          >
            +
          </button>
        </div>
        <div
          style={{
            background: "rgba(255, 255, 255, 0.03)",
            border: "1px solid rgba(232, 227, 218, 0.1)",
            borderRadius: "8px",
            padding: "10px",
            fontSize: "13px",
            color: "var(--text-subtle)",
            height: "80px",
            overflowX: "auto",
            overflowY: "auto",
            whiteSpace: "pre",
            marginTop: "12px"
          }}
        >
          {project.instructions || "No custom instructions saved."}
        </div>
      </section>

      <section className="context-section">
        <div className="context-section-header">
          <h2>Files</h2>
          {!isUploading ? (
            <label aria-label="Upload project files">
              +
              <input
                type="file"
                multiple
                onChange={async (event) => {
                  const target = event.target;
                  const selectedFiles = Array.from(target.files ?? []);
                  if (selectedFiles.length > 0) {
                    setIsUploading(true);
                    try {
                      await onFilesAdded(selectedFiles);
                    } finally {
                      setIsUploading(false);
                    }
                  }
                  target.value = "";
                }}
              />
            </label>
          ) : (
            <span style={{ fontSize: "12px", color: "var(--accent)" }}>Uploading...</span>
          )}
        </div>
        <div className="capacity-meter" aria-label="Project capacity used">
          <span style={{ width: `${capacityUsed}%` }} />
        </div>
        <p>{Math.round(capacityUsed)}% of project capacity used</p>
        {project.files.length > 0 && (
          <div className="project-file-list" style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "12px" }}>
            {project.files.slice(0, 4).map((file) => (
              <div 
                key={file.id} 
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 12px",
                  background: "rgba(255, 255, 255, 0.05)",
                  borderRadius: "8px",
                  border: "1px solid rgba(232, 227, 218, 0.1)",
                  fontSize: "13px"
                }}
              >
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, paddingRight: "8px" }} title={file.original_filename}>
                  {file.original_filename}
                </span>
                <button 
                  type="button" 
                  onClick={() => onFileDelete(file.id)} 
                  aria-label={`Delete ${file.original_filename}`}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "var(--text-subtle)",
                    cursor: "pointer",
                    padding: "4px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0
                  }}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="context-section context-status">
        <h2>Workspace</h2>
        <dl>
          <div>
            <dt>User</dt>
            <dd>{authUser?.username || "Guest"}</dd>
          </div>
          <div>
            <dt>Active chat</dt>
            <dd>{activeConversation?.title || (activeConversationId ? "Current thread" : "New thread")}</dd>
          </div>
          <div>
            <dt>Stage</dt>
            <dd>{meta.backendStage || "waiting for input"}</dd>
          </div>
          <div>
            <dt>Pending</dt>
            <dd>{pendingCount}</dd>
          </div>
        </dl>
      </section>
    </aside>
      
      {isInstructionsModalOpen && (
        <div className="confirm-modal-layer">
          <div className="project-create-modal confirm-modal" role="dialog" aria-modal="true" style={{ width: "500px", maxWidth: "90vw" }}>
            <p className="empty-eyebrow">Project Settings</p>
            <h2 style={{ marginBottom: "16px" }}>Custom Instructions</h2>
            <label style={{ display: "flex", flexDirection: "column", gap: "8px", width: "100%" }}>
              <span style={{ fontSize: "14px", fontWeight: 600 }}>Instructions</span>
              <textarea 
                value={draftInstructions} 
                onChange={(e) => setDraftInstructions(e.target.value)} 
                rows={10} 
                autoFocus 
                placeholder="Add rules for all agents in this project..."
                style={{
                  width: "100%",
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid rgba(232, 227, 218, 0.1)",
                  borderRadius: "8px",
                  padding: "12px",
                  color: "var(--text)",
                  fontFamily: "inherit",
                  resize: "vertical"
                }}
              />
            </label>
            <div className="confirm-modal-actions" style={{ marginTop: "24px" }}>
              <button className="ghost-button" type="button" onClick={() => setIsInstructionsModalOpen(false)}>
                Cancel
              </button>
              <button 
                className="danger-button" 
                style={{ background: "var(--accent)", color: "#111", border: "none" }} 
                type="button" 
                onClick={() => {
                  onInstructionsChange(draftInstructions);
                  setIsInstructionsModalOpen(false);
                }}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
