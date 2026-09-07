export type ChatMode = "instant" | "extended";

export type ChatRequestPayload = {
  user_id: string;
  project_id?: string | null;
  query: string;
  mode: ChatMode;
  conversation_id?: string | null;
  model?: string | null;
};

export type AuthUser = {
  user_id: string;
  username: string;
  email: string;
};

export type SignupPayload = {
  username: string;
  email: string;
  password: string;
};

export type SigninPayload = {
  email: string;
  password: string;
};

export type ChatResponsePayload = {
  conversation_id: string;
  answer: string;
  approved: boolean;
  route_reason: string;
  iteration_count: number;
  raw_state: Record<string, unknown>;
};

export type ChatArtifact = {
  artifact_id?: string;
  version_id: string;
  render_url: string;
  title: string;
  extension?: string;
  download_url?: string;
};

export type ChatStreamEvent =
  | {
      type: "conversation_created";
      conversation_id: string;
      user_message_id?: string;
    }
  | {
      type: "node_start" | "node_end";
      node: string;
      message?: string;
      visible_message?: string;
      content?: string;
    }
  | {
      type: "node_delta";
      node: string;
      content: string;
    }
  | {
      type: "reasoning_delta";
      node: string;
      content: string;
    }
  | {
      type: "research_query";
      node: string;
      query: string;
      message?: string;
    }
  | {
      type: "search_query_started" | "search_query_completed";
      node: string;
      query: string;
      result_count?: number;
      message?: string;
    }
  | {
      type: "search_result_found";
      node: string;
      query?: string;
      matched_queries?: string[];
      result_id: string;
      title?: string;
      url: string;
      domain?: string;
      source_type?: string;
    }
  | {
      type: "source_selection_completed";
      node: string;
      phase?: string;
      selected_sources: number;
      message?: string;
    }
  | {
      type: "source_extraction_started";
      node: string;
      phase?: string;
      selected_sources: number;
      message?: string;
    }
  | {
      type: "source_extraction_completed";
      node: string;
      phase?: string;
      selected_sources: number;
      successfully_extracted: number;
      partial: number;
      failed: number;
      skipped: number;
      snippet_fallbacks: number;
      total_cleaned_chars: number;
      message?: string;
    }
  | {
      type: "follow_up_research_started";
      node: string;
      iteration: number;
      approved_query_count: number;
      rejected_query_count: number;
      message?: string;
    }
  | {
      type: "follow_up_search_completed";
      node: string;
      iteration: number;
      raw_results_received: number;
      message?: string;
    }
  | {
      type: "research_evidence_merged";
      node: string;
      iteration: number;
      canonical_results_added: number;
      duplicates_removed: number;
      total_canonical_sources: number;
      message?: string;
    }
  | {
      type: "research_loop_stopped";
      node: string;
      iteration: number;
      stop_reason: string;
      total_canonical_sources: number;
      message?: string;
    }
  | {
      type: "research_source";
      node: string;
      query?: string;
      title?: string;
      url: string;
      source?: string | null;
      favicon?: string | null;
    }
  | {
      type: "research_phase";
      node: string;
      phase: "plan" | "search" | "synthesize" | "validate" | "package";
      message: string;
      content?: string;
      status?: "active" | "done" | "error";
      summary?: Record<string, number>;
    }
  | {
      type: "artifact_generation_started";
      node: string;
      claim_count?: number;
      citation_count?: number;
      artifact_kind?: string;
    }
  | {
      type: "artifact_validated";
      node: string;
      section_count?: number;
      citation_count?: number;
      sanitized?: boolean;
      status?: string;
    }
  | {
      type: "artifact_persisted";
      node: string;
      version?: number;
      status?: string;
      artifact_id?: string;
      version_id?: string;
      render_url?: string;
      title?: string;
    }
  | {
      type: "final";
      conversation_id: string;
      answer: string;
      reasoning?: string | null;
      artifact?: ChatArtifact | null;
      approved: boolean;
      route_reason: string;
      iteration_count: number;
      waiting_for_clarification?: boolean;
      state?: Record<string, unknown>;
    }
  | {
      type: "error";
      detail: string;
    };

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  project_id?: string;
};

