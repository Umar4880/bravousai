"use client";

import type { ConversationSummary } from "../../lib/api";

type ConfirmDeleteModalProps = {
  conversation: ConversationSummary;
  isMutating: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmDeleteModal({
  conversation,
  isMutating,
  onCancel,
  onConfirm,
}: ConfirmDeleteModalProps) {
  return (
    <div className="confirm-modal-layer">
      <div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-chat-title">
        <p className="empty-eyebrow">Delete chat</p>
        <h2 id="delete-chat-title">{conversation.title || "Untitled chat"}</h2>
        <p>This will remove the chat and its saved messages from your sidebar.</p>
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
