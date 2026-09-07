export type ProjectFile = {
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
  status: string;
  created_at: string;
  deleted_at: string | null;
};

export type ResearchProject = {
  id: string;
  user_id: string;
  title: string;
  description: string;
  instructions: string;
  files: ProjectFile[];
  created_at: string;
  updated_at: string;
};

export type WorkspaceView = "home" | "project" | "chat";

export const ACTIVE_PROJECT_STORAGE_KEY = "gulzarsoft_active_project_id";

export const DEFAULT_PROJECTS: ResearchProject[] = [
  {
    id: "enterprise-rag-architecture",
    user_id: "",
    title: "enterprise rag architecture",
    description:
      "Designing, developing and deploying enterprise rag system that reduces hallucination, controls cost, and handles many source files.",
    instructions: "Prioritize grounded answers, clear citations, and practical implementation steps.",
    files: [],
    created_at: new Date("2026-06-01T00:00:00.000Z").toISOString(),
    updated_at: new Date("2026-06-01T00:00:00.000Z").toISOString(),
  },
  {
    id: "learning-research-presentations",
    user_id: "",
    title: "Learning your research and presentations",
    description: "Collect research threads, presentation plans, and source-backed study notes.",
    instructions: "",
    files: [],
    created_at: new Date("2026-06-02T00:00:00.000Z").toISOString(),
    updated_at: new Date("2026-06-02T00:00:00.000Z").toISOString(),
  },
];

export function createProjectId(title: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 44);

  return `${slug || "project"}-${Date.now().toString(36)}`;
}