export type ProjectFileSummary = {
  id: string;
  user_id: string;
  project_id: string;
  conversation_id: string | null;
  original_filename: string;
  safe_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  storage_bucket: string;
  storage_key: string;
  status: "uploaded" | "deleted" | string;
  created_at: string;
  deleted_at: string | null;
};

export type ProjectSummary = {
  id: string;
  user_id: string;
  title: string;
  description: string;
  instructions: string;
  created_at: string;
  updated_at: string;
  files: ProjectFileSummary[];
};

export type ProjectsResponse = {
  projects: ProjectSummary[];
};

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  created_at: string;
};

export type WorkflowTraceStep = {
  node: string;
  label: string;
  status: "active" | "done";
  isOpen: boolean;
  isExpanded?: boolean;
  content: string;
  sources: Array<{
    id: string;
    title: string;
    url: string;
    favicon?: string | null;
    domain?: string | null;
    sourceType?: string | null;
    query?: string | null;
  }>;
};

export type WorkflowTrace = {
  steps: WorkflowTraceStep[];
  answer: string;
  artifact?: ChatArtifact | null;
};

export type ConversationsResponse = {
  conversations: ConversationSummary[];
};

export type ConversationMessagesResponse = {
  conversation: ConversationSummary;
  messages: ConversationMessage[];
  trace?: WorkflowTrace;
  traces?: Record<string, WorkflowTrace>;
};

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function readErrorDetail(response: Response): Promise<string> {
  let detail = `Request failed with status ${response.status}`;

  try {
    const err = (await response.json()) as { detail?: string | { msg?: string }[] };
    if (typeof err.detail === "string") {
      detail = err.detail;
    } else if (Array.isArray(err.detail) && err.detail[0]?.msg) {
      detail = err.detail[0].msg;
    }
  } catch {
    // Keep default detail when response body is not JSON.
  }

  return detail;
}

async function postJson<TResponse, TPayload>(
  path: string,
  payload: TPayload,
): Promise<TResponse> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  return (await response.json()) as TResponse;
}

