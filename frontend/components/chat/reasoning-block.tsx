"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ReasoningBlockProps {
  reasoning: string;
  isThinking?: boolean;
  duration?: number;
  defaultExpanded?: boolean;
}

export function ReasoningBlock({
  reasoning,
  isThinking = false,
  duration,
  defaultExpanded = false,
}: ReasoningBlockProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [userToggled, setUserToggled] = useState(false);

  // Auto-expand only while actively thinking, then collapse cleanly like Claude
  useEffect(() => {
    if (isThinking && !userToggled) {
      setIsExpanded(true);
    } else if (!isThinking && !userToggled) {
      setIsExpanded(false);
    }
  }, [isThinking, userToggled]);

  if (!reasoning && !isThinking) return null;

  const durationText = duration ? `${duration}s` : "a few seconds";

  return (
    <div className="claude-thought-block">
      <button
        type="button"
        className={`claude-thought-trigger ${isThinking ? "thinking" : ""}`}
        onClick={() => {
          setUserToggled(true);
          setIsExpanded((prev) => !prev);
        }}
        aria-expanded={isExpanded}
      >
        <div className="claude-thought-trigger-content">
          {isThinking ? (
            <span className="claude-thought-spinner" aria-hidden="true">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2v4" />
                <path d="m16.2 7.8 2.9-2.9" />
                <path d="M18 12h4" />
                <path d="m16.2 16.2 2.9 2.9" />
                <path d="M12 18v4" />
                <path d="m4.9 19.1 2.9-2.9" />
                <path d="M2 12h4" />
                <path d="m4.9 4.9 2.9 2.9" />
              </svg>
            </span>
          ) : null}
          <span className="claude-thought-label">
            {isThinking ? "Thinking..." : `Thought for ${durationText}`}
          </span>
          <svg
            className={`claude-thought-chevron ${isExpanded ? "open" : ""}`}
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </div>
      </button>

      {isExpanded && (
        <div className="claude-thought-container markdown-body">
          {reasoning ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {reasoning}
            </ReactMarkdown>
          ) : (
            <p className="claude-thought-placeholder">Formulating thought process...</p>
          )}
        </div>
      )}
    </div>
  );
}
