"use client";

import type { ConversationSummary } from "../../lib/api";
import { LoadingScreen } from "./loading-screen";

type ConversationListProps = {
  authUserExists: boolean;
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  pendingConversationIds: Set<string>;
  isLoadingConversations: boolean;
  chatMenuId: string | null;
  renamingChatId: string | null;
  renameDraft: string;
  isMutatingChat: boolean;
  onOpenConversation: (conversationId: string) => void;
  onToggleMenu: (conversationId: string) => void;
  onStartRename: (conversation: ConversationSummary) => void;
  onCancelRename: () => void;
  onCommitRename: (conversation: ConversationSummary) => void;
  onRenameDraftChange: (value: string) => void;
  onDeleteRequest: (conversation: ConversationSummary) => void;
};

export function ConversationList({
  authUserExists,
  conversations,
  activeConversationId,
  pendingConversationIds,
  isLoadingConversations,
  chatMenuId,
  renamingChatId,
  renameDraft,
  isMutatingChat,
  onOpenConversation,
  onToggleMenu,
  onStartRename,
  onCancelRename,
  onCommitRename,
  onRenameDraftChange,
  onDeleteRequest,
}: ConversationListProps) {
  return (
    <section className="conversation-history" aria-label="Saved chats">
      <div className="section-heading">
        <h2>Recent work</h2>
      </div>

      {!authUserExists && <p className="sidebar-empty">Sign in to see your saved chats.</p>}
      {authUserExists && isLoadingConversations && (
        <LoadingScreen variant="inline" label="Loading chats..." />
      )}
      {authUserExists && !isLoadingConversations && conversations.length === 0 && (
        <p className="sidebar-empty">No chats yet.</p>
      )}

      {authUserExists && conversations.length > 0 && (
        <div className="conversation-list">
          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={`conversation-item ${
                conversation.id === activeConversationId ? "active" : ""
              } ${pendingConversationIds.has(conversation.id) ? "pending" : ""}`}
            >
              {renamingChatId === conversation.id ? (
                <input
                  className="conversation-rename-input"
                  value={renameDraft}
                  onChange={(event) => onRenameDraftChange(event.target.value)}
                  onBlur={() => onCommitRename(conversation)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      onCommitRename(conversation);
                    }
                    if (event.key === "Escape") {
                      event.preventDefault();
                      onCancelRename();
                    }
                  }}
                  autoFocus
                  maxLength={128}
                  disabled={isMutatingChat}
                  aria-label="Rename chat"
                />
              ) : (
                <button
                  className="conversation-title-button"
                  type="button"
                  onClick={() => onOpenConversation(conversation.id)}
                >
                  <span>{conversation.title || "Untitled chat"}</span>
                  {pendingConversationIds.has(conversation.id) && <small>Generating...</small>}
                </button>
              )}
              <button
                className="conversation-menu-button"
                type="button"
                onClick={() => onToggleMenu(conversation.id)}
                aria-label={`Options for ${conversation.title || "Untitled chat"}`}
                aria-haspopup="menu"
                aria-expanded={chatMenuId === conversation.id}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="5" r="1" />
                  <circle cx="12" cy="12" r="1" />
                  <circle cx="12" cy="19" r="1" />
                </svg>
              </button>
              {chatMenuId === conversation.id && (
                <div className="conversation-menu" role="menu">
                  <button type="button" role="menuitem" onClick={() => onStartRename(conversation)}>
                    Rename
                  </button>
                  <button
                    className="danger"
                    type="button"
                    role="menuitem"
                    onClick={() => onDeleteRequest(conversation)}
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
