export type Role = "user" | "assistant";

export type UiMessage = {
  id: string;
  role: Role;
  content: string;
  intro?: string;
  timestamp: string;
  reasoning?: string;
  reasoningDuration?: number;
  trace?: StoredWorkflowTrace;
};

export type ArtifactView = {
  artifact_id?: string;
  version_id: string;
  render_url: string;
  title: string;
  extension?: string;
  download_url?: string;
};

export type ChatMeta = {
  approved: boolean;
  routeReason: string;
  iterationCount: number;
  lastAgent: string;
  nextAgent: string;
  backendStage: string;
};

export type WorkflowStep = {
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

export type ClarificationQuestion = {
  question: string;
  guess_1: string;
  guess_2: string;
};

export type StoredWorkflowTrace = {
  steps: WorkflowStep[];
  answer: string;
  intro?: string;
  reasoning?: string;
  reasoningDuration?: number;
  artifact?: ArtifactView | null;
  clarification_questions?: ClarificationQuestion[];
};

export type InFlightWorkflowTrace = {
  conversationId: string;
  userMessageId: string | null;
  trace: StoredWorkflowTrace;
  updatedAt: string;
  isRunning: boolean;
};

export type VisibleTraceStep = WorkflowStep & {
  safeContent: string;
};

export type WorkflowSource = WorkflowStep["sources"][number];
