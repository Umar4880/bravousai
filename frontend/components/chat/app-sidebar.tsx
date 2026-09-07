"use client";

import { useState, useEffect } from "react";
import type { ResearchProject, WorkspaceView } from "./projects";
import type { AuthUser, ConversationSummary } from "../../lib/api";
import { LoadingScreen } from "./loading-screen";
import {
  LuPanelLeftClose,
  LuPanelLeftOpen,
  LuCirclePlus,
  LuSearch,
  LuChevronRight,
  LuChevronDown,
  LuPlus,
  LuEllipsisVertical,
  LuLogOut,
  LuSettings
} from "react-icons/lu";
import { SettingsModal } from "./settings-modal";

type AppSidebarProps = {
  authUser: AuthUser | null;
  projects: ResearchProject[];
  activeProjectId: string | null;
  activeView: WorkspaceView;
  isCollapsed: boolean;
  isLoadingProjects: boolean;
  projectSearch: string;
  onProjectSearchChange: (value: string) => void;
  onToggleCollapsed: () => void;
  onHome: () => void;
  onNewChat: () => void;
  onCreateProject: () => void;
  onOpenProject: (projectId: string) => void;
  onSignIn: () => void;
  onSignUp: () => void;
  onSignOut: () => void;

  // Props for project dropdown and action menu
  projectConversations: Record<string, ConversationSummary[]>;
  activeConversationId: string | null;
  onOpenConversation: (conversationId: string) => void;
  onNewChatInProject: (projectId: string) => void;
  onStartRenameProject: (project: ResearchProject) => void;
  onCommitRenameProject: (project: ResearchProject) => void;
  onCancelRenameProject: () => void;
  onDeleteProjectRequest: (project: ResearchProject) => void;
  renamingProjectId: string | null;
  renameProjectDraft: string;
  onRenameProjectDraftChange: (value: string) => void;
  isMutatingProject: boolean;

  // Props for chat action menu
  chatMenuId?: string | null;
  onToggleChatMenu?: (conversationId: string) => void;
  renamingChatId?: string | null;
  renameChatDraft?: string;
  onRenameChatDraftChange?: (value: string) => void;
  onStartRenameChat?: (chat: ConversationSummary) => void;
  onCommitRenameChat?: (chat: ConversationSummary) => void;
  onCancelRenameChat?: () => void;
  onDeleteChatRequest?: (chat: ConversationSummary) => void;
  isMutatingChat?: boolean;
};

