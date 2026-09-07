import type { VisibleTraceStep, WorkflowSource, WorkflowStep } from "./types";

export function normalizeTraceLine(value: string): string {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

export function workflowLabel(node: string, fallback = "Working..."): string {
  const labels: Record<string, string> = {
    deep_research: "Deep Research in progress...",
    research_plan: "Planning research...",
    research_search: "Searching on internet...",
    source_extraction: "Reading selected sources...",
    research_synthesize: "Synthesizing result...",
    follow_up_research: "Checking follow-up evidence...",
    presentation: "Building presentation artifact...",
  };

  return labels[node] ?? fallback;
}

export function shouldOpenWorkflowStep(node: string): boolean {
  return [
    "deep_research",
    "research_plan",
    "research_search",
    "source_extraction",
    "research_synthesize",
    "follow_up_research",
    "presentation",
  ].includes(node);
}

export function looksInternalWorkflowContent(content: string): boolean {
  const trimmed = content.trim();
  if (!trimmed) {
    return false;
  }
  return (
    trimmed.startsWith("{") ||
    trimmed.startsWith("[") ||
    trimmed.includes('"workflow"') ||
    trimmed.includes('"requires_research"') ||
    trimmed.includes('"route_reason"') ||
    trimmed.includes('"execution_path"') ||
    trimmed.includes("source_evidence_content") ||
    trimmed.includes("StructuredSynthesisOutput") ||
    trimmed.includes("ResearchPackage")
  );
}

export function visibleTraceSteps(steps: WorkflowStep[]): VisibleTraceStep[] {
  return steps
    .map((step) => ({
      ...step,
      safeContent: looksInternalWorkflowContent(step.content) ? "" : step.content,
    }))
    .filter((step) => step.safeContent || step.sources.length > 0);
}

export function workflowTraceTitle(steps: WorkflowStep[], answer = ""): string {
  const hasAnswer = Boolean(answer.trim());
  const activeStep = [...steps].reverse().find((step) => step.status === "active");
  const doneNodes = new Set(steps.filter((step) => step.status === "done").map((step) => step.node));
  const sourceCount = steps.reduce((total, step) => total + step.sources.length, 0);

  if (hasAnswer || doneNodes.has("deep_research")) {
    if (sourceCount > 0) {
      return `Synthesized findings from ${sourceCount} sources into a grounded response`;
    }
    return "Prepared the final response";
  }

  if (activeStep?.node === "research_synthesize") {
    return "Synthesizing collected evidence into a grounded answer";
  }

  if (activeStep?.node === "source_extraction") {
    return "Reading selected sources for stronger evidence";
  }

  if (activeStep?.node === "follow_up_research") {
    return "Checking follow-up evidence before the final answer";
  }

  if (activeStep?.node === "research_search" || sourceCount > 0) {
    return sourceCount > 0
      ? `Reviewing ${sourceCount} search results and selected sources`
      : "Searching reliable sources for the request";
  }

  if (activeStep?.node === "research_plan" || doneNodes.has("research_plan")) {
    return "Planned the research path and evidence checks";
  }

  if (activeStep?.node === "deep_research") {
    return "Conducting comprehensive deep research";
  }

  return "Working through the request";
}

export function isWorkflowTraceOpen(steps: WorkflowStep[]): boolean {
  return steps.some((step) => step.isOpen);
}

export function groupedWorkflowSources(sources: WorkflowSource[]) {
  const groups = new Map<string, WorkflowSource[]>();

  for (const source of sources) {
    const key = source.query || "Selected sources";
    groups.set(key, [...(groups.get(key) ?? []), source]);
  }

  return Array.from(groups.entries()).map(([query, items]) => ({ query, items }));
}

export function collapsedTraceContent(content: string, isExpanded?: boolean): string {
  if (isExpanded) {
    return content;
  }

  const lines = content.split("\n").filter((line) => line.trim());
  if (lines.length <= 5) {
    return content;
  }

  return lines.slice(0, 5).join("\n");
}

export function traceStepNeedsExpansion(step: VisibleTraceStep): boolean {
  const lineCount = step.safeContent.split("\n").filter((line) => line.trim()).length;
  const groupCount = groupedWorkflowSources(step.sources).length;
  return lineCount > 5 || step.sources.length > 8 || groupCount > 2;
}

export function visibleSourceGroups(step: VisibleTraceStep) {
  const groups = groupedWorkflowSources(step.sources);
  if (step.isExpanded) {
    return groups.map((group) => ({ ...group, totalCount: group.items.length }));
  }

  return groups.slice(0, 2).map((group) => ({
    ...group,
    totalCount: group.items.length,
    items: group.items.slice(0, 4),
  }));
}

export function sourceDomain(url: string, fallback?: string | null): string {
  if (fallback) {
    return fallback;
  }

  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

