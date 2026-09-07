"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "../hooks/use-auth";
import { useProjects } from "../hooks/use-projects";
import { useConversations } from "../hooks/use-conversations";
import { useChatStream } from "../hooks/use-chat-stream";

import { AppSidebar } from "./chat/app-sidebar";
import { AuthModal } from "./chat/auth-modal";
import { ChatComposer } from "./chat/chat-composer";
import { ConfirmDeleteModal } from "./chat/confirm-delete-modal";
import { ProjectDeleteModal } from "./chat/project-delete-modal";
import { ConversationList } from "./chat/conversation-list";
import { LandingPage } from "./chat/landing-page";
import { LoadingScreen } from "./chat/loading-screen";
import { MessageList } from "./chat/message-list";
import { ProjectContextPanel } from "./chat/project-context-panel";
import { ProjectCreateModal } from "./chat/project-create-modal";
import { ProjectHome } from "./chat/project-home";
import { ProjectHeader } from "./chat/project-header";

import {
  chatPath,
  parseAppRoute,
  projectHomePath,
  projectPath,
} from "./chat/routes";
import type { WorkspaceView } from "./chat/projects";

export function ChatShellV2() {
  const pathname = usePathname();
  const router = useRouter();

  // Navigation / layout state
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("home");
  const [isAppSidebarCollapsed, setIsAppSidebarCollapsed] = useState(false);
  const [artifactWidth, setArtifactWidth] = useState(520);
  const [isResizing, setIsResizing] = useState(false);
  const isResizingRef = useRef(false);

  // 1. Auth Hook
  const {
    authUser,
    authMode,
    isAuthModalOpen,
    hasLoadedSession,
    authError,
    setAuthMode,
    openSignIn,
    openSignUp,
    closeAuthModal,
    handleAuthenticated,
    handleSignOut,
  } = useAuth();

  // 2. Projects Hook
  const {
    projects,
    activeProjectId,
    activeProject,
    isLoadingProjects,
    projectSearch,
    setProjectSearch,
    setActiveProjectId,
    isCreateProjectOpen,
    projectTitleDraft,
    projectDescriptionDraft,
    setProjectTitleDraft,
    setProjectDescriptionDraft,
    openCreateModal,
    closeCreateModal,
    createProjectFromDraft,
    renamingProjectId,
    renameProjectDraft,
    setRenameProjectDraft,
    startRenameProject,
    cancelRenameProject,
    commitRenameProject,
    deleteProjectTarget,
    isMutatingProject,
    requestDeleteProject,
    cancelDeleteProject,
    confirmDeleteProject,
    updateActiveProjectInstructions,
    addActiveProjectFiles,
    deleteActiveProjectFile,
  } = useProjects(authUser);

  // 3. Conversations Hook
  const handleOpenConversationRoute = useCallback(
    (targetId: string) => {
      setWorkspaceView("chat");
      router.push(chatPath(targetId));
    },
    [router],
  );

  const {
    conversations,
    conversationsByProject,
    conversationId,
    setConversationId,
    isLoadingConversations,
    isMutatingChat,
    chatMenuId,
    setChatMenuId,
    renamingChatId,
    renameDraft,
    setRenameDraft,
    deleteTarget,
    pendingConversationIds,
    loadConversations,
    loadAllProjectConversations,
    openConversation,
    startRename,
    cancelRename,
    commitRename,
    requestDelete,
    cancelDelete,
    confirmDelete,
  } = useConversations(authUser, activeProjectId, handleOpenConversationRoute);

  // 4. Chat Streaming Hook
  const handleConversationCreated = useCallback(
    (newId: string) => {
      setConversationId(newId);
      window.history.replaceState(null, "", chatPath(newId));
      if (activeProjectId) {
        void loadConversations(activeProjectId);
      }
    },
    [activeProjectId, loadConversations, setConversationId],
  );

  const handleStreamFinished = useCallback(() => {
    if (activeProjectId) {
      void loadConversations(activeProjectId);
    }
  }, [activeProjectId, loadConversations]);

  const {
    messages,
    liveAssistantContent,
    liveAssistantIntro,
    liveReasoning,
    isThinking,
    reasoningDuration,
    workflowSteps,
    activeArtifact,
    meta,
    error,
    isLoadingConversation,
    isWaitingForFirstStreamEvent,
    isActiveSending,
    draft,
    selectedMode,
    isModeMenuOpen,
    composerHeight,
    composerInputRef,
    scrollAnchorRef,
    setDraft,
    setSelectedMode,
    setIsModeMenuOpen,
    setActiveArtifact,
    loadConversation,
    sendMessage,
    stopGeneration,
    reexecute,
    resetChat,
    toggleWorkflowTrace,
    toggleMessageTrace,
    toggleWorkflowTraceStepExpansion,
    toggleMessageTraceStepExpansion,
    handleComposerKeyDown,
    handleComposerSubmit,
  } = useChatStream({
    authUser,
    activeProjectId,
    activeConversationId: conversationId,
    onConversationCreated: handleConversationCreated,
    onStreamFinished: handleStreamFinished,
  });

  // Load conversations for sidebar projects when projects are ready
  useEffect(() => {
    if (projects.length > 0 && authUser) {
      void loadAllProjectConversations(projects.map((p) => p.id));
    }
  }, [projects, authUser, loadAllProjectConversations]);

  // Route Synchronization
  useEffect(() => {
    if (!hasLoadedSession) return;

    const parsed = parseAppRoute(pathname);

    if (parsed.type === "home") {
      setWorkspaceView("home");
      setConversationId(null);
      resetChat();
      return;
    }

    if (parsed.type === "project") {
      setActiveProjectId(parsed.projectId);
      setWorkspaceView("project");
      setConversationId(null);
      resetChat();
      return;
    }

    if (parsed.type === "chat") {
      setWorkspaceView("chat");
      if (parsed.chatId !== conversationId) {
        setConversationId(parsed.chatId);
        void loadConversation(parsed.chatId);
      }
    }
  }, [
    pathname,
    hasLoadedSession,
    conversationId,
    resetChat,
    setActiveProjectId,
    setConversationId,
    loadConversation,
  ]);

  // Navigation handlers
  const handleOpenHome = useCallback(() => {
    setWorkspaceView("home");
    setConversationId(null);
    resetChat();
    router.push(projectHomePath());
  }, [resetChat, router, setConversationId]);

  const handleOpenProject = useCallback(
    (projId: string) => {
      setActiveProjectId(projId);
      setWorkspaceView("project");
      setConversationId(null);
      resetChat();
      router.push(projectPath(projId));
    },
    [resetChat, router, setActiveProjectId, setConversationId],
  );

  const handleStartProjectChat = useCallback(() => {
    resetChat();
    setConversationId(null);
    setWorkspaceView("chat");
    const projId = activeProjectId ?? projects[0]?.id;
    if (projId) {
      setActiveProjectId(projId);
    }
  }, [activeProjectId, projects, resetChat, setActiveProjectId, setConversationId]);

  const handleNewChatInProject = useCallback(
    (projId: string) => {
      setActiveProjectId(projId);
      resetChat();
      setConversationId(null);
      setWorkspaceView("chat");
    },
    [resetChat, setActiveProjectId, setConversationId],
  );

  // Resize handle drag logic for Artifact panel
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingRef.current) return;
      const newWidth = window.innerWidth - e.clientX;
      if (newWidth >= 360 && newWidth <= window.innerWidth - 420) {
        setArtifactWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      if (isResizingRef.current) {
        isResizingRef.current = false;
        setIsResizing(false);
        document.body.style.cursor = "default";
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  if (!hasLoadedSession) {
    return <LoadingScreen label="Loading..." />;
  }

  const canSend = Boolean(draft.trim() && !isActiveSending && !isLoadingConversation);

  return (
    <main className="console-root">
      <AppSidebar
        authUser={authUser}
        projects={projects}
        activeProjectId={activeProjectId}
        activeView={workspaceView}
        isCollapsed={isAppSidebarCollapsed}
        isLoadingProjects={Boolean(authUser && isLoadingProjects)}
        projectSearch={projectSearch}
        onProjectSearchChange={setProjectSearch}
        onToggleCollapsed={() => setIsAppSidebarCollapsed((prev) => !prev)}
        onHome={handleOpenHome}
        onNewChat={handleStartProjectChat}
        onCreateProject={() => {
          if (!authUser) {
            openSignIn();
            return;
          }
          openCreateModal();
        }}
        onOpenProject={handleOpenProject}
        onSignIn={openSignIn}
        onSignUp={openSignUp}
        onSignOut={handleSignOut}
        projectConversations={conversationsByProject}
        activeConversationId={conversationId}
        onOpenConversation={(nextId) => {
          openConversation(nextId);
          handleOpenConversationRoute(nextId);
        }}
        onNewChatInProject={handleNewChatInProject}
        onStartRenameProject={startRenameProject}
        onCommitRenameProject={commitRenameProject}
        onCancelRenameProject={cancelRenameProject}
        onDeleteProjectRequest={requestDeleteProject}
        renamingProjectId={renamingProjectId}
        renameProjectDraft={renameProjectDraft}
        onRenameProjectDraftChange={setRenameProjectDraft}
        isMutatingProject={isMutatingProject}
        chatMenuId={chatMenuId}
        onToggleChatMenu={(id) => setChatMenuId((prev) => (prev === id ? null : id))}
        renamingChatId={renamingChatId}
        renameChatDraft={renameDraft}
        onRenameChatDraftChange={setRenameDraft}
        onStartRenameChat={startRename}
        onCommitRenameChat={commitRename}
        onCancelRenameChat={cancelRename}
        onDeleteChatRequest={requestDelete}
        isMutatingChat={isMutatingChat}
      />

      <div className={`console-shell ${isAppSidebarCollapsed ? "with-collapsed-sidebar" : ""}`}>
        {/* VIEW 1: HOME */}
        {workspaceView === "home" &&
          (authUser && isLoadingProjects ? (
            <LoadingScreen label="Loading projects..." />
          ) : authUser ? (
            <ProjectHome
              projects={projects}
              searchValue={projectSearch}
              onSearchChange={setProjectSearch}
              onOpenProject={handleOpenProject}
              onCreateProject={openCreateModal}
            />
          ) : (
            <LandingPage onSignIn={openSignIn} onSignUp={openSignUp} />
          ))}

        {/* VIEW 2: PROJECT OVERVIEW */}
        {workspaceView === "project" && activeProject && (
          <>
            <section className="project-workspace fresh-chat-panel">
              <ProjectHeader
                authUser={authUser}
                project={activeProject}
                onBack={handleOpenHome}
                onSignIn={openSignIn}
                onSignUp={openSignUp}
                onSignOut={handleSignOut}
              />

              <ChatComposer
                draft={draft}
                selectedMode={selectedMode}
                isModeMenuOpen={isModeMenuOpen}
                canSend={canSend}
                isActiveSending={isActiveSending}
                isLoadingConversation={isLoadingConversation}
                composerHeight={composerHeight}
                isFreshConversation={true}
                inputRef={composerInputRef}
                onDraftChange={setDraft}
                onModeChange={setSelectedMode}
                onModeMenuToggle={() => setIsModeMenuOpen((prev) => !prev)}
                onModeMenuClose={() => setIsModeMenuOpen(false)}
                onSubmit={(e) => {
                  setWorkspaceView("chat");
                  handleComposerSubmit(e);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && canSend) {
                    setWorkspaceView("chat");
                  }
                  handleComposerKeyDown(e);
                }}
              />

              <ConversationList
                authUserExists={Boolean(authUser)}
                conversations={conversations}
                activeConversationId={conversationId}
                pendingConversationIds={pendingConversationIds}
                isLoadingConversations={isLoadingConversations}
                chatMenuId={chatMenuId}
                renamingChatId={renamingChatId}
                renameDraft={renameDraft}
                isMutatingChat={isMutatingChat}
                onOpenConversation={(nextId) => {
                  openConversation(nextId);
                  handleOpenConversationRoute(nextId);
                }}
                onToggleMenu={(nextId) =>
                  setChatMenuId((currentId) => (currentId === nextId ? null : nextId))
                }
                onStartRename={startRename}
                onCancelRename={cancelRename}
                onCommitRename={(c) => void commitRename(c)}
                onRenameDraftChange={setRenameDraft}
                onDeleteRequest={requestDelete}
              />
            </section>

            <ProjectContextPanel
              authUser={authUser}
              conversations={conversations}
              meta={meta}
              activeConversationId={conversationId}
              pendingCount={pendingConversationIds.size}
              project={activeProject}
              onInstructionsChange={updateActiveProjectInstructions}
              onFilesAdded={addActiveProjectFiles}
              onFileDelete={deleteActiveProjectFile}
            />
          </>
        )}

        {/* VIEW 3: CHAT VIEW */}
        {workspaceView === "chat" && isLoadingConversation && (
          <div className="project-chat-screen">
            <LoadingScreen label="Loading chat..." />
          </div>
        )}

        {workspaceView === "chat" && !isLoadingConversation && (
          <div className={`project-chat-screen ${activeArtifact ? "has-artifact" : ""}`}>
            <section className="chat-workspace">
              <MessageList
                messages={messages}
                workflowSteps={workflowSteps}
                liveAssistantContent={liveAssistantContent}
                liveAssistantIntro={liveAssistantIntro}
                liveReasoning={liveReasoning}
                isThinking={isThinking}
                reasoningDuration={reasoningDuration}
                liveArtifact={activeArtifact}
                isWaitingForFirstStreamEvent={isWaitingForFirstStreamEvent}
                error={error}
                scrollAnchorRef={scrollAnchorRef}
                onReexecute={reexecute}
                onResume={() => {}}
                onToggleWorkflowTrace={toggleWorkflowTrace}
                onToggleMessageTrace={toggleMessageTrace}
                onToggleWorkflowStepExpansion={toggleWorkflowTraceStepExpansion}
                onToggleMessageTraceStepExpansion={toggleMessageTraceStepExpansion}
                onArtifactClick={setActiveArtifact}
              />

              <ChatComposer
                draft={draft}
                selectedMode={selectedMode}
                isModeMenuOpen={isModeMenuOpen}
                canSend={canSend}
                isActiveSending={isActiveSending}
                isLoadingConversation={isLoadingConversation}
                composerHeight={composerHeight}
                isFreshConversation={false}
                inputRef={composerInputRef}
                onDraftChange={setDraft}
                onModeChange={setSelectedMode}
                onModeMenuToggle={() => setIsModeMenuOpen((prev) => !prev)}
                onModeMenuClose={() => setIsModeMenuOpen(false)}
                onSubmit={handleComposerSubmit}
                onKeyDown={handleComposerKeyDown}
                onStop={stopGeneration}
                placeholder="Type your message here..."
              />
            </section>

            {activeArtifact && (
              <>
                <div
                  className="resize-handle"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    isResizingRef.current = true;
                    setIsResizing(true);
                    document.body.style.cursor = "col-resize";
                  }}
                  style={{ cursor: "col-resize" }}
                />
                <section className="artifact-panel" style={{ width: artifactWidth }}>
                  <div className="artifact-header">
                    <div className="artifact-header-left">
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                        <line x1="3" y1="9" x2="21" y2="9" />
                        <line x1="9" y1="21" x2="9" y2="21" />
                      </svg>
                      <h3>{activeArtifact.title || "Interactive Artifact"}</h3>
                    </div>
                    <div className="artifact-header-actions">
                      <button
                        className="artifact-header-btn"
                        title="Copy contents"
                        onClick={() => {
                          if (navigator.clipboard) {
                            void navigator.clipboard.writeText(activeArtifact.render_url);
                          }
                        }}
                      >
                        <span>Copy</span>
                        <svg
                          width="12"
                          height="12"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                        >
                          <polyline points="9 11 12 14 22 4" />
                          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                        </svg>
                      </button>
                      <button
                        className="artifact-header-icon-btn"
                        onClick={() => {
                          const iframe = document.querySelector(
                            ".artifact-iframe",
                          ) as HTMLIFrameElement;
                          if (iframe) iframe.src = iframe.src;
                        }}
                        title="Reload"
                      >
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                        >
                          <polyline points="23 4 23 10 17 10" />
                          <polyline points="1 20 1 14 7 14" />
                          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                        </svg>
                      </button>
                      <button
                        className="artifact-header-icon-btn"
                        onClick={() => setActiveArtifact(null)}
                        title="Close"
                      >
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                        >
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  <div className="artifact-iframe-wrapper">
                    <iframe
                      src={activeArtifact.render_url}
                      title={activeArtifact.title}
                      className="artifact-iframe"
                      style={{ pointerEvents: isResizing ? "none" : "auto" }}
                    />
                  </div>
                </section>
              </>
            )}
          </div>
        )}
      </div>

      {/* Modals */}
      {isAuthModalOpen && authMode && (
        <AuthModal
          mode={authMode}
          error={authError}
          onClose={closeAuthModal}
          onAuthenticated={handleAuthenticated}
          onShowSignin={() => setAuthMode("signin")}
          onShowSignup={() => setAuthMode("signup")}
        />
      )}

      {deleteTarget && (
        <ConfirmDeleteModal
          conversation={deleteTarget}
          isMutating={isMutatingChat}
          onCancel={cancelDelete}
          onConfirm={() => void confirmDelete(resetChat)}
        />
      )}

      {deleteProjectTarget && (
        <ProjectDeleteModal
          project={deleteProjectTarget}
          isMutating={isMutatingProject}
          onCancel={cancelDeleteProject}
          onConfirm={() => void confirmDeleteProject()}
        />
      )}

      <ProjectCreateModal
        isOpen={isCreateProjectOpen}
        title={projectTitleDraft}
        description={projectDescriptionDraft}
        onTitleChange={setProjectTitleDraft}
        onDescriptionChange={setProjectDescriptionDraft}
        onCancel={closeCreateModal}
        onSubmit={(e) => {
          e.preventDefault();
          void createProjectFromDraft().then((newId) => {
            if (newId) {
              router.push(projectPath(newId));
            }
          });
        }}
      />
    </main>
  );
}
