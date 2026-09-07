"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatArtifact } from "../../lib/api";
import type { StoredWorkflowTrace, WorkflowStep } from "./types";
import {
  collapsedTraceContent,
  isWorkflowTraceOpen,
  sourceDomain,
  traceStepNeedsExpansion,
  visibleSourceGroups,
  visibleTraceSteps,
  workflowTraceTitle,
} from "./workflow";
import { ArtifactFrame } from "./artifact-frame";
import { InlineVisualRenderer } from "./renderers/InlineVisualRenderer";
import { InlineArtifactCard } from "./inline-artifact-card";
import { ReasoningBlock } from "./reasoning-block";

type WorkflowTraceCardProps = {
  trace?: StoredWorkflowTrace;
  steps?: WorkflowStep[];
  answer?: string;
  reasoning?: string;
  isThinking?: boolean;
  artifact?: ChatArtifact | null;
  timestamp?: string;
  onToggleTrace: () => void;
  onToggleStepExpansion: (node: string) => void;
  onArtifactClick?: (artifact: ChatArtifact) => void;
};

export function WorkflowTraceCard({
  trace,
  steps,
  answer = "",
  reasoning = "",
  isThinking = false,
  artifact = null,
  timestamp,
  onToggleTrace,
  onToggleStepExpansion,
  onArtifactClick,
}: WorkflowTraceCardProps) {
  const resolvedSteps = trace?.steps ?? steps ?? [];
  const resolvedAnswer = trace?.answer ?? answer;
  const resolvedReasoning = trace?.reasoning ?? reasoning;
  const resolvedArtifact = trace?.artifact ?? artifact;
  const traceSteps = visibleTraceSteps(resolvedSteps);
  const traceOpen = isWorkflowTraceOpen(resolvedSteps);
  const hasDetails = traceSteps.length > 0;
  const showWorkflowHeader = resolvedSteps.length > 0;

  return (
    <div className="workflow-card" aria-label="Workflow progress">
      {showWorkflowHeader && (
        <button
          className="workflow-trace-header"
          type="button"
          onClick={onToggleTrace}
          disabled={!hasDetails}
        >
          <span className="workflow-icon" aria-hidden="true">
            {resolvedAnswer ? "ok" : "live"}
          </span>
          <span>{workflowTraceTitle(resolvedSteps, resolvedAnswer)}</span>
          {hasDetails && (
            <span className="workflow-caret" aria-hidden="true">
              {traceOpen ? "-" : "+"}
            </span>
          )}
        </button>
      )}

      {traceOpen && hasDetails && (
        <div className="workflow-detail workflow-trace-detail">
          {traceSteps.map((step) => (
            <div className="workflow-trace-entry" key={step.node}>
              <div className="workflow-trace-entry-title">{step.label}</div>
              {step.safeContent && (
                <div className="workflow-stream markdown-body">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{ code: InlineVisualRenderer as any }}
                  >
                    {collapsedTraceContent(step.safeContent, step.isExpanded)}
                  </ReactMarkdown>
                </div>
              )}
              {step.sources.length > 0 && (
                <div className="workflow-sources">
                  {visibleSourceGroups(step).map((group) => (
                    <div className="workflow-source-group" key={group.query}>
                      <div className="workflow-source-group-header">
                        <span>{group.query}</span>
                        <small>{group.totalCount} results</small>
                      </div>
                      <div className="workflow-source-list">
                        {group.items.map((source) => (
                          <a href={source.url} key={source.id} target="_blank" rel="noreferrer">
                            {source.favicon ? (
                              <img src={source.favicon} alt="" />
                            ) : (
                              <span aria-hidden="true">link</span>
                            )}
                            <span>{source.title}</span>
                            <small>{source.domain || sourceDomain(source.url)}</small>
                          </a>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {traceStepNeedsExpansion(step) && (
                <button
                  className="workflow-show-more"
                  type="button"
                  onClick={() => onToggleStepExpansion(step.node)}
                >
                  {step.isExpanded ? "Show less" : "Show more"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {(resolvedReasoning || isThinking) && (
        <ReasoningBlock
          reasoning={resolvedReasoning || ""}
          isThinking={isThinking}
        />
      )}

      {resolvedArtifact && (
        resolvedArtifact.extension === "html" ? (
          <InlineArtifactCard
            artifactId={resolvedArtifact.artifact_id || ""}
            versionId={resolvedArtifact.version_id}
            renderUrl={resolvedArtifact.render_url}
            title={resolvedArtifact.title}
          />
        ) : (
          <button
            type="button"
            className="artifact-snippet-button"
            onClick={() => onArtifactClick?.(resolvedArtifact)}
            title="Open Artifact"
          >
            <div className="artifact-snippet-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
            </div>
            <div className="artifact-snippet-content">
              <span className="artifact-snippet-title">{resolvedArtifact.title || "Interactive Artifact"}</span>
              <span className="artifact-snippet-subtitle">
                {(() => {
                  const ext = (resolvedArtifact.extension || "MD").toUpperCase();
                  const codeExts = ['HTML', 'TSX', 'TS', 'JS', 'JSX', 'CSS', 'PY', 'JSON', 'SH', 'YML', 'YAML'];
                  return codeExts.includes(ext) ? `Code • ${ext}` : `Document • ${ext}`;
                })()}
              </span>
            </div>
            <div className="artifact-snippet-action">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              <span>Open</span>
            </div>
          </button>
        )
      )}
      {resolvedAnswer && (
        <div className="workflow-answer markdown-body">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{ code: InlineVisualRenderer as any }}
          >
            {resolvedAnswer}
          </ReactMarkdown>
        </div>
      )}
      {timestamp && <span className="message-time">{timestamp}</span>}
    </div>
  );
}