async function getJson<TResponse>(path: string): Promise<TResponse> {
  const response = await fetch(apiUrl(path), {
    method: "GET",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  return (await response.json()) as TResponse;
}

async function patchJson<TResponse, TPayload>(
  path: string,
  payload: TPayload,
): Promise<TResponse> {
  const response = await fetch(apiUrl(path), {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  return (await response.json()) as TResponse;
}

async function deleteJson<TResponse>(path: string): Promise<TResponse> {
  const response = await fetch(apiUrl(path), {
    method: "DELETE",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  return (await response.json()) as TResponse;
}

export async function signup(payload: SignupPayload): Promise<AuthUser> {
  return postJson<AuthUser, SignupPayload>("/api/v1/auth/signup", payload);
}

export async function signin(payload: SigninPayload): Promise<AuthUser> {
  return postJson<AuthUser, SigninPayload>("/api/v1/auth/signin", payload);
}

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isValidUuid(id?: string | null): boolean {
  return Boolean(id && UUID_REGEX.test(id));
}

export async function getConversations(
  userId: string,
  projectId?: string | null,
): Promise<ConversationsResponse> {
  if (!isValidUuid(userId)) {
    return { conversations: [] };
  }
  const params = new URLSearchParams({ user_id: userId });
  if (projectId) {
    if (!isValidUuid(projectId)) {
      return { conversations: [] };
    }
    params.set("project_id", projectId);
  }
  return getJson<ConversationsResponse>(`/api/v1/chat/conversations?${params}`);
}

export async function getConversationMessages(
  userId: string,
  conversationId: string,
): Promise<ConversationMessagesResponse> {
  if (!isValidUuid(userId) || !isValidUuid(conversationId)) {
    throw new Error(`Invalid UUID provided (user: ${userId}, conversation: ${conversationId})`);
  }
  const params = new URLSearchParams({ user_id: userId });
  return getJson<ConversationMessagesResponse>(
    `/api/v1/chat/conversations/${conversationId}/messages?${params}`,
  );
}

export async function renameConversation(
  userId: string,
  conversationId: string,
  title: string,
): Promise<Pick<ConversationSummary, "id" | "title">> {
  const params = new URLSearchParams({ user_id: userId });
  return patchJson<Pick<ConversationSummary, "id" | "title">, { title: string }>(
    `/api/v1/chat/conversations/${conversationId}?${params}`,
    { title },
  );
}

export async function deleteConversation(
  userId: string,
  conversationId: string,
): Promise<{ deleted: boolean; id: string }> {
  const params = new URLSearchParams({ user_id: userId });
  return deleteJson<{ deleted: boolean; id: string }>(
    `/api/v1/chat/conversations/${conversationId}?${params}`,
  );
}

export async function getProjects(userId: string): Promise<ProjectsResponse> {
  const params = new URLSearchParams({ user_id: userId });
  return getJson<ProjectsResponse>(`/api/v1/projects?${params}`);
}

export async function createProject(payload: {
  user_id: string;
  title: string;
  description?: string;
  instructions?: string;
}): Promise<ProjectSummary> {
  return postJson<ProjectSummary, typeof payload>("/api/v1/projects", payload);
}

export async function updateProject(
  userId: string,
  projectId: string,
  payload: { title?: string; description?: string },
): Promise<ProjectSummary> {
  return patchJson<ProjectSummary, { user_id: string; title?: string; description?: string }>(
    `/api/v1/projects/${projectId}`,
    { user_id: userId, ...payload },
  );
}

export async function deleteProject(
  userId: string,
  projectId: string,
): Promise<{ deleted: boolean; id: string }> {
  const params = new URLSearchParams({ user_id: userId });
  return deleteJson<{ deleted: boolean; id: string }>(
    `/api/v1/projects/${projectId}?${params}`,
  );
}

export async function updateProjectInstructions(
  userId: string,
  projectId: string,
  instructions: string,
): Promise<ProjectSummary> {
  return patchJson<ProjectSummary, { user_id: string; instructions: string }>(
    `/api/v1/projects/${projectId}/instructions`,
    { user_id: userId, instructions },
  );
}

export async function uploadProjectFile(
  userId: string,
  projectId: string,
  file: File,
): Promise<ProjectFileSummary> {
  const formData = new FormData();
  formData.set("user_id", userId);
  formData.set("file", file);

  const response = await fetch(apiUrl(`/api/v1/projects/${projectId}/files`), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  return (await response.json()) as ProjectFileSummary;
}

export async function deleteProjectFile(
  userId: string,
  projectId: string,
  fileId: string,
): Promise<{ deleted: boolean; id: string }> {
  const params = new URLSearchParams({ user_id: userId });
  return deleteJson<{ deleted: boolean; id: string }>(
    `/api/v1/projects/${projectId}/files/${fileId}?${params}`,
  );
}

export async function streamChatMessage({
  payload,
  onEvent,
  signal,
}: {
  payload: ChatRequestPayload;
  onEvent: (event: ChatStreamEvent) => void;
  signal?: AbortSignal;
}): Promise<void> {
  const response = await fetch(apiUrl("/api/v1/chat/stream"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    cache: "no-store",
    signal,
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  if (!response.body) {
    throw new Error("Streaming response does not contain a body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  function handleBlock(block: string) {
    const line = block
      .split("\n")
      .find((candidate) => candidate.startsWith("data: "));

    if (!line) {
      return;
    }

    const json = line.slice("data: ".length).trim();
    if (!json) {
      return;
    }

    const event = JSON.parse(json) as ChatStreamEvent;
    if (event.type === "error") {
      throw new Error(event.detail || "The backend stream failed.");
    }
    onEvent(event);
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      buffer += chunk;

      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";

      for (const block of blocks) {
        if (block.trim()) handleBlock(block);
      }
    }

    if (buffer.trim()) {
      handleBlock(buffer);
    }
  } finally {
    reader.releaseLock();
  }
}
