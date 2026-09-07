"use client";

import { type FormEvent, type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import {
  type AuthUser,
  type ChatArtifact,
  type ChatMode,
  type ChatStreamEvent,
  type ConversationSummary,
  createProject,
  deleteConversation,
  deleteProjectFile,
  getConversationMessages,
  getConversations,
  getProjects,
  renameConversation,
  streamResumeMessage,
  streamChatMessage,
  updateProjectInstructions,
  uploadProjectFile,
} from "../lib/api";
import { AuthModal } from "./chat/auth-modal";
import { AppSidebar } from "./chat/app-sidebar";
import { ChatComposer } from "./chat/chat-composer";
import { ConfirmDeleteModal } from "./chat/confirm-delete-modal";
import { ProjectDeleteModal } from "./chat/project-delete-modal";
import { ConversationList } from "./chat/conversation-list";
import { MessageList } from "./chat/message-list";
import { LoadingScreen } from "./chat/loading-screen";
import { ProjectChatSidebar } from "./chat/project-chat-sidebar";
import { ProjectContextPanel } from "./chat/project-context-panel";
import { ProjectCreateModal } from "./chat/project-create-modal";
import { ProjectHome } from "./chat/project-home";
import { LandingPage } from "./chat/landing-page";
import { ProjectHeader } from "./chat/project-header";
import {
  chatPath,
  parseAppRoute,
  projectHomePath,
  projectPath,
} from "./chat/routes";
import {
  ACTIVE_PROJECT_STORAGE_KEY,
  DEFAULT_PROJECTS,
  type ResearchProject,
  type WorkspaceView,
} from "./chat/projects";
import {
  AUTH_STORAGE_KEY,
  deleteInFlightWorkflowTrace,
  deleteStoredWorkflowTrace,
  readInFlightWorkflowTrace,
  readStoredAuthUser,
  readStoredWorkflowTraces,
  writeInFlightWorkflowTrace,
  writeStoredWorkflowTrace,
} from "./chat/storage";
import { currentTime, formatMessageTime } from "./chat/time";
import type { ChatMeta, InFlightWorkflowTrace, StoredWorkflowTrace, UiMessage, WorkflowStep } from "./chat/types";
import {
  isWorkflowTraceOpen,
  looksInternalWorkflowContent,
  normalizeTraceLine,
  shouldOpenWorkflowStep,
  sourceDomain,
  workflowLabel,
} from "./chat/workflow";

const FRESH_CHAT_PHRASES = [
  "What's up",
  "How is it going",
  "Let me know when you're ready",
  "What are we working on today",
  "Bring me the thing you came up with",
  "Ready when you are",
  "What should we explore first",
  "Tell me what is on your mind",
  "Let's research something",
  "What question are we chasing",
  "Drop the first idea here",
  "Where should we begin",
];

function pickFreshChatPhrase(): string {
  return FRESH_CHAT_PHRASES[Math.floor(Math.random() * FRESH_CHAT_PHRASES.length)];
}

function cleanRouteReason(rawReason: string): string {
  const withoutPrefix = rawReason
    .replace(/^Supervisor routed to\s+__?\w+__?\s*:?\s*/i, "")
    .replace(/^Supervisor routed to\s+\w+\s*:?\s*/i, "")
    .replace(/\*\*/g, "")
    .replace(/\s+/g, " ")
    .trim();

  if (!withoutPrefix) {
    return "Route reason was not provided.";
  }

  const firstSentence = withoutPrefix.split(/(?<=[.!?])\s+/)[0]?.trim() ?? withoutPrefix;
  return firstSentence.slice(0, 220);
}

function normalizeContent(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

export function ChatShell() {
  const router = useRouter();
  const pathname = usePathname();
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authMode, setAuthMode] = useState<"signin" | "signup" | null>(null);
  const [hasLoadedSession, setHasLoadedSession] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState<string>("");
  const [selectedMode, setSelectedMode] = useState<ChatMode>("instant");
  const [isModeMenuOpen, setIsModeMenuOpen] = useState<boolean>(false);
  const [chatMenuId, setChatMenuId] = useState<string | null>(null);
  const [renamingChatId, setRenamingChatId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState<string>("");
  const [deleteTarget, setDeleteTarget] = useState<ConversationSummary | null>(null);
  const [isMutatingChat, setIsMutatingChat] = useState<boolean>(false);
  const [freshChatPhrase, setFreshChatPhrase] = useState<string>(() => FRESH_CHAT_PHRASES[0]);
  const [isLoadingConversation, setIsLoadingConversation] = useState<boolean>(false);
  const [pendingConversationIds, setPendingConversationIds] = useState<Set<string>>(() => new Set());
  const [isPendingNewChat, setIsPendingNewChat] = useState<boolean>(false);
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>([]);
  const [liveAssistantContent, setLiveAssistantContent] = useState<string>("");
  const [isWaitingForFirstStreamEvent, setIsWaitingForFirstStreamEvent] = useState<boolean>(false);
  const [composerHeight, setComposerHeight] = useState<number>(48);
  const [error, setError] = useState<string>("");
  const [projects, setProjects] = useState<ResearchProject[]>([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [conversationsByProject, setConversationsByProject] = useState<Record<string, ConversationSummary[]>>({});
  const [renamingProjectId, setRenamingProjectId] = useState<string | null>(null);
  const [renameProjectDraft, setRenameProjectDraft] = useState<string>("");
  const [deleteProjectTarget, setDeleteProjectTarget] = useState<ResearchProject | null>(null);
  const [isMutatingProject, setIsMutatingProject] = useState<boolean>(false);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("home");
  const [isAppSidebarCollapsed, setIsAppSidebarCollapsed] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");
  const [isCreateProjectOpen, setIsCreateProjectOpen] = useState(false);
  const [projectTitleDraft, setProjectTitleDraft] = useState("");
  const [projectDescriptionDraft, setProjectDescriptionDraft] = useState("");
  const [clarificationQuestions, setClarificationQuestions] = useState<
    Array<{ question: string; guess_1: string; guess_2: string }> | null
  >(null);
  const [activeArtifact, setActiveArtifact] = useState<ChatArtifact | null>(null);
  const [artifactWidth, setArtifactWidth] = useState<number>(600);
  const [isResizing, setIsResizing] = useState(false);
  const [meta, setMeta] = useState<ChatMeta>({
    approved: false,
    routeReason: "No route decision yet.",
    iterationCount: 0,
    lastAgent: "idle",
    nextAgent: "supervisor",
    backendStage: "waiting for input",
  });

  const scrollAnchorRef = useRef<HTMLDivElement | null>(null);
  const composerInputRef = useRef<HTMLTextAreaElement | null>(null);
  const activeConversationIdRef = useRef<string | null>(null);
  const activeStreamConversationIdRef = useRef<string | null>(null);
  const activeStreamUserMessageIdRef = useRef<string | null>(null);
  const activeStreamTraceRef = useRef<InFlightWorkflowTrace | null>(null);
  const suppressRouteLoadForConversationRef = useRef<string | null>(null);
  const shouldAutoScrollRef = useRef(false);
  const instructionsSaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isResizingRef = useRef(false);

  const parsedRoute = useMemo(() => parseAppRoute(pathname), [pathname]);

  const routeConversationId = parsedRoute.type === "chat" ? parsedRoute.chatId : null;

  const activeProject = useMemo(() => {
    return projects.find((project) => project.id === activeProjectId) ?? projects[0] ?? null;
  }, [activeProjectId, projects]);

  const routeProjectId = parsedRoute.type === "project" ? parsedRoute.projectId : null;

  const isProjectViewLoading = Boolean(
    workspaceView === "project" &&
      (!hasLoadedSession ||
        (authUser && isLoadingProjects) ||
        (routeProjectId && !projects.some((project) => project.id === routeProjectId))),
  );

  const isChatViewLoading = Boolean(
    workspaceView === "chat" &&
      (isLoadingConversation ||
        (routeConversationId &&
          conversationId !== routeConversationId &&
          Boolean(authUser) &&
          !error)),
  );

  useEffect(() => {
    function handleMouseMove(e: MouseEvent) {
      if (!isResizingRef.current) return;
      const newWidth = document.body.clientWidth - e.clientX;
      if (newWidth >= 300 && newWidth <= 1200) {
        setArtifactWidth(newWidth);
      }
    }
    
    function handleMouseUp() {
      if (isResizingRef.current) {
        isResizingRef.current = false;
        setIsResizing(false);
        document.body.style.cursor = "default";
      }
    }
    
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  useEffect(() => {
    setAuthUser(readStoredAuthUser());
    const storedActiveProjectId = window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
    setProjects([]);
    setActiveProjectId(storedActiveProjectId);
    setHasLoadedSession(true);
    setFreshChatPhrase(pickFreshChatPhrase());
  }, []);

  useEffect(() => {
    return () => {
      if (instructionsSaveTimeoutRef.current) {
        clearTimeout(instructionsSaveTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!shouldAutoScrollRef.current) {
      return;
    }

    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
    shouldAutoScrollRef.current = false;
  }, [messages, pendingConversationIds, isPendingNewChat, workflowSteps, liveAssistantContent]);

  useEffect(() => {
    activeConversationIdRef.current = conversationId;
  }, [conversationId]);

  useEffect(() => {
    if (conversationId && (workflowSteps.length > 0 || liveAssistantContent)) {
      const trace = {
        steps: workflowSteps,
        answer: liveAssistantContent,
        artifact: activeStreamTraceRef.current?.trace.artifact ?? null,
      };
      writeStoredWorkflowTrace(conversationId, trace);
      if (activeStreamUserMessageIdRef.current) {
        writeStoredWorkflowTrace(activeStreamUserMessageIdRef.current, trace);
      }
    }
  }, [conversationId, workflowSteps, liveAssistantContent]);

  useEffect(() => {
    if (authUser) {
      setAuthMode(null);
      void loadProjects(authUser.user_id);
    }
  }, [authUser]);

  useEffect(() => {
    if (authUser && activeProjectId) {
      void loadConversations(authUser.user_id, activeProjectId);
    }
  }, [authUser, activeProjectId]);

  useEffect(() => {
    if (hasLoadedSession && activeProjectId) {
      window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, activeProjectId);
    }
  }, [activeProjectId, hasLoadedSession]);

  useEffect(() => {
    if (!hasLoadedSession) {
      return;
    }

    if (pathname === "/") {
      router.replace(projectHomePath());
      return;
    }

    if (parsedRoute.type === "home") {
      setWorkspaceView("home");
      return;
    }

    if (parsedRoute.type === "project") {
      setActiveProjectId(parsedRoute.projectId);
      setWorkspaceView((currentView) => {
        if (currentView === "chat" && !conversationId) {
          return "chat";
        }
        return "project";
      });

      if (conversationId) {
        setConversationId(null);
        setMessages([]);
        setWorkflowSteps([]);
        setLiveAssistantContent("");
        setIsWaitingForFirstStreamEvent(false);
      }
      return;
    }

    if (parsedRoute.type === "chat") {
      setWorkspaceView("chat");
    }
  }, [hasLoadedSession, pathname, parsedRoute, conversationId, router]);

  useEffect(() => {
    if (!authUser || !routeConversationId || routeConversationId === conversationId) {
      return;
    }

    if (suppressRouteLoadForConversationRef.current === routeConversationId) {
      suppressRouteLoadForConversationRef.current = null;
      return;
    }

    if (activeStreamConversationIdRef.current === routeConversationId) {
      setConversationId(routeConversationId);
      setWorkspaceView("chat");
      return;
    }

    void openConversation(routeConversationId, false);
  }, [authUser, routeConversationId, conversationId]);

  useEffect(() => {
    const input = composerInputRef.current;
    if (!input) {
      return;
    }

    input.style.height = "auto";
    const minHeight = 48;
    const maxHeight = 112;
    const nextHeight = Math.min(Math.max(input.scrollHeight, minHeight), maxHeight);
    input.style.height = `${nextHeight}px`;
    input.style.overflowY = input.scrollHeight > maxHeight ? "auto" : "hidden";
    setComposerHeight(nextHeight);
  }, [draft]);

  const isActiveSending = conversationId
    ? pendingConversationIds.has(conversationId)
    : isPendingNewChat;

  const canSend = useMemo(() => {
    return Boolean(draft.trim() && !isActiveSending && !isLoadingConversation);
  }, [draft, isActiveSending, isLoadingConversation]);

  const isFreshConversation = Boolean(
    hasLoadedSession &&
      messages.length === 0 &&
      !conversationId &&
      !isActiveSending &&
      !isLoadingConversation,
  );
  const isAuthModalOpen = Boolean(authMode && hasLoadedSession && !authUser);

  async function loadProjects(userId: string) {
    setIsLoadingProjects(true);

    try {
      const response = await getProjects(userId);
      const nextProjects = response.projects;
      setProjects(nextProjects);
      const storedActiveProjectId = window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
      const nextActiveProjectId =
        nextProjects.find((project) => project.id === activeProjectId)?.id ??
        nextProjects.find((project) => project.id === storedActiveProjectId)?.id ??
        nextProjects[0]?.id ??
        null;
      setActiveProjectId(nextActiveProjectId);
      if (nextProjects.length === 0) {
        setWorkspaceView("home");
      }

      // Load conversations for all projects in parallel
      const convoPromises = nextProjects.map(async (project) => {
        try {
          const convoRes = await getConversations(userId, project.id);
          return { projectId: project.id, conversations: convoRes.conversations };
        } catch (e) {
          console.error(`Failed to load conversations for project ${project.id}`, e);
          return { projectId: project.id, conversations: [] };
        }
      });
      const convoResults = await Promise.all(convoPromises);
      const mapping: Record<string, ConversationSummary[]> = {};
      for (const res of convoResults) {
        mapping[res.projectId] = res.conversations;
      }
      setConversationsByProject(mapping);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects.");
    } finally {
      setIsLoadingProjects(false);
    }
  }

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (conversationId) {
      clearConversationPending(conversationId);
    } else {
      setIsPendingNewChat(false);
    }
  };

  async function loadConversations(userId: string, projectId: string | null = activeProjectId) {
    if (!projectId) {
      setConversations([]);
      return;
    }

    setIsLoadingConversations(true);

    try {
      const response = await getConversations(userId, projectId);
      setConversations(response.conversations);
      setConversationsByProject((prev) => ({
        ...prev,
        [projectId]: response.conversations,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conversations.");
    } finally {
      setIsLoadingConversations(false);
    }
  }

  function markConversationPending(nextConversationId: string) {
    setPendingConversationIds((prev) => {
      const next = new Set(prev);
      next.add(nextConversationId);
      return next;
    });
  }

  function clearConversationPending(nextConversationId: string) {
    setPendingConversationIds((prev) => {
      const next = new Set(prev);
      next.delete(nextConversationId);
      return next;
    });
  }

  function isViewingConversation(nextConversationId: string | null | undefined): boolean {
    return Boolean(
      nextConversationId &&
        (activeConversationIdRef.current === nextConversationId ||
          activeStreamConversationIdRef.current === nextConversationId),
    );
  }

  function snapshotActiveStreamTrace(nextTrace?: StoredWorkflowTrace): InFlightWorkflowTrace | null {
    const conversationForStream = activeStreamConversationIdRef.current;
    if (!conversationForStream) {
      return null;
    }

    const snapshot: InFlightWorkflowTrace = {
      conversationId: conversationForStream,
      userMessageId: activeStreamUserMessageIdRef.current,
      trace: nextTrace ?? {
        steps: workflowSteps,
        answer: liveAssistantContent,
      },
      updatedAt: new Date().toISOString(),
      isRunning: true,
    };
    activeStreamTraceRef.current = snapshot;
    writeInFlightWorkflowTrace(snapshot);
    return snapshot;
  }

  function updateActiveStreamSteps(updater: (steps: WorkflowStep[]) => WorkflowStep[]) {
    const streamSnapshot = activeStreamTraceRef.current;
    const streamConversationId = activeStreamConversationIdRef.current;

    if (!streamSnapshot || !streamConversationId) {
      setWorkflowSteps(updater);
      return;
    }

    const nextSteps = updater(streamSnapshot.trace.steps);
    const nextTrace = {
      steps: nextSteps,
      answer: streamSnapshot.trace.answer,
      artifact: streamSnapshot.trace.artifact ?? null,
    };
    snapshotActiveStreamTrace(nextTrace);

    if (isViewingConversation(streamConversationId)) {
      setWorkflowSteps(nextSteps);
    }
  }

  function updateActiveStreamAnswer(updater: (answer: string) => string) {
    const streamSnapshot = activeStreamTraceRef.current;
    const streamConversationId = activeStreamConversationIdRef.current;

    if (!streamSnapshot || !streamConversationId) {
      setLiveAssistantContent(updater);
      return;
    }

    const nextAnswer = updater(streamSnapshot.trace.answer);
    const nextTrace = {
      steps: streamSnapshot.trace.steps,
      answer: nextAnswer,
      artifact: streamSnapshot.trace.artifact ?? null,
    };
    snapshotActiveStreamTrace(nextTrace);

    if (isViewingConversation(streamConversationId)) {
      setLiveAssistantContent(nextAnswer);
    }
  }

  function updateActiveStreamArtifact(artifact: ChatArtifact | null) {
    const streamSnapshot = activeStreamTraceRef.current;
    const streamConversationId = activeStreamConversationIdRef.current;

    if (!streamSnapshot || !streamConversationId) {
      return;
    }

    const nextTrace = {
      steps: streamSnapshot.trace.steps,
      answer: streamSnapshot.trace.answer,
      artifact,
    };
    snapshotActiveStreamTrace(nextTrace);
  }

  function upsertWorkflowStep(
    node: string,
    label: string,
    status: WorkflowStep["status"] = "active",
  ) {
    updateActiveStreamSteps((prev) => {
      const existing = prev.find((step) => step.node === node);
      if (existing) {
        return prev.map((step) =>
          step.node === node
            ? { ...step, label, status, isOpen: status === "active" }
            : status === "active"
              ? { ...step, isOpen: false }
              : step,
        );
      }

      const nextStep = {
        node,
        label,
        status,
        isOpen: status === "active" && shouldOpenWorkflowStep(node),
        content: "",
        sources: [],
      };

      return [
        ...prev.map((step) => ({ ...step, isOpen: false })),
        nextStep,
      ];
    });
  }

  function appendWorkflowContent(node: string, content: string) {
    if (!content || looksInternalWorkflowContent(content)) {
      return;
    }

    updateActiveStreamSteps((prev) =>
      prev.map((step) =>
        step.node === node
          ? {
              ...step,
              content: `${step.content}${step.content.endsWith("\n") || content.startsWith("\n") || !step.content ? "" : "\n"}${content}`,
              isOpen: step.status === "active" ? true : step.isOpen,
            }
          : step,
      ),
    );
  }

  function appendUniqueWorkflowContent(node: string, content: string) {
    if (!content || looksInternalWorkflowContent(content)) {
      return;
    }

    updateActiveStreamSteps((prev) =>
      prev.map((step) => {
        if (step.node !== node) {
          return step;
        }

        const existingLines = new Set(
          step.content
            .split("\n")
            .map(normalizeTraceLine)
            .filter(Boolean),
        );
        const nextLines = content
          .split("\n")
          .map((line) => line.trim())
          .filter((line) => line && !existingLines.has(normalizeTraceLine(line)));

        if (nextLines.length === 0) {
          return step;
        }

        const nextContent = nextLines.join("\n");
        return {
          ...step,
          content: `${step.content}${step.content.endsWith("\n") || !step.content ? "" : "\n"}${nextContent}`,
          isOpen: step.status === "active" ? true : step.isOpen,
        };
      }),
    );
  }

  function addWorkflowSource(
    event: Extract<ChatStreamEvent, { type: "research_source" | "search_result_found" }>,
  ) {
    updateActiveStreamSteps((prev) =>
      prev.map((step) => {
        if (step.node !== "research_search") {
          return step;
        }

        if (step.sources.some((source) => source.url === event.url)) {
          return step;
        }

        return {
          ...step,
          isOpen: true,
          sources: [
            ...step.sources,
            {
              id: `${event.url}-${step.sources.length}`,
              title: event.title || ("source" in event ? event.source : undefined) || event.url,
              url: event.url,
              favicon: "favicon" in event ? event.favicon : null,
              domain: sourceDomain(event.url, "domain" in event ? event.domain : null),
              sourceType: "source_type" in event ? event.source_type : null,
              query: event.query ?? null,
            },
          ],
        };
      }),
    );
  }

  async function openConversation(nextConversationId: string, updateUrl = true) {
    if (!authUser) {
      return;
    }

    setWorkspaceView("chat");
    if (nextConversationId === conversationId) {
      return;
    }

    setChatMenuId(null);
    setRenamingChatId(null);
    setIsLoadingConversation(true);
    setError("");

    try {
      const response = await getConversationMessages(authUser.user_id, nextConversationId);
      const storedTraces = readStoredWorkflowTraces();
      const inFlightTrace = readInFlightWorkflowTrace(nextConversationId);
      const fallbackTrace = inFlightTrace?.trace ?? response.trace ?? storedTraces[nextConversationId];
      const tracesByMessageId = {
        ...storedTraces,
        ...(response.traces ?? {}),
      };
      if (inFlightTrace?.userMessageId) {
        tracesByMessageId[inFlightTrace.userMessageId] = inFlightTrace.trace;
      }
      let lastUserMessageId = "";
      setConversationId(response.conversation.id);
      const lastTrace = fallbackTrace;
      if (lastTrace?.clarification_questions && lastTrace.clarification_questions.length > 0) {
        setClarificationQuestions(lastTrace.clarification_questions);
        setMeta((prev) => ({
          ...prev,
          nextAgent: "conversation",
          backendStage: "Waiting for your answer",
        }));
      } else {
        setClarificationQuestions(null);
      }
      if (response.conversation.project_id) {
        setActiveProjectId(response.conversation.project_id);
      }
      if (updateUrl) {
        window.history.replaceState(null, "", chatPath(response.conversation.id));
      }
      const shouldRestoreInFlightTrace = Boolean(inFlightTrace?.isRunning && fallbackTrace);
      setWorkflowSteps(shouldRestoreInFlightTrace ? fallbackTrace.steps : []);
      setLiveAssistantContent(shouldRestoreInFlightTrace ? fallbackTrace.answer : "");
      setIsWaitingForFirstStreamEvent(false);
      shouldAutoScrollRef.current = true;
      const mappedMessages: UiMessage[] = response.messages.map((message, index, messages) => {
        const role = (message.role === "user" ? "user" : "assistant") as "user" | "assistant";
        let trace: StoredWorkflowTrace | undefined;

        if (role === "user") {
          lastUserMessageId = message.id;
        } else if (lastUserMessageId) {
          trace = tracesByMessageId[lastUserMessageId];
        }

        const isLastAssistant = role === "assistant" && index === messages.length - 1;
        if (!trace && isLastAssistant && fallbackTrace) {
          trace = {
            ...fallbackTrace,
            answer: fallbackTrace.answer || message.content,
          };
        }
        if (trace) {
          trace = {
            ...trace,
            answer: trace.answer || message.content,
          };
        }

        return {
          id: message.id,
          role,
          content: trace ? "" : message.content,
          timestamp: formatMessageTime(message.created_at),
          trace,
        };
      });

      const filteredMessages = mappedMessages.filter(
        (message) => !(message.role === "user" && message.content.startsWith('{"answers":'))
      );

      setMessages(filteredMessages);

      let foundArtifact: ChatArtifact | null = null;
      for (let i = mappedMessages.length - 1; i >= 0; i--) {
        if (mappedMessages[i].trace?.artifact) {
          foundArtifact = mappedMessages[i].trace!.artifact!;
          break;
        }
      }
      setActiveArtifact(foundArtifact);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open conversation.");
    } finally {
      setIsLoadingConversation(false);
    }
  }

  function handleAuthenticated(user: AuthUser) {
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
    setAuthUser(user);
    setConversationId(null);
    router.push(projectHomePath());
    setMessages([]);
    setWorkflowSteps([]);
    setLiveAssistantContent("");
    setClarificationQuestions(null);
    setFreshChatPhrase(pickFreshChatPhrase());
    setError("");
    setAuthMode(null);
    setWorkspaceView("home");
  }

  function clearSession(message = "Your session expired. Please sign in again.") {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    window.localStorage.removeItem("gulzarsoft_user_id");
    setAuthUser(null);
    setConversationId(null);
    router.push(projectHomePath());
    setConversations([]);
    setMessages([]);
    setWorkflowSteps([]);
    setLiveAssistantContent("");
    setClarificationQuestions(null);
    setIsWaitingForFirstStreamEvent(false);
    setPendingConversationIds(new Set());
    setIsPendingNewChat(false);
    setError(message);
  }

  function handleSignOut() {
    clearSession("You have signed out.");
  }

  function updateProjects(updater: (currentProjects: ResearchProject[]) => ResearchProject[]) {
    setProjects((currentProjects) => {
      const nextProjects = updater(currentProjects);
      if (activeProjectId && !nextProjects.some((project) => project.id === activeProjectId)) {
        setActiveProjectId(nextProjects[0]?.id ?? null);
      }
      return nextProjects;
    });
  }

  function openHome() {
    setWorkspaceView("home");
    setConversationId(null);
    setMessages([]);
    setWorkflowSteps([]);
    setLiveAssistantContent("");
    setClarificationQuestions(null);
    setIsWaitingForFirstStreamEvent(false);
    router.push(projectHomePath());
  }

  function openProject(projectId: string) {
    setActiveProjectId(projectId);
    setWorkspaceView("project");
    setConversationId(null);
    setMessages([]);
    setWorkflowSteps([]);
    setLiveAssistantContent("");
    setIsWaitingForFirstStreamEvent(false);
    router.push(projectPath(projectId));
  }

  function startProjectChat() {
    if (!activeProject && projects[0]) {
      setActiveProjectId(projects[0].id);
    }
    resetConversation("chat");
  }

  async function createProjectFromDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = projectTitleDraft.trim();
    if (!title || !authUser) {
      if (!authUser) {
        setAuthMode("signin");
        setError("Please sign in to create a project.");
      }
      return;
    }

    try {
      const nextProject = await createProject({
        user_id: authUser.user_id,
        title,
        description: projectDescriptionDraft.trim(),
      });
      setProjects((currentProjects) => [nextProject, ...currentProjects]);
      setActiveProjectId(nextProject.id);
      setWorkspaceView("project");
      setProjectTitleDraft("");
      setProjectDescriptionDraft("");
      setIsCreateProjectOpen(false);
      router.push(projectPath(nextProject.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
    }
  }

  function updateActiveProjectInstructions(instructions: string) {
    if (!activeProject || !authUser) {
      return;
    }

    updateProjects((currentProjects) =>
      currentProjects.map((project) =>
        project.id === activeProject.id ? { ...project, instructions } : project,
      ),
    );

    if (instructionsSaveTimeoutRef.current) {
      clearTimeout(instructionsSaveTimeoutRef.current);
    }
    instructionsSaveTimeoutRef.current = setTimeout(() => {
      void updateProjectInstructions(authUser.user_id, activeProject.id, instructions)
        .then((updatedProject) => {
          setProjects((currentProjects) =>
            currentProjects.map((project) =>
              project.id === updatedProject.id ? updatedProject : project,
            ),
          );
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : "Failed to save project instructions.");
        });
    }, 500);
  }

  async function addActiveProjectFiles(files: File[]) {
    if (!activeProject || !authUser) {
      return;
    }

    try {
      const uploadedFiles = await Promise.all(
        files.map((file) => uploadProjectFile(authUser.user_id, activeProject.id, file)),
      );
      setProjects((currentProjects) =>
        currentProjects.map((project) =>
          project.id === activeProject.id
            ? { ...project, files: [...uploadedFiles, ...project.files] }
            : project,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload project file.");
    }
  }

  async function deleteActiveProjectFile(fileId: string) {
    if (!activeProject || !authUser) {
      return;
    }

    try {
      await deleteProjectFile(authUser.user_id, activeProject.id, fileId);
      setProjects((currentProjects) =>
        currentProjects.map((project) =>
          project.id === activeProject.id
            ? { ...project, files: project.files.filter((file) => file.id !== fileId) }
            : project,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete project file.");
    }
  }

  function startRename(conversation: ConversationSummary) {
    setChatMenuId(null);
    setRenamingChatId(conversation.id);
    setRenameDraft(conversation.title || "Untitled chat");
  }

  function cancelRename() {
    setRenamingChatId(null);
    setRenameDraft("");
  }

  async function commitRename(conversation: ConversationSummary) {
    if (!authUser || isMutatingChat || renamingChatId !== conversation.id) {
      return;
    }

    const nextTitle = renameDraft.split(/\s+/).join(" ").trim().slice(0, 128);
    if (!nextTitle || nextTitle === conversation.title) {
      cancelRename();
      return;
    }

    setIsMutatingChat(true);
    setRenamingChatId(null);
    setRenameDraft("");

    try {
      const updated = await renameConversation(authUser.user_id, conversation.id, nextTitle);
      const updatedTitle = updated.title;
      setConversations((prev) =>
        prev.map((item) =>
          item.id === conversation.id ? { ...item, title: updatedTitle } : item,
        ),
      );
      if (conversation.project_id) {
        setConversationsByProject((prev) => {
          const projectConvos = prev[conversation.project_id!] || [];
          return {
            ...prev,
            [conversation.project_id!]: projectConvos.map((item) =>
              item.id === conversation.id ? { ...item, title: updatedTitle } : item
            ),
          };
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename chat.");
      setRenamingChatId(conversation.id);
      setRenameDraft(nextTitle);
    } finally {
      setIsMutatingChat(false);
    }
  }

  async function confirmDeleteConversation() {
    if (!authUser || !deleteTarget || isMutatingChat) {
      return;
    }

    const targetId = deleteTarget.id;
    setIsMutatingChat(true);
    setError("");

    try {
      await deleteConversation(authUser.user_id, targetId);
      setConversations((prev) => prev.filter((conversation) => conversation.id !== targetId));
      if (deleteTarget.project_id) {
        setConversationsByProject((prev) => {
          const projectConvos = prev[deleteTarget.project_id!] || [];
          return {
            ...prev,
            [deleteTarget.project_id!]: projectConvos.filter((item) => item.id !== targetId),
          };
        });
      }
      deleteStoredWorkflowTrace(targetId);
      setPendingConversationIds((prev) => {
        const next = new Set(prev);
        next.delete(targetId);
        return next;
      });

      if (targetId === conversationId) {
        resetConversation();
      }

      setDeleteTarget(null);
      setChatMenuId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete chat.");
    } finally {
      setIsMutatingChat(false);
    }
  }

  function startRenameProject(project: ResearchProject) {
    setRenamingProjectId(project.id);
    setRenameProjectDraft(project.title);
  }

  function cancelRenameProject() {
    setRenamingProjectId(null);
    setRenameProjectDraft("");
  }

  async function commitRenameProject(project: ResearchProject) {
    if (!authUser || isMutatingProject || renamingProjectId !== project.id) {
      return;
    }

    const nextTitle = renameProjectDraft.split(/\s+/).join(" ").trim().slice(0, 160);
    if (!nextTitle || nextTitle === project.title) {
      cancelRenameProject();
      return;
    }

    setIsMutatingProject(true);
    setRenamingProjectId(null);
    setRenameProjectDraft("");

    try {
      const { updateProject } = await import("../lib/api");
      const updated = await updateProject(authUser.user_id, project.id, { title: nextTitle });
      setProjects((prev) =>
        prev.map((item) =>
          item.id === project.id ? { ...item, title: updated.title } : item,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename project.");
      setRenamingProjectId(project.id);
      setRenameProjectDraft(nextTitle);
    } finally {
      setIsMutatingProject(false);
    }
  }

  async function confirmDeleteProject() {
    if (!authUser || !deleteProjectTarget || isMutatingProject) {
      return;
    }

    const targetId = deleteProjectTarget.id;
    setIsMutatingProject(true);
    setError("");

    try {
      const { deleteProject } = await import("../lib/api");
      await deleteProject(authUser.user_id, targetId);
      setProjects((prev) => prev.filter((project) => project.id !== targetId));
      setConversationsByProject((prev) => {
        const next = { ...prev };
        delete next[targetId];
        return next;
      });

      if (targetId === activeProjectId) {
        setActiveProjectId(null);
        resetConversation("home");
      }

      setDeleteProjectTarget(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete project.");
    } finally {
      setIsMutatingProject(false);
    }
  }



  function handleNewChatInProject(projectId: string) {
    setActiveProjectId(projectId);
    resetConversation("chat");
  }

  function closeAuthModal() {
    setAuthMode(null);
  }

  async function handleQuery(
    query: string,
    addToHistory: boolean = true,
    isClarificationResume: boolean = false,
    isCheckpointResume: boolean = false
  ) {
    if (!query || isActiveSending || isLoadingConversation) {
      return;
    }

    if (!authUser?.user_id) {
      setAuthMode("signin");
      setError("Please sign in or create an account to start chatting.");
      return;
    }

    setWorkspaceView("chat");

    let userMessageClientId = "";
    if (addToHistory) {
      if (liveAssistantContent.trim()) {
        const completedAssistantMessage: UiMessage = {
          id: `${Date.now()}-assistant-complete`,
          role: "assistant",
          content: liveAssistantContent,
          timestamp: currentTime(),
          trace: {
            steps: workflowSteps,
            answer: liveAssistantContent,
            artifact: activeStreamTraceRef.current?.trace.artifact ?? null,
          },
        };
        setMessages((prev) => [...prev, completedAssistantMessage]);
      }

      let displayContent = query;
      if (query.startsWith('{"answers":')) {
        try {
          const parsed = JSON.parse(query);
          const ansList = parsed.answers;
          const lines = ["Here are my clarifications:"];
          if (clarificationQuestions && clarificationQuestions.length > 0) {
            clarificationQuestions.forEach((q, idx) => {
              lines.push(`**Q: ${q.question}**`);
              lines.push(`A: ${ansList[idx]}`);
            });
          } else {
            ansList.forEach((ans: string, idx: number) => {
              lines.push(`**Q${idx + 1}:** ${ans}`);
            });
          }
          displayContent = lines.join("\n");
        } catch (e) {
          console.error("Failed to parse clarification JSON", e);
        }
      }

      userMessageClientId = `${Date.now()}-user`;
      const userMessage: UiMessage = {
        id: userMessageClientId,
        role: "user",
        content: displayContent,
        timestamp: currentTime(),
      };
      shouldAutoScrollRef.current = true;
      setMessages((prev) => [...prev, userMessage]);
      setDraft("");
    }

    const requestConversationId = conversationId;
    const isNewConversationRequest = requestConversationId === null;
    let streamConversationId = requestConversationId;
    activeStreamConversationIdRef.current = requestConversationId;
    activeStreamUserMessageIdRef.current = null;
    setError("");

    if (!isClarificationResume && !isCheckpointResume) {
      setWorkflowSteps([]);
      setLiveAssistantContent("");
      activeStreamTraceRef.current = requestConversationId
        ? {
            conversationId: requestConversationId,
            userMessageId: null,
            trace: { steps: [], answer: "" },
            updatedAt: new Date().toISOString(),
            isRunning: true,
          }
        : null;
      if (requestConversationId) {
        deleteStoredWorkflowTrace(requestConversationId);
        deleteInFlightWorkflowTrace(requestConversationId);
        if (activeStreamTraceRef.current) {
          writeInFlightWorkflowTrace(activeStreamTraceRef.current);
        }
      }
    } else {
      setLiveAssistantContent("");
      if (activeStreamTraceRef.current) {
        activeStreamTraceRef.current.trace.answer = "";
        activeStreamTraceRef.current.isRunning = true;
        writeInFlightWorkflowTrace(activeStreamTraceRef.current);
      }
    }

    setIsWaitingForFirstStreamEvent(true);
    setMeta((prev) => ({
      ...prev,
      backendStage: "preparing to plan...",
      nextAgent: "supervisor",
    }));

    if (requestConversationId) {
      markConversationPending(requestConversationId);
    } else {
      setIsPendingNewChat(true);
    }

    abortControllerRef.current = new AbortController();

    try {
      const onEvent = (event: ChatStreamEvent) => {
          setIsWaitingForFirstStreamEvent(false);

          if (event.type === "conversation_created") {
            shouldAutoScrollRef.current = true;
            streamConversationId = event.conversation_id;
            activeStreamConversationIdRef.current = event.conversation_id;
            activeStreamUserMessageIdRef.current = event.user_message_id ?? null;
            activeStreamTraceRef.current = {
              conversationId: event.conversation_id,
              userMessageId: event.user_message_id ?? null,
              trace: activeStreamTraceRef.current?.trace ?? { steps: [], answer: "" },
              updatedAt: new Date().toISOString(),
              isRunning: true,
            };
            writeInFlightWorkflowTrace(activeStreamTraceRef.current);
            if (isNewConversationRequest) {
              suppressRouteLoadForConversationRef.current = event.conversation_id;
              setConversationId(event.conversation_id);
              activeConversationIdRef.current = event.conversation_id;
              window.history.replaceState(null, "", chatPath(event.conversation_id));
              
              const optimisticChat: ConversationSummary = {
                id: event.conversation_id,
                project_id: activeProject?.id ?? activeProjectId,
                title: "Generating...",
                created_at: new Date().toISOString(),
              };
              setConversations((prev) => [optimisticChat, ...prev]);
              const pId = activeProject?.id ?? activeProjectId;
              if (pId) {
                setConversationsByProject((prev) => ({
                  ...prev,
                  [pId]: [optimisticChat, ...(prev[pId] || [])],
                }));
              }

              markConversationPending(event.conversation_id);
              setIsPendingNewChat(false);
            }
            const realUserMessageId = event.user_message_id;
            if (realUserMessageId && userMessageClientId) {
              setMessages((prev) =>
                prev.map((message) =>
                  message.id === userMessageClientId
                    ? { ...message, id: realUserMessageId }
                    : message,
                ),
              );
            }
            return;
          }

          if (event.type === "node_start") {
            if (event.node === "researcher") {
              return;
            }
            if (event.node === "conversation") {
              upsertWorkflowStep(
                "conversation",
                event.message || "Understanding your request...",
                "active",
              );
              shouldAutoScrollRef.current = true;
              return;
            }
            upsertWorkflowStep(
              event.node,
              event.message || workflowLabel(event.node),
              "active",
            );
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "node_end") {
            if (event.node === "conversation") {
              if (event.content) {
                updateActiveStreamAnswer(() => event.content || "");
                shouldAutoScrollRef.current = true;
              }
              return;
            }
            if (event.node === "researcher") {
              return;
            }
            if (event.node === "presentation" && event.content) {
              updateActiveStreamAnswer(() => event.content || "");
            }
            upsertWorkflowStep(
              event.node,
              event.message || workflowLabel(event.node).replace("...", " complete."),
              "done",
            );
            shouldAutoScrollRef.current = true;
            if (event.content && event.node !== "writer" && event.node !== "supervisor") {
              appendWorkflowContent(event.node, event.content);
            }
            return;
          }

          if (event.type === "node_delta") {
            if (event.node === "conversation") {
              updateActiveStreamAnswer((current) => `${current}${event.content}`);
              shouldAutoScrollRef.current = true;
              return;
            }
            if (event.node === "writer") {
              updateActiveStreamAnswer((current) => `${current}${event.content}`);
              shouldAutoScrollRef.current = true;
              return;
            }
            if (event.node === "researcher") {
              appendWorkflowContent("research_synthesize", event.content);
            } else {
              appendWorkflowContent(event.node, event.content);
            }
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "workflow_plan") {
            upsertWorkflowStep("supervisor", event.message || "Planning workflow complete.", "done");
            appendWorkflowContent(
              "supervisor",
              event.message || "Workflow selected. I routed the request to the right specialist steps.",
            );
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "research_query") {
            upsertWorkflowStep("research_search", "Searching on internet...", "active");
            appendUniqueWorkflowContent("research_search", event.message || event.query);
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "search_query_started") {
            upsertWorkflowStep("research_search", "Searching on internet...", "active");
            appendUniqueWorkflowContent("research_search", `Searching for ${event.query}`);
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "search_query_completed") {
            upsertWorkflowStep("research_search", "Searching on internet...", "active");
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "search_result_found") {
            upsertWorkflowStep("research_search", "Searching on internet...", "active");
            addWorkflowSource(event);
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "research_source") {
            upsertWorkflowStep("research_search", "Searching on internet...", "active");
            addWorkflowSource(event);
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "source_selection_completed") {
            upsertWorkflowStep("source_extraction", "Selecting sources to read...", "active");
            appendWorkflowContent(
              "source_extraction",
              event.message || `Selected ${event.selected_sources} sources for deeper reading.`,
            );
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "source_extraction_started") {
            upsertWorkflowStep("source_extraction", "Reading selected sources...", "active");
            appendWorkflowContent(
              "source_extraction",
              event.message || `Reading ${event.selected_sources} selected sources.`,
            );
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "source_extraction_completed") {
            upsertWorkflowStep("source_extraction", "Reading selected sources complete.", "done");
            appendWorkflowContent(
              "source_extraction",
              event.message ||
                `Extracted ${event.successfully_extracted + event.partial} sources. ${event.failed + event.skipped} sources used snippets or could not be fully read.`,
            );
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "follow_up_research_started") {
            upsertWorkflowStep("follow_up_research", "Checking follow-up evidence...", "active");
            appendWorkflowContent(
              "follow_up_research",
              event.message ||
                `Checking ${event.approved_query_count} follow-up paths and skipping ${event.rejected_query_count} low-value paths.`,
            );
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "follow_up_search_completed") {
            upsertWorkflowStep("follow_up_research", "Checking follow-up evidence...", "active");
            appendWorkflowContent(
              "follow_up_research",
              event.message || `Received ${event.raw_results_received} follow-up search results.`,
            );
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "research_evidence_merged") {
            upsertWorkflowStep("follow_up_research", "Merging follow-up evidence...", "active");
            appendWorkflowContent(
              "follow_up_research",
              event.message ||
                `Added ${event.canonical_results_added} new canonical sources and removed ${event.duplicates_removed} duplicates. Total sources: ${event.total_canonical_sources}.`,
            );
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "research_loop_stopped") {
            upsertWorkflowStep("follow_up_research", "Follow-up evidence checked.", "done");
            appendWorkflowContent(
              "follow_up_research",
              event.message || `Follow-up stopped: ${event.stop_reason.replace(/_/g, " ")}.`,
            );
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "research_phase") {
            if (event.phase === "plan") {
              upsertWorkflowStep(
                "research_plan",
                event.message || "Planning research...",
                event.status === "done" ? "done" : "active",
              );
              if (event.content) {
                appendWorkflowContent("research_plan", `${event.content}\n`);
              }
            }
            if (event.phase === "search") {
              upsertWorkflowStep("research_search", event.message || "Searching on internet...", "active");
            }
            if (event.phase === "synthesize") {
              upsertWorkflowStep("research_synthesize", event.message || "Synthesizing result...", "active");
              if (event.content) {
                appendWorkflowContent("research_synthesize", `${event.content}\n`);
              }
            }
            shouldAutoScrollRef.current = true;
            return;
          }

          if (
            event.type === "artifact_persisted" &&
            typeof event.version_id === "string" &&
            typeof event.render_url === "string"
          ) {
            upsertWorkflowStep("presentation", "Building interactive artifact...", "done");
            updateActiveStreamArtifact({
              artifact_id: typeof event.artifact_id === "string" ? event.artifact_id : undefined,
              version_id: event.version_id,
              render_url: event.render_url,
              title: typeof event.title === "string" ? event.title : "Interactive artifact",
            });
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "presentation_planned") {
            if (event.artifact_kind && event.artifact_kind !== "none") {
              upsertWorkflowStep("presentation", "Building interactive artifact...", "active");
            }
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "artifact_generation_started") {
            upsertWorkflowStep("presentation", "Generating artifact layout...", "active");
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "clarification_question") {
            upsertWorkflowStep("conversation", "Clarifying your request...", "active");
            if (event.questions && event.questions.length > 0) {
              setClarificationQuestions(event.questions);
              updateActiveStreamAnswer(() => "Please answer the clarification questions to proceed.");
              const trace = activeStreamTraceRef.current;
              if (trace) {
                trace.trace.clarification_questions = event.questions;
                writeInFlightWorkflowTrace(trace);
              }
            } else {
              const questionText =
                event.total && event.total > 1
                  ? `**Question ${(event.index || 0) + 1} of ${event.total}:** ${event.question}`
                  : event.question || "";
              updateActiveStreamAnswer(() => questionText);
            }
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "clarification_planned") {
            upsertWorkflowStep("conversation", "Planning clarification questions...", "active");
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "clarification_completed") {
            upsertWorkflowStep("conversation", "Clarification complete.", "done");
            setClarificationQuestions(null);
            shouldAutoScrollRef.current = true;
            return;
          }

          if (event.type === "final") {
            streamConversationId = event.conversation_id;
            const finalAgent =
              typeof event.state?.last_agent === "string" ? event.state.last_agent : "";
            updateActiveStreamAnswer(() => event.answer);
            const finalSnapshot = activeStreamTraceRef.current;
            if (finalSnapshot) {
              const completedSnapshot = {
                ...finalSnapshot,
                trace: {
                  ...finalSnapshot.trace,
                  answer: event.answer,
                  artifact: event.artifact ?? finalSnapshot.trace.artifact ?? null,
                },
                updatedAt: new Date().toISOString(),
                isRunning: false,
              };
              activeStreamTraceRef.current = completedSnapshot;
              writeInFlightWorkflowTrace(completedSnapshot);
              if (!event.waiting_for_clarification) {
                writeStoredWorkflowTrace(event.conversation_id, completedSnapshot.trace);
                if (completedSnapshot.userMessageId) {
                  writeStoredWorkflowTrace(completedSnapshot.userMessageId, completedSnapshot.trace);
                }
              }
            }
            if (event.artifact) {
              setActiveArtifact(event.artifact);
            }
            shouldAutoScrollRef.current = true;
            
            // Clear live stream state so it doesn't render twice
            setWorkflowSteps([]);
            setLiveAssistantContent("");

            if (isViewingConversation(event.conversation_id)) {
              setMeta({
                approved: event.approved,
                routeReason: cleanRouteReason(event.route_reason || ""),
                iterationCount: event.iteration_count,
                lastAgent: finalAgent || "observer",
                nextAgent: event.waiting_for_clarification ? "conversation" : "end",
                backendStage: event.waiting_for_clarification
                  ? "Waiting for your answer"
                  : event.approved
                    ? "workflow approved"
                    : "workflow completed",
              });
            }
            if (!event.waiting_for_clarification) {
              void loadConversations(authUser.user_id, activeProjectId);
            }
          }
        };

      if (isCheckpointResume && requestConversationId) {
        await streamResumeMessage(
          { conversation_id: requestConversationId, user_id: authUser.user_id },
          onEvent,
          abortControllerRef.current.signal
        );
      } else {
        await streamChatMessage(
          {
            user_id: authUser.user_id,
            project_id: activeProject?.id ?? activeProjectId,
            query,
            mode: selectedMode,
            conversation_id: requestConversationId,
          },
          onEvent,
          abortControllerRef.current.signal
        );
      }
    } catch (submissionError) {
      const isAbortError =
        submissionError instanceof Error &&
        (submissionError.name === "AbortError" || submissionError.message.toLowerCase().includes("aborted"));

      const isStillViewingRequest =
        activeConversationIdRef.current === requestConversationId ||
        (isNewConversationRequest && activeConversationIdRef.current === null);

      if (isAbortError) {
        if (isStillViewingRequest) {
          setMeta((prev) => ({ ...prev, backendStage: "stopped" }));
          
          if (liveAssistantContent.trim() || workflowSteps.length > 0) {
            const finalSnapshot = activeStreamTraceRef.current;
            const completedAssistantMessage: UiMessage = {
              id: `${Date.now()}-assistant-stopped`,
              role: "assistant",
              content: liveAssistantContent,
              timestamp: currentTime(),
              trace: {
                steps: [...workflowSteps],
                answer: liveAssistantContent,
                artifact: finalSnapshot?.trace.artifact ?? null,
              },
            };
            setMessages((prev) => [...prev, completedAssistantMessage]);
          }
          setWorkflowSteps([]);
          setLiveAssistantContent("");
        }
        return;
      }

      const message =
        submissionError instanceof Error
          ? submissionError.message
          : "Failed to reach the API. Check if backend is running.";

      if (message.includes("401") || message.toLowerCase().includes("unauthorized")) {
        clearSession();
        return;
      }

      if (isStillViewingRequest) {
        setError(message);
        setMeta((prev) => ({
          ...prev,
          backendStage: "request failed",
        }));
      }
    } finally {
      if (streamConversationId) {
        clearConversationPending(streamConversationId);
      } else {
        setIsPendingNewChat(false);
      }
      activeStreamConversationIdRef.current = null;
      activeStreamUserMessageIdRef.current = null;
      setIsWaitingForFirstStreamEvent(false);
    }
  }

  function toggleWorkflowTrace() {
    setWorkflowSteps((prev) => {
      const nextOpen = !isWorkflowTraceOpen(prev);
      return prev.map((step) => ({ ...step, isOpen: nextOpen }));
    });
  }

  function toggleMessageTrace(messageId: string) {
    setMessages((prev) =>
      prev.map((message) => {
        if (message.id !== messageId || !message.trace) {
          return message;
        }

        const nextOpen = !isWorkflowTraceOpen(message.trace.steps);
        return {
          ...message,
          trace: {
            ...message.trace,
            steps: message.trace.steps.map((step) => ({ ...step, isOpen: nextOpen })),
          },
        };
      }),
    );
  }

  function toggleWorkflowTraceStepExpansion(node: string) {
    setWorkflowSteps((prev) =>
      prev.map((step) =>
        step.node === node ? { ...step, isExpanded: !step.isExpanded } : step,
      ),
    );
  }

  function toggleMessageTraceStepExpansion(messageId: string, node: string) {
    setMessages((prev) =>
      prev.map((message) => {
        if (message.id !== messageId || !message.trace) {
          return message;
        }

        return {
          ...message,
          trace: {
            ...message.trace,
            steps: message.trace.steps.map((step) =>
              step.node === node ? { ...step, isExpanded: !step.isExpanded } : step,
            ),
          },
        };
      }),
    );
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    handleQuery(draft.trim(), true);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }

    event.preventDefault();
    if (canSend) {
      event.currentTarget.form?.requestSubmit();
    }
  }

  function handleReexecute() {
    const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");
    if (lastUserMessage) {
      // Remove the last assistant message before re-executing
      setMessages((prev) => {
        const lastIndex = prev.length - 1;
        if (lastIndex >= 0 && prev[lastIndex].role === "assistant") {
          return prev.slice(0, lastIndex);
        }
        return prev;
      });
      handleQuery(lastUserMessage.content, true);
    }
  }

  async function handleClarificationSubmit(answers: string[]) {
    setClarificationQuestions(null);
    const jsonAnswers = JSON.stringify({ answers });
    await handleQuery(jsonAnswers, false, true);
  }

  async function handleResume() {
    console.log("Attempting to resume conversation with ID:", conversationId);
    if (!conversationId) return;

    handleQuery("", false, false, true);
  }

  function resetConversation(nextView: WorkspaceView = "project") {
    setConversationId(null);
    setMessages([]);
    setWorkflowSteps([]);
    setLiveAssistantContent("");
    setActiveArtifact(null);
    setClarificationQuestions(null);
    setIsWaitingForFirstStreamEvent(false);
    setFreshChatPhrase(pickFreshChatPhrase());
    setMeta({
      approved: false,
      routeReason: "No route decision yet.",
      iterationCount: 0,
      lastAgent: "idle",
      nextAgent: "supervisor",
      backendStage: "waiting for input",
    });
    setError("");
    setWorkspaceView(nextView);

    const projectId = activeProjectId ?? activeProject?.id ?? null;
    if ((nextView === "chat" || nextView === "project") && projectId) {
      router.push(projectPath(projectId));
      return;
    }
    router.push(projectHomePath());
  }

  if (!hasLoadedSession) {
    return <LoadingScreen label="Loading..." />;
  }

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
        onToggleCollapsed={() => setIsAppSidebarCollapsed((isCollapsed) => !isCollapsed)}
        onHome={openHome}
        onNewChat={startProjectChat}
        onCreateProject={() => {
          if (!authUser) {
            setAuthMode("signin");
            return;
          }
          setIsCreateProjectOpen(true);
        }}
        onOpenProject={openProject}
        onSignIn={() => setAuthMode("signin")}
        onSignUp={() => setAuthMode("signup")}
        onSignOut={handleSignOut}
        projectConversations={conversationsByProject}
        activeConversationId={conversationId}
        onOpenConversation={(nextConversationId) => void openConversation(nextConversationId)}
        onNewChatInProject={handleNewChatInProject}
        onStartRenameProject={startRenameProject}
        onCommitRenameProject={commitRenameProject}
        onCancelRenameProject={cancelRenameProject}
        onDeleteProjectRequest={(project) => setDeleteProjectTarget(project)}
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
        onDeleteChatRequest={(chat) => setDeleteTarget(chat)}
        isMutatingChat={isMutatingChat}
      />

      <div className={`console-shell ${isAppSidebarCollapsed ? "with-collapsed-sidebar" : ""}`}>
        {workspaceView === "home" && (
          authUser && isLoadingProjects ? (
            <LoadingScreen label="Loading projects..." />
          ) : authUser ? (
            <ProjectHome
              projects={projects}
              searchValue={projectSearch}
              onSearchChange={setProjectSearch}
              onOpenProject={openProject}
              onCreateProject={() => {
                if (!authUser) {
                  setAuthMode("signin");
                  return;
                }
                setIsCreateProjectOpen(true);
              }}
            />
          ) : (
            <LandingPage
              onSignIn={() => setAuthMode("signin")}
              onSignUp={() => setAuthMode("signup")}
            />
          )
        )}

        {workspaceView === "project" && isProjectViewLoading && (
          <LoadingScreen label="Loading project..." />
        )}

        {workspaceView === "project" && !isProjectViewLoading && activeProject && (
          <>
            <section className="project-workspace fresh-chat-panel">
              <ProjectHeader
                authUser={authUser}
                project={activeProject}
                onBack={openHome}
                onSignIn={() => setAuthMode("signin")}
                onSignUp={() => setAuthMode("signup")}
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
                isFreshConversation={isFreshConversation}
                inputRef={composerInputRef}
                onDraftChange={setDraft}
                onModeChange={setSelectedMode}
                onModeMenuToggle={() => setIsModeMenuOpen((isOpen) => !isOpen)}
                onModeMenuClose={() => setIsModeMenuOpen(false)}
                onSubmit={onSubmit}
                onKeyDown={handleComposerKeyDown}
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
                onOpenConversation={(nextConversationId) => void openConversation(nextConversationId)}
                onToggleMenu={(nextConversationId) =>
                  setChatMenuId((currentId) => (currentId === nextConversationId ? null : nextConversationId))
                }
                onStartRename={startRename}
                onCancelRename={cancelRename}
                onCommitRename={(conversation) => void commitRename(conversation)}
                onRenameDraftChange={setRenameDraft}
                onDeleteRequest={(conversation) => {
                  setChatMenuId(null);
                  setDeleteTarget(conversation);
                }}
              />
            </section>

            <ProjectContextPanel
              authUser={authUser}
              conversations={conversations}
              meta={meta}
              activeConversationId={conversationId}
              pendingCount={pendingConversationIds.size + (isPendingNewChat ? 1 : 0)}
              project={activeProject}
              onInstructionsChange={updateActiveProjectInstructions}
              onFilesAdded={addActiveProjectFiles}
              onFileDelete={deleteActiveProjectFile}
            />
          </>
        )}

        {workspaceView === "chat" && isChatViewLoading && (
          <div className="project-chat-screen">
            <LoadingScreen label="Loading chat..." />
          </div>
        )}

        {workspaceView === "chat" && !isChatViewLoading && activeProject && (
          <div className={`project-chat-screen ${activeArtifact ? "has-artifact" : ""}`}>
            <section className="chat-workspace">
              <MessageList
                messages={messages}
                workflowSteps={workflowSteps}
                liveAssistantContent={liveAssistantContent}
                liveArtifact={activeStreamTraceRef.current?.trace.artifact ?? null}
                isWaitingForFirstStreamEvent={isWaitingForFirstStreamEvent}
                error={error}
                scrollAnchorRef={scrollAnchorRef}
                onReexecute={handleReexecute}
                onResume={handleResume}
                onToggleWorkflowTrace={toggleWorkflowTrace}
                onToggleMessageTrace={toggleMessageTrace}
                onToggleWorkflowStepExpansion={toggleWorkflowTraceStepExpansion}
                onToggleMessageTraceStepExpansion={toggleMessageTraceStepExpansion}
                clarificationQuestions={clarificationQuestions}
                onClarificationSubmit={handleClarificationSubmit}
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
                onModeMenuToggle={() => setIsModeMenuOpen((isOpen) => !isOpen)}
                onModeMenuClose={() => setIsModeMenuOpen(false)}
                onSubmit={onSubmit}
                onKeyDown={handleComposerKeyDown}
                onStop={handleStop}
                disabled={clarificationQuestions !== null && clarificationQuestions.length > 0}
                placeholder={
                  clarificationQuestions !== null && clarificationQuestions.length > 0
                    ? "Please answer the clarification questions above..."
                    : "Type your message here..."
                }
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
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                        <line x1="3" y1="9" x2="21" y2="9"></line>
                        <line x1="9" y1="21" x2="9" y2="9"></line>
                      </svg>
                      <h3>{activeArtifact.title || "Interactive Artifact"}</h3>
                    </div>
                    <div className="artifact-header-actions">
                      <button className="artifact-header-btn" title="Copy contents">
                        <span>Copy</span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="9 11 12 14 22 4"></polyline>
                          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
                        </svg>
                      </button>
                      <button className="artifact-header-icon-btn" onClick={() => {
                        const iframe = document.querySelector('.artifact-iframe') as HTMLIFrameElement;
                        if (iframe) iframe.src = iframe.src;
                      }} title="Reload">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="23 4 23 10 17 10"></polyline>
                          <polyline points="1 20 1 14 7 14"></polyline>
                          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                        </svg>
                      </button>
                      <button className="artifact-header-icon-btn" onClick={() => setActiveArtifact(null)} title="Close">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <line x1="18" y1="6" x2="6" y2="18"></line>
                          <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                      </button>
                    </div>
                  </div>
                  <div className="artifact-iframe-wrapper">
                    <iframe src={activeArtifact.render_url} title={activeArtifact.title} className="artifact-iframe" style={{ pointerEvents: isResizing ? 'none' : 'auto' }} />
                  </div>
                </section>
              </>
            )}
          </div>
        )}
      </div>

      {isAuthModalOpen && authMode && (
        <AuthModal
          mode={authMode}
          error={error}
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
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => void confirmDeleteConversation()}
        />
      )}

      {deleteProjectTarget && (
        <ProjectDeleteModal
          project={deleteProjectTarget}
          isMutating={isMutatingProject}
          onCancel={() => setDeleteProjectTarget(null)}
          onConfirm={() => void confirmDeleteProject()}
        />
      )}

      <ProjectCreateModal
        isOpen={isCreateProjectOpen}
        title={projectTitleDraft}
        description={projectDescriptionDraft}
        onTitleChange={setProjectTitleDraft}
        onDescriptionChange={setProjectDescriptionDraft}
        onCancel={() => setIsCreateProjectOpen(false)}
        onSubmit={createProjectFromDraft}
      />
    </main>
  );
}