export function AppSidebar({
  authUser,
  onSignIn,
  onSignUp,
  onSignOut,
  projects,
  activeProjectId,
  isCollapsed,
  isLoadingProjects,
  projectSearch,
  onProjectSearchChange,
  onToggleCollapsed,
  onHome,
  onCreateProject,
  onOpenProject,

  projectConversations,
  activeConversationId,
  onOpenConversation,
  onNewChatInProject,
  onStartRenameProject,
  onCommitRenameProject,
  onCancelRenameProject,
  onDeleteProjectRequest,
  renamingProjectId,
  renameProjectDraft,
  onRenameProjectDraftChange,
  isMutatingProject,

  chatMenuId,
  onToggleChatMenu,
  renamingChatId,
  renameChatDraft,
  onRenameChatDraftChange,
  onStartRenameChat,
  onCommitRenameChat,
  onCancelRenameChat,
  onDeleteChatRequest,
  isMutatingChat,
}: AppSidebarProps) {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const normalizedSearch = projectSearch.trim().toLowerCase();

  const visibleProjects = normalizedSearch
    ? projects.filter((project) =>
      `${project.title} ${project.description}`.toLowerCase().includes(normalizedSearch),
    )
    : projects;

  const [expandedProjectIds, setExpandedProjectIds] = useState<Set<string>>(() => new Set());
  const [projectMenuId, setProjectMenuId] = useState<string | null>(null);

  // Auto-expand active project dropdown
  useEffect(() => {
    if (activeProjectId) {
      setExpandedProjectIds((prev) => {
        const next = new Set(prev);
        next.add(activeProjectId);
        return next;
      });
    }
  }, [activeProjectId]);

  // Click away to close 3-dots menus
  useEffect(() => {
    const handleGlobalClick = () => {
      setProjectMenuId(null);
      if (onToggleChatMenu) {
        onToggleChatMenu(""); // Sending empty string clears chatMenuId if it was open
      }
    };
    window.addEventListener("click", handleGlobalClick);
    return () => window.removeEventListener("click", handleGlobalClick);
  }, [onToggleChatMenu]);

  const toggleProjectMenu = (projectId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setProjectMenuId((prev) => (prev === projectId ? null : projectId));
    if (onToggleChatMenu) onToggleChatMenu(""); // close chat menu if open
  };

  return (
    <aside className={`app-sidebar ${isCollapsed ? "collapsed" : ""}`} aria-label="Workspace navigation">
      <div className="sidebar-brand-row">
        <button
          className="sidebar-brand"
          type="button"
          onClick={onHome}
          aria-label="BravousAI home"
          suppressHydrationWarning={true}
        >
          {!isCollapsed && <strong>BravousAI</strong>}
        </button>
        <button
          className="sidebar-icon-button"
          type="button"
          onClick={onToggleCollapsed}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          title="Collaps Sidebar"
          suppressHydrationWarning={true}
        >
          <span>{isCollapsed ? <LuPanelLeftClose /> : <LuPanelLeftOpen />}</span>
        </button>
      </div>

      <nav className="sidebar-primary-nav" aria-label="Primary">
        <button
          style={isCollapsed ? { display: "flex", justifyContent: "center" } : {}}
          type="button"
          onClick={onCreateProject}
          title="New project"
          suppressHydrationWarning={true}
        >
          <LuCirclePlus />
          {!isCollapsed && "New Project"}
        </button>
      </nav>
      <nav className="sidebar-primary-nav" aria-label="Primary">
        <button
          style={isCollapsed ? { display: "flex", justifyContent: "center" } : {}}
          type="button"
          title="Search project"
          suppressHydrationWarning={true}
        >
          <LuSearch />

          {!isCollapsed && (
            <input
              className="sidebar-project-search"
              value={projectSearch}
              onChange={(event) => onProjectSearchChange(event.target.value)}
              placeholder="Search projects"
              suppressHydrationWarning={true}
            />
          )}
        </button>
      </nav>

      <section className="sidebar-projects">
        <div className="sidebar-section-title">
          {!isCollapsed && <span>Projects</span>}
        </div>
        <div className="sidebar-project-list">
          {(!isCollapsed && isLoadingProjects) ? (
            <LoadingScreen variant="sidebar" label="Loading projects" />
          ) : (
            visibleProjects.map((project) => {
              const isExpanded = expandedProjectIds.has(project.id);
              const conversations = projectConversations[project.id] || [];
              const isRenaming = renamingProjectId === project.id;
              const isActive = project.id === activeProjectId;

              return (
                <div key={project.id} className={`sidebar-project-item ${isActive ? "active" : ""}`}>
                  <div className="sidebar-project-header-row">
                    {/* Chevron Expansion Toggle */}
                    {!isCollapsed && (
                      <button
                        className="project-expand-button"
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedProjectIds((prev) => {
                            const next = new Set(prev);
                            if (next.has(project.id)) {
                              next.delete(project.id);
                            } else {
                              next.add(project.id);
                            }
                            return next;
                          });
                        }}
                        suppressHydrationWarning={true}
                      >
                        {isExpanded ? <LuChevronDown /> : <LuChevronRight />}
                      </button>
                    )}

                    {/* Inline Rename Input or Title button */}
                    {isRenaming ? (
                      <input
                        className="project-rename-input"
                        value={renameProjectDraft}
                        onChange={(e) => onRenameProjectDraftChange(e.target.value)}
                        onBlur={() => onCommitRenameProject(project)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            onCommitRenameProject(project);
                          }
                          if (e.key === "Escape") {
                            e.preventDefault();
                            onCancelRenameProject();
                          }
                        }}
                        autoFocus
                        disabled={isMutatingProject}
                        suppressHydrationWarning={true}
                      />
                    ) : (
                      <button
                        className="project-title-button"
                        type="button"
                        onClick={() => onOpenProject(project.id)}
                        title={project.title}
                        suppressHydrationWarning={true}
                      >
                        {!isCollapsed && <span>{project.title}</span>}
                        {isCollapsed && <span>{project.title.substring(0, 2).toUpperCase()}</span>}
                      </button>
                    )}

                    {/* Action buttons (New Chat inside project, and Options 3-dots) */}
                    {!isCollapsed && !isRenaming && (
                      <div className="project-action-buttons">
                        <button
                          className="project-action-btn"
                          type="button"
                          title="New Chat in project"
                          onClick={(e) => {
                            e.stopPropagation();
                            onNewChatInProject(project.id);
                          }}
                          suppressHydrationWarning={true}
                        >
                          <LuPlus />
                        </button>
                        <button
                          className="project-action-btn"
                          type="button"
                          title="Project options"
                          onClick={(e) => toggleProjectMenu(project.id, e)}
                          suppressHydrationWarning={true}
                        >
                          <LuEllipsisVertical />
                        </button>

                        {/* Dropdown 3-dots menu */}
                        {projectMenuId === project.id && (
                          <div className="project-dropdown-menu" role="menu">
                            <button
                              type="button"
                              role="menuitem"
                              onClick={(e) => {
                                e.stopPropagation();
                                setProjectMenuId(null);
                                onStartRenameProject(project);
                              }}
                              suppressHydrationWarning={true}
                            >
                              Rename
                            </button>
                            <button
                              className="danger"
                              type="button"
                              role="menuitem"
                              onClick={(e) => {
                                e.stopPropagation();
                                setProjectMenuId(null);
                                onDeleteProjectRequest(project);
                              }}
                              suppressHydrationWarning={true}
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Expanded Conversations List */}
                  {isExpanded && !isCollapsed && (
                    <div className="sidebar-project-chats">
                      {conversations.length === 0 ? (
                        <span className="sidebar-empty-chats">No chats yet</span>
                      ) : (
                        conversations.map((chat) => (
                          <div key={chat.id} className="sidebar-chat-item">
                            {renamingChatId === chat.id ? (
                              <input
                                className="chat-rename-input"
                                value={renameChatDraft}
                                onChange={(e) => onRenameChatDraftChange?.(e.target.value)}
                                onBlur={() => onCommitRenameChat?.(chat)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    e.preventDefault();
                                    onCommitRenameChat?.(chat);
                                  }
                                  if (e.key === "Escape") {
                                    e.preventDefault();
                                    onCancelRenameChat?.();
                                  }
                                }}
                                autoFocus
                                disabled={isMutatingChat}
                                suppressHydrationWarning={true}
                              />
                            ) : (
                              <>
                                <button
                                  className={`sidebar-chat-link ${chat.id === activeConversationId ? "active" : ""}`}
                                  type="button"
                                  onClick={() => onOpenConversation(chat.id)}
                                  title={chat.title || "Untitled chat"}
                                  suppressHydrationWarning={true}
                                >
                                  <span>{chat.title || "Untitled chat"}</span>
                                </button>
                                <button
                                  className="chat-action-btn"
                                  type="button"
                                  title="Chat options"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setProjectMenuId(null);
                                    onToggleChatMenu?.(chat.id);
                                  }}
                                  suppressHydrationWarning={true}
                                >
                                  <LuEllipsisVertical />
                                </button>
                                {chatMenuId === chat.id && (
                                  <div className="project-dropdown-menu chat-dropdown-menu" role="menu">
                                    <button
                                      type="button"
                                      role="menuitem"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        onToggleChatMenu?.("");
                                        onStartRenameChat?.(chat);
                                      }}
                                      suppressHydrationWarning={true}
                                    >
                                      Rename
                                    </button>
                                    <button
                                      className="danger"
                                      type="button"
                                      role="menuitem"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        onToggleChatMenu?.("");
                                        onDeleteChatRequest?.(chat);
                                      }}
                                      suppressHydrationWarning={true}
                                    >
                                      Delete
                                    </button>
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </section>

      <div className="sidebar-footer">
        {authUser ? (
          <>
            <div className="sidebar-user-strip" onClick={() => setIsSettingsOpen(true)} style={{ cursor: "pointer" }}>
              <div className="sidebar-user-avatar">
                <span className="user-initial">{authUser.username.charAt(0).toUpperCase()}</span>
                <span className="user-settings-icon"><LuSettings size={18} /></span>
              </div>
              {!isCollapsed && (
                <>
                  <div className="sidebar-user-info">
                    <strong>{authUser.username}</strong>
                    <small>Free plan</small>
                  </div>
                  <button
                    className="sidebar-logout-btn"
                    type="button"
                    onClick={(e) => { e.stopPropagation(); onSignOut(); }}
                    title="Sign out"
                    suppressHydrationWarning={true}
                  >
                    <LuLogOut size={16} />
                  </button>
                </>
              )}
            </div>
            <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
          </>
        ) : (
          <>
            <div className="sidebar-user-strip" onClick={() => setIsSettingsOpen(true)} style={{ cursor: "pointer" }}>
              <div className="sidebar-user-avatar">
                <span className="user-initial">?</span>
                <span className="user-settings-icon"><LuSettings size={18} /></span>
              </div>
              {!isCollapsed && (
                <div className="sidebar-user-info">
                  <strong>Guest</strong>
                  <button className="text-button" onClick={(e) => { e.stopPropagation(); onSignIn(); }}>Sign In</button>
                </div>
              )}
            </div>
            <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
          </>
        )}
      </div>
    </aside>
  );
}
