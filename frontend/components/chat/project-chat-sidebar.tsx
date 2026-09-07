"use client";

import type { ConversationSummary } from "../../lib/api";
import type { ResearchProject } from "./projects";
import { LoadingScreen } from "./loading-screen";

type ProjectChatSidebarProps = {
  project: ResearchProject;
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  isLoading: boolean;
  onProjectOverview: () => void;
  onOpenConversation: (conversationId: string) => void;
  onNewChat: () => void;
};

export function ProjectChatSidebar({
  project,
  conversations,
  activeConversationId,
  isLoading,
  onProjectOverview,
  onOpenConversation,
  onNewChat,
}: ProjectChatSidebarProps) {
  return (
    <aside className="project-chat-sidebar" aria-label="Project chats">
      <button className="back-link chat-back-link" type="button" onClick={onProjectOverview}>
        {"<- Project"}
      </button>
      <div>
        <h2>{project.title}</h2>
        <button type="button" onClick={onNewChat}>
          + New chat
        </button>
      </div>
      {isLoading ? (
        <LoadingScreen variant="inline" label="Loading chats..." />
      ) : (
        <div className="project-chat-list">
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              className={conversation.id === activeConversationId ? "active" : ""}
              type="button"
              onClick={() => onOpenConversation(conversation.id)}
            >
              {conversation.title || "Untitled chat"}
            </button>
          ))}
        </div>
      )}
    </aside>
  );
}
