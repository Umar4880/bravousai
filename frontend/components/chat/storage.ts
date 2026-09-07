import type { AuthUser } from "../../lib/api";
import type { InFlightWorkflowTrace, StoredWorkflowTrace } from "./types";

export const AUTH_STORAGE_KEY = "gulzarsoft_auth_user";
export const WORKFLOW_TRACE_STORAGE_KEY = "gulzarsoft_workflow_traces";
export const IN_FLIGHT_WORKFLOW_TRACE_STORAGE_KEY = "gulzarsoft_inflight_workflow_traces";

export function readStoredAuthUser(): AuthUser | null {
  const rawUser = window.localStorage.getItem(AUTH_STORAGE_KEY);

  if (!rawUser) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawUser) as Partial<AuthUser>;
    if (
      typeof parsed.user_id === "string" &&
      typeof parsed.username === "string" &&
      typeof parsed.email === "string"
    ) {
      return {
        user_id: parsed.user_id,
        username: parsed.username,
        email: parsed.email,
      };
    }
  } catch {
    // Invalid stored session; clear it below.
  }

  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  return null;
}

export function readStoredWorkflowTraces(): Record<string, StoredWorkflowTrace> {
  try {
    const rawValue = window.localStorage.getItem(WORKFLOW_TRACE_STORAGE_KEY);
    if (!rawValue) {
      return {};
    }

    const parsed = JSON.parse(rawValue);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }

    return Object.fromEntries(
      Object.entries(parsed).flatMap(([key, value]) => {
        if (Array.isArray(value)) {
          return [[key, { steps: value, answer: "" }]];
        }

        if (
          value &&
          typeof value === "object" &&
          Array.isArray((value as StoredWorkflowTrace).steps)
        ) {
          const casted = value as StoredWorkflowTrace;
          return [[
            key,
            {
              steps: casted.steps,
              answer: typeof casted.answer === "string" ? casted.answer : "",
              intro: typeof casted.intro === "string" ? casted.intro : undefined,
              reasoning: typeof casted.reasoning === "string" ? casted.reasoning : undefined,
              reasoningDuration: typeof casted.reasoningDuration === "number" ? casted.reasoningDuration : undefined,
              artifact: casted.artifact ?? null,
            },
          ]];
        }

        return [];
      }),
    ) as Record<string, StoredWorkflowTrace>;
  } catch {
    return {};
  }
}

export function writeStoredWorkflowTrace(conversationId: string, trace: StoredWorkflowTrace) {
  const traces = readStoredWorkflowTraces();
  traces[conversationId] = trace;
  window.localStorage.setItem(WORKFLOW_TRACE_STORAGE_KEY, JSON.stringify(traces));
}

export function deleteStoredWorkflowTrace(conversationId: string) {
  const traces = readStoredWorkflowTraces();
  delete traces[conversationId];
  window.localStorage.setItem(WORKFLOW_TRACE_STORAGE_KEY, JSON.stringify(traces));
}

export function readInFlightWorkflowTraces(): Record<string, InFlightWorkflowTrace> {
  try {
    const rawValue = window.sessionStorage.getItem(IN_FLIGHT_WORKFLOW_TRACE_STORAGE_KEY);
    if (!rawValue) {
      return {};
    }

    const parsed = JSON.parse(rawValue);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }

    return Object.fromEntries(
      Object.entries(parsed).flatMap(([key, value]) => {
        if (!value || typeof value !== "object") {
          return [];
        }

        const candidate = value as Partial<InFlightWorkflowTrace>;
        if (
          typeof candidate.conversationId !== "string" ||
          !candidate.trace ||
          !Array.isArray(candidate.trace.steps)
        ) {
          return [];
        }

        return [[
          key,
          {
            conversationId: candidate.conversationId,
            userMessageId: typeof candidate.userMessageId === "string" ? candidate.userMessageId : null,
            trace: {
              steps: candidate.trace.steps,
              answer: typeof candidate.trace.answer === "string" ? candidate.trace.answer : "",
              intro: typeof candidate.trace.intro === "string" ? candidate.trace.intro : undefined,
              reasoning: typeof candidate.trace.reasoning === "string" ? candidate.trace.reasoning : undefined,
              reasoningDuration: typeof candidate.trace.reasoningDuration === "number" ? candidate.trace.reasoningDuration : undefined,
              artifact: candidate.trace.artifact ?? null,
            },
            updatedAt: typeof candidate.updatedAt === "string" ? candidate.updatedAt : new Date().toISOString(),
            isRunning: candidate.isRunning !== false,
          },
        ]];
      }),
    ) as Record<string, InFlightWorkflowTrace>;
  } catch {
    return {};
  }
}

export function writeInFlightWorkflowTrace(snapshot: InFlightWorkflowTrace) {
  const traces = readInFlightWorkflowTraces();
  traces[snapshot.conversationId] = snapshot;
  if (snapshot.userMessageId) {
    traces[snapshot.userMessageId] = snapshot;
  }
  window.sessionStorage.setItem(IN_FLIGHT_WORKFLOW_TRACE_STORAGE_KEY, JSON.stringify(traces));
}

export function readInFlightWorkflowTrace(conversationIdOrMessageId: string): InFlightWorkflowTrace | undefined {
  return readInFlightWorkflowTraces()[conversationIdOrMessageId];
}

export function deleteInFlightWorkflowTrace(conversationId: string, userMessageId?: string | null) {
  const traces = readInFlightWorkflowTraces();
  const snapshot = traces[conversationId];
  delete traces[conversationId];
  if (userMessageId) {
    delete traces[userMessageId];
  }
  if (snapshot?.userMessageId) {
    delete traces[snapshot.userMessageId];
  }
  window.sessionStorage.setItem(IN_FLIGHT_WORKFLOW_TRACE_STORAGE_KEY, JSON.stringify(traces));
}
