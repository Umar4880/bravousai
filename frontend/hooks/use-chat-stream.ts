"use client";

import {
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  type AuthUser,
  type ChatArtifact,
  type ChatMode,
  type ChatStreamEvent,
  getConversationMessages,
  streamChatMessage,
} from "../lib/chat-api";
import {
  deleteInFlightWorkflowTrace,
  readInFlightWorkflowTrace,
  readStoredWorkflowTraces,
  writeInFlightWorkflowTrace,
  writeStoredWorkflowTrace,
} from "../components/chat/storage";
import { currentTime, formatMessageTime } from "../components/chat/time";
import type {
  ChatMeta,
  InFlightWorkflowTrace,
  StoredWorkflowTrace,
  UiMessage,
  WorkflowStep,
} from "../components/chat/types";
import {
  isWorkflowTraceOpen,
  looksInternalWorkflowContent,
  normalizeTraceLine,
  sourceDomain,
  workflowLabel,
} from "../components/chat/workflow";

const DEFAULT_META: ChatMeta = {
  approved: false,
  routeReason: "Direct agent response",
  iterationCount: 0,
  lastAgent: "agent",
  nextAgent: "end",
  backendStage: "ready",
};

export function useChatStream({
  authUser,
  activeProjectId,
  activeConversationId,
  onConversationCreated,
  onStreamFinished,
}: {
  authUser: AuthUser | null;
  activeProjectId: string | null;
  activeConversationId: string | null;
  onConversationCreated?: (newId: string) => void;
  onStreamFinished?: () => void;
}) {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [liveAssistantContent, setLiveAssistantContent] = useState("");
  const [liveAssistantIntro, setLiveAssistantIntro] = useState("");
  const [liveReasoning, setLiveReasoning] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [reasoningDuration, setReasoningDuration] = useState<number | undefined>(undefined);
  const thinkingStartTimeRef = useRef<number | null>(null);
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>([]);
  const [activeArtifact, setActiveArtifact] = useState<ChatArtifact | null>(null);
  const [meta, setMeta] = useState<ChatMeta>(DEFAULT_META);
  const [error, setError] = useState("");

  const [isLoadingConversation, setIsLoadingConversation] = useState(false);
  const [isWaitingForFirstStreamEvent, setIsWaitingForFirstStreamEvent] = useState(false);
  const [isActiveSending, setIsActiveSending] = useState(false);

  // Composer
  const [draft, setDraft] = useState("");
  const [selectedMode, setSelectedMode] = useState<ChatMode>("instant");
  const [isModeMenuOpen, setIsModeMenuOpen] = useState(false);
  const [composerHeight, setComposerHeight] = useState(48);

  const composerInputRef = useRef<HTMLTextAreaElement | null>(null);
  const scrollAnchorRef = useRef<HTMLDivElement | null>(null);
  const shouldAutoScrollRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // In-flight stream state refs
  const activeStreamConversationIdRef = useRef<string | null>(null);
  const activeStreamUserMessageIdRef = useRef<string | null>(null);
  const activeStreamTraceRef = useRef<InFlightWorkflowTrace | null>(null);

  // Auto-scroll when messages or streaming content changes
  useEffect(() => {
    if (!shouldAutoScrollRef.current) return;
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
    shouldAutoScrollRef.current = false;
  }, [messages, workflowSteps, liveAssistantContent, liveAssistantIntro, liveReasoning, isActiveSending]);

  // Composer input auto-height
  useEffect(() => {
    const input = composerInputRef.current;
    if (!input) return;

    input.style.height = "auto";
    const minHeight = 48;
    const maxHeight = 112;
    const nextHeight = Math.min(Math.max(input.scrollHeight, minHeight), maxHeight);
    input.style.height = `${nextHeight}px`;
    input.style.overflowY = input.scrollHeight > maxHeight ? "auto" : "hidden";
    setComposerHeight(nextHeight);
  }, [draft]);

  // Workflow helpers
  const upsertWorkflowStep = useCallback(
    (node: string, label: string, status: "active" | "done") => {
      setWorkflowSteps((prev) => {
        const index = prev.findIndex((s) => s.node === node);
        if (index === -1) {
          return [
            ...prev,
            {
              node,
              label,
              status,
              isOpen: status === "active",
              content: "",
              sources: [],
            },
          ];
        }
        return prev.map((step, i) =>
          i === index
            ? {
                ...step,
                label,
                status,
                isOpen: status === "active" ? true : step.isOpen,
              }
            : step,
        );
      });
    },
    [],
  );

  const appendWorkflowContent = useCallback((node: string, content: string) => {
    if (!content) return;
    setWorkflowSteps((prev) =>
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
  }, []);

  const appendUniqueWorkflowContent = useCallback((node: string, content: string) => {
    if (!content || looksInternalWorkflowContent(content)) return;
    setWorkflowSteps((prev) =>
      prev.map((step) => {
        if (step.node !== node) return step;

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

        if (nextLines.length === 0) return step;

        return {
          ...step,
          content: `${step.content}${step.content.endsWith("\n") || !step.content ? "" : "\n"}${nextLines.join("\n")}`,
          isOpen: step.status === "active" ? true : step.isOpen,
        };
      }),
    );
  }, []);

  const addWorkflowSource = useCallback(
    (event: Extract<ChatStreamEvent, { type: "research_source" | "search_result_found" }>) => {
      setWorkflowSteps((prev) =>
        prev.map((step) => {
          if (step.node !== "research_search") return step;
          if (step.sources.some((s) => s.url === event.url)) return step;

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
    },
    [],
  );

  // Load conversation messages
  const loadConversation = useCallback(
    async (targetConversationId: string) => {
      if (!authUser) return;

      setIsLoadingConversation(true);
      setError("");

      try {
        const response = await getConversationMessages(authUser.user_id, targetConversationId);
        const storedTraces = readStoredWorkflowTraces();
        const inFlightTrace = readInFlightWorkflowTrace(targetConversationId);
        const fallbackTrace =
          inFlightTrace?.trace ?? response.trace ?? storedTraces[targetConversationId];

        const tracesByMessageId = {
          ...storedTraces,
          ...(response.traces ?? {}),
        };
        if (inFlightTrace?.userMessageId) {
          tracesByMessageId[inFlightTrace.userMessageId] = inFlightTrace.trace;
        }

        let lastUserMessageId = "";
        const mappedMessages: UiMessage[] = response.messages.map((msg, index, arr) => {
          const role = (msg.role === "user" ? "user" : "assistant") as "user" | "assistant";
          let trace: StoredWorkflowTrace | undefined;

          if (role === "user") {
            lastUserMessageId = msg.id;
          } else if (lastUserMessageId) {
            trace = tracesByMessageId[lastUserMessageId];
          }

          const isLastAssistant = role === "assistant" && index === arr.length - 1;
          if (!trace && isLastAssistant && fallbackTrace) {
            trace = {
              ...fallbackTrace,
              answer: fallbackTrace.answer || msg.content,
            };
          }

          return {
            id: msg.id,
            role,
            content: trace ? "" : msg.content,
            timestamp: formatMessageTime(msg.created_at),
            trace,
            reasoning: trace?.reasoning,
            reasoningDuration: trace?.reasoningDuration,
            intro: trace?.intro,
          };
        });

        setMessages(mappedMessages);

        // Find artifact in messages if any
        let foundArtifact: ChatArtifact | null = null;
        for (let i = mappedMessages.length - 1; i >= 0; i--) {
          if (mappedMessages[i].trace?.artifact) {
            foundArtifact = mappedMessages[i].trace!.artifact!;
            break;
          }
        }
        setActiveArtifact(foundArtifact);

        // Restore in-flight state if still running
        if (inFlightTrace?.isRunning && fallbackTrace) {
          setWorkflowSteps(fallbackTrace.steps);
          setLiveAssistantContent(fallbackTrace.answer);
        } else {
          setWorkflowSteps([]);
          setLiveAssistantContent("");
        }

        shouldAutoScrollRef.current = true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load messages.");
      } finally {
        setIsLoadingConversation(false);
      }
    },
    [authUser],
  );

  // Send message & stream response
  const sendMessage = useCallback(
    async (queryText?: string) => {
      const textToSend = (queryText ?? draft).trim();
      if (!textToSend || isActiveSending || !authUser) return;

      setDraft("");
      setError("");
      setIsActiveSending(true);
      setIsWaitingForFirstStreamEvent(true);
      setLiveAssistantContent("");
      setLiveAssistantIntro("");
      setLiveReasoning("");
      setIsThinking(false);
      setReasoningDuration(undefined);
      thinkingStartTimeRef.current = null;
      setWorkflowSteps([]);

      const userMsgId = `user-${Date.now()}`;
      const userMessage: UiMessage = {
        id: userMsgId,
        role: "user",
        content: textToSend,
        timestamp: currentTime(),
      };

      setMessages((prev) => [...prev, userMessage]);
      shouldAutoScrollRef.current = true;

      const requestConversationId = activeConversationId;
      activeStreamConversationIdRef.current = requestConversationId;
      activeStreamUserMessageIdRef.current = userMsgId;

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      let currentAssistantIntro = "";
      let currentAssistantAnswer = "";
      let currentAssistantReasoning = "";
      let currentReasoningDuration: number | undefined = undefined;
      let hasDispatchedTools = false;
      let currentWorkflowSteps: WorkflowStep[] = [];
      let currentArtifact: ChatArtifact | null = null;

      try {
        await streamChatMessage({
          payload: {
            user_id: authUser.user_id,
            project_id: activeProjectId,
            query: textToSend,
            mode: selectedMode,
            conversation_id: requestConversationId,
          },
          signal: abortController.signal,
          onEvent: (event: ChatStreamEvent) => {
            setIsWaitingForFirstStreamEvent(false);

            if (event.type === "conversation_created") {
              activeStreamConversationIdRef.current = event.conversation_id;
              if (event.user_message_id) {
                setMessages((prev) =>
                  prev.map((m) => (m.id === userMsgId ? { ...m, id: event.user_message_id! } : m)),
                );
              }
              onConversationCreated?.(event.conversation_id);
              return;
            }

            if (event.type === "reasoning_delta") {
              if (!thinkingStartTimeRef.current) {
                thinkingStartTimeRef.current = Date.now();
              }
              currentAssistantReasoning += event.content;
              setLiveReasoning((prev) => prev + event.content);
              setIsThinking(true);
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "node_delta") {
              if (thinkingStartTimeRef.current) {
                const dur = Math.max(1, Math.round((Date.now() - thinkingStartTimeRef.current) / 1000));
                currentReasoningDuration = dur;
                setReasoningDuration(dur);
                thinkingStartTimeRef.current = null;
              }
              setIsThinking(false);

              if (!hasDispatchedTools) {
                currentAssistantIntro += event.content;
                setLiveAssistantIntro((prev) => prev + event.content);
              } else {
                currentAssistantAnswer += event.content;
                setLiveAssistantContent((prev) => prev + event.content);
              }
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "node_start") {
              if (event.node !== "agent") {
                hasDispatchedTools = true;
              }
              const label = event.message || workflowLabel(event.node);
              upsertWorkflowStep(event.node, label, "active");
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "node_end") {
              const label =
                event.message || workflowLabel(event.node).replace("...", " complete.");
              upsertWorkflowStep(event.node, label, "done");
              if (event.content) {
                appendWorkflowContent(event.node, event.content);
              }
              shouldAutoScrollRef.current = true;
              return;
            }

            // Deep research telemetry
            if (event.type === "research_query" || event.type === "search_query_started") {
              upsertWorkflowStep("research_search", "Searching on internet...", "active");
              appendUniqueWorkflowContent("research_search", event.query);
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "search_result_found" || event.type === "research_source") {
              upsertWorkflowStep("research_search", "Searching on internet...", "active");
              addWorkflowSource(event);
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "source_selection_completed") {
              upsertWorkflowStep("source_extraction", "Selecting sources to read...", "active");
              appendWorkflowContent(
                "source_extraction",
                event.message || `Selected ${event.selected_sources} sources.`,
              );
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "source_extraction_started") {
              upsertWorkflowStep("source_extraction", "Reading selected sources...", "active");
              appendWorkflowContent(
                "source_extraction",
                event.message || `Reading ${event.selected_sources} sources.`,
              );
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "source_extraction_completed") {
              upsertWorkflowStep("source_extraction", "Reading selected sources complete.", "done");
              appendWorkflowContent(
                "source_extraction",
                event.message || `Extracted ${event.successfully_extracted} sources.`,
              );
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "follow_up_research_started") {
              upsertWorkflowStep("follow_up_research", "Checking follow-up evidence...", "active");
              appendWorkflowContent(
                "follow_up_research",
                event.message || `Checking ${event.approved_query_count} paths.`,
              );
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "research_loop_stopped") {
              upsertWorkflowStep("follow_up_research", "Follow-up evidence checked.", "done");
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "research_phase") {
              hasDispatchedTools = true;
              if (event.phase === "plan") {
                upsertWorkflowStep("research_plan", event.message || "Planning research...", event.status === "done" ? "done" : "active");
              } else if (event.phase === "search") {
                upsertWorkflowStep("research_search", event.message || "Searching...", "active");
              } else if (event.phase === "synthesize") {
                upsertWorkflowStep("research_synthesize", event.message || "Synthesizing findings...", "active");
              }
              if (event.content) {
                appendWorkflowContent(`research_${event.phase}`, `${event.content}\n`);
              }
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "artifact_persisted" && event.render_url) {
              const art: ChatArtifact = {
                artifact_id: event.artifact_id,
                version_id: event.version_id || "v1",
                render_url: event.render_url,
                title: event.title || "Interactive Artifact",
              };
              currentArtifact = art;
              setActiveArtifact(art);
              upsertWorkflowStep("presentation", "Building interactive artifact...", "done");
              shouldAutoScrollRef.current = true;
              return;
            }

            if (event.type === "final") {
              setIsThinking(false);
              if (thinkingStartTimeRef.current) {
                const dur = Math.max(1, Math.round((Date.now() - thinkingStartTimeRef.current) / 1000));
                currentReasoningDuration = dur;
                setReasoningDuration(dur);
                thinkingStartTimeRef.current = null;
              }

              const finalAnswer = hasDispatchedTools
                ? (event.answer || currentAssistantAnswer)
                : (event.answer || currentAssistantIntro || currentAssistantAnswer);
              const finalIntro = hasDispatchedTools ? (currentAssistantIntro || undefined) : undefined;
              const finalReasoning = event.reasoning || currentAssistantReasoning || undefined;
              const finalDuration = currentReasoningDuration;
              const cid = event.conversation_id || activeStreamConversationIdRef.current || "";

              setWorkflowSteps((latestSteps) => {
                currentWorkflowSteps = latestSteps;
                return latestSteps;
              });

              const storedTrace: StoredWorkflowTrace | undefined =
                currentWorkflowSteps.length > 0 || finalReasoning
                  ? {
                      steps: currentWorkflowSteps,
                      intro: finalIntro,
                      answer: finalAnswer,
                      artifact: event.artifact ?? currentArtifact ?? null,
                      reasoning: finalReasoning,
                      reasoningDuration: finalDuration,
                    }
                  : undefined;

              if (cid && storedTrace) {
                writeStoredWorkflowTrace(cid, storedTrace);
                if (activeStreamUserMessageIdRef.current) {
                  writeStoredWorkflowTrace(activeStreamUserMessageIdRef.current, storedTrace);
                }
              }

              const assistantMessage: UiMessage = {
                id: `assistant-${Date.now()}`,
                role: "assistant",
                content: storedTrace ? "" : finalAnswer,
                intro: finalIntro,
                timestamp: currentTime(),
                trace: storedTrace,
                reasoning: finalReasoning,
                reasoningDuration: finalDuration,
              };

              setMessages((prev) => [...prev, assistantMessage]);
              setLiveAssistantContent("");
              setLiveAssistantIntro("");
              setLiveReasoning("");
              setWorkflowSteps([]);

              setMeta({
                approved: event.approved,
                routeReason: event.route_reason || "Direct agent response",
                iterationCount: event.iteration_count,
                lastAgent: "agent",
                nextAgent: "end",
                backendStage: "completed",
              });

              if (event.artifact) {
                setActiveArtifact(event.artifact);
              }

              onStreamFinished?.();
              shouldAutoScrollRef.current = true;
            }
          },
        });
      } catch (err: unknown) {
        const isAbort =
          err instanceof Error &&
          (err.name === "AbortError" || err.message.toLowerCase().includes("aborted"));

        if (isAbort) {
          setMeta((prev) => ({ ...prev, backendStage: "stopped" }));
          if (currentAssistantAnswer.trim() || workflowSteps.length > 0 || currentAssistantReasoning.trim()) {
            const assistantMsg: UiMessage = {
              id: `assistant-stopped-${Date.now()}`,
              role: "assistant",
              content: currentAssistantAnswer,
              timestamp: currentTime(),
              reasoning: currentAssistantReasoning || undefined,
              trace:
                workflowSteps.length > 0 || currentAssistantReasoning.trim()
                  ? {
                      steps: [...workflowSteps],
                      answer: currentAssistantAnswer,
                      artifact: currentArtifact,
                      reasoning: currentAssistantReasoning || undefined,
                    }
                  : undefined,
            };
            setMessages((prev) => [...prev, assistantMsg]);
          }
        } else {
          setError(err instanceof Error ? err.message : "Request failed.");
          setMeta((prev) => ({ ...prev, backendStage: "error" }));
        }

        setLiveAssistantContent("");
        setLiveReasoning("");
        setIsThinking(false);
        setWorkflowSteps([]);
      } finally {
        setIsActiveSending(false);
        setIsWaitingForFirstStreamEvent(false);
        abortControllerRef.current = null;
        activeStreamConversationIdRef.current = null;
        activeStreamUserMessageIdRef.current = null;
      }
    },
    [
      draft,
      isActiveSending,
      authUser,
      activeProjectId,
      activeConversationId,
      selectedMode,
      upsertWorkflowStep,
      appendWorkflowContent,
      appendUniqueWorkflowContent,
      addWorkflowSource,
      onConversationCreated,
      onStreamFinished,
      workflowSteps,
    ],
  );

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const reexecute = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;

    // Remove last assistant message if present
    setMessages((prev) => {
      const lastIndex = prev.length - 1;
      if (lastIndex >= 0 && prev[lastIndex].role === "assistant") {
        return prev.slice(0, lastIndex);
      }
      return prev;
    });

    void sendMessage(lastUser.content);
  }, [messages, sendMessage]);

  // Trace toggling
  const toggleWorkflowTrace = useCallback(() => {
    setWorkflowSteps((prev) => {
      const nextOpen = !isWorkflowTraceOpen(prev);
      return prev.map((step) => ({ ...step, isOpen: nextOpen }));
    });
  }, []);

  const toggleMessageTrace = useCallback((messageId: string) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== messageId || !msg.trace) return msg;
        const nextOpen = !isWorkflowTraceOpen(msg.trace.steps);
        return {
          ...msg,
          trace: {
            ...msg.trace,
            steps: msg.trace.steps.map((s) => ({ ...s, isOpen: nextOpen })),
          },
        };
      }),
    );
  }, []);

  const toggleWorkflowTraceStepExpansion = useCallback((node: string) => {
    setWorkflowSteps((prev) =>
      prev.map((step) =>
        step.node === node ? { ...step, isExpanded: !step.isExpanded } : step,
      ),
    );
  }, []);

  const toggleMessageTraceStepExpansion = useCallback(
    (messageId: string, node: string) => {
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id !== messageId || !msg.trace) return msg;
          return {
            ...msg,
            trace: {
              ...msg.trace,
              steps: msg.trace.steps.map((s) =>
                s.node === node ? { ...s, isExpanded: !s.isExpanded } : s,
              ),
            },
          };
        }),
      );
    },
    [],
  );

  const handleComposerKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key !== "Enter" || event.shiftKey) return;
      event.preventDefault();
      if (draft.trim() && !isActiveSending && !isLoadingConversation) {
        void sendMessage();
      }
    },
    [draft, isActiveSending, isLoadingConversation, sendMessage],
  );

  const handleComposerSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (draft.trim() && !isActiveSending && !isLoadingConversation) {
        void sendMessage();
      }
    },
    [draft, isActiveSending, isLoadingConversation, sendMessage],
  );

  const resetChat = useCallback(() => {
    setMessages([]);
    setWorkflowSteps([]);
    setLiveAssistantContent("");
    setLiveAssistantIntro("");
    setLiveReasoning("");
    setIsThinking(false);
    setReasoningDuration(undefined);
    thinkingStartTimeRef.current = null;
    setActiveArtifact(null);
    setError("");
    setMeta(DEFAULT_META);
    setIsWaitingForFirstStreamEvent(false);
  }, []);

  return {
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

    // Composer
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
    setError,
    setMessages,

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
  };
}
