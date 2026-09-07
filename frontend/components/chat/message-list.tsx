"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatArtifact } from "../../lib/api";
import type { UiMessage, WorkflowStep, ClarificationQuestion } from "./types";
import { WorkflowTraceCard } from "./workflow-trace-card";
import { ClarificationWizard } from "./clarification-wizard";
import { InlineVisualRenderer } from "./renderers/InlineVisualRenderer";
import { ReasoningBlock } from "./reasoning-block";

type MessageListProps = {
  messages: UiMessage[];
  workflowSteps: WorkflowStep[];
  liveAssistantContent: string;
  liveAssistantIntro?: string;
  liveReasoning?: string;
  isThinking?: boolean;
  reasoningDuration?: number;
  liveArtifact?: ChatArtifact | null;
  isWaitingForFirstStreamEvent: boolean;
  error: string;
  scrollAnchorRef: React.RefObject<HTMLDivElement | null>;
  onReexecute: () => void;
  onResume: () => void;
  onToggleWorkflowTrace: () => void;
  onToggleMessageTrace: (messageId: string) => void;
  onToggleWorkflowStepExpansion: (node: string) => void;
  onToggleMessageTraceStepExpansion: (messageId: string, node: string) => void;
  clarificationQuestions?: ClarificationQuestion[] | null;
  onClarificationSubmit?: (answers: string[]) => void;
  onArtifactClick?: (artifact: ChatArtifact) => void;
};

export function MessageList({
  messages,
  workflowSteps,
  liveAssistantContent,
  liveAssistantIntro,
  liveReasoning,
  isThinking,
  reasoningDuration,
  liveArtifact,
  isWaitingForFirstStreamEvent,
  error,
  scrollAnchorRef,
  onReexecute,
  onResume,
  onToggleWorkflowTrace,
  onToggleMessageTrace,
  onToggleWorkflowStepExpansion,
  onToggleMessageTraceStepExpansion,
  clarificationQuestions,
  onClarificationSubmit,
  onArtifactClick,
}: MessageListProps) {
  return (
    <div className="chat-log" role="log" aria-live="polite">
      <div className="chat-log-content">
        {messages.map((message, index) => {
          const isLast = index === messages.length - 1;

          return (
            <article
              key={message.id}
              className={`message-row ${message.role}`}
              style={{ animationDelay: `${index * 55}ms` }}
            >
              {message.trace ? (
                <WorkflowTraceCard
                  trace={{
                    ...message.trace,
                    intro: message.trace.intro || message.intro,
                    answer: message.trace.answer || message.content,
                    reasoning: message.reasoning || message.trace.reasoning,
                    reasoningDuration: message.trace.reasoningDuration ?? message.reasoningDuration,
                  }}
                  timestamp={message.timestamp}
                  onToggleTrace={() => onToggleMessageTrace(message.id)}
                  onToggleStepExpansion={(node) => onToggleMessageTraceStepExpansion(message.id, node)}
                  onArtifactClick={onArtifactClick}
                />
              ) : (
                <div className="message-bubble">
                  {message.reasoning && (
                    <ReasoningBlock
                      reasoning={message.reasoning}
                      duration={message.reasoningDuration}
                    />
                  )}
                  <div className="message-text markdown-body">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code: InlineVisualRenderer as any
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  </div>
                </div>
              )}

              {message.role === "user" && (
                <div className="message-row-toolbar">
                  <button
                    className="reexecute-button"
                    onClick={onReexecute}
                    title="Re-execute pipeline"
                    aria-label="Re-execute pipeline"
                    type="button"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="12"
                      height="12"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M21.5 2v6h-6" />
                      <path d="M21.34 15.57a10 10 0 1 1-.57-8.38l.73.81" />
                    </svg>
                  </button>
                  <span className="message-time">{message.timestamp}</span>
                </div>

              )}
            </article>
          );
        })}

        {(workflowSteps.length > 0 || liveAssistantContent || liveAssistantIntro || liveReasoning || isThinking) && (
          <article className="message-row assistant workflow-row">
            <WorkflowTraceCard
              steps={workflowSteps}
              intro={liveAssistantIntro}
              answer={liveAssistantContent}
              reasoning={liveReasoning}
              reasoningDuration={reasoningDuration}
              isThinking={isThinking}
              artifact={liveArtifact}
              onToggleTrace={onToggleWorkflowTrace}
              onToggleStepExpansion={onToggleWorkflowStepExpansion}
              onArtifactClick={onArtifactClick}
            />
          </article>
        )}

        {clarificationQuestions && clarificationQuestions.length > 0 && onClarificationSubmit && (
          <div className="clarification-wizard-container">
            <ClarificationWizard
              questions={clarificationQuestions}
              onSubmit={onClarificationSubmit}
            />
          </div>
        )}

        {isWaitingForFirstStreamEvent && !liveReasoning && !isThinking && (
          <article className="message-row assistant">
            <div className="message-bubble typing" aria-label="Assistant is working">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </div>
          </article>
        )}

        {error && (
          <div className="error-banner">
            <p>{error}</p>
            <button type="button" className="ghost-button" onClick={onResume}>
              Resume from Checkpoint
            </button>
          </div>
        )}
        <div ref={scrollAnchorRef} />
      </div>
    </div>
  );
}
