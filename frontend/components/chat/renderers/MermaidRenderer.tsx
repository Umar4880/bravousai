"use client";

import React, { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  theme: "default",
  themeVariables: {
    fontSize: "16px",
    fontFamily: "var(--font-sans, system-ui, sans-serif)",
  },
  flowchart: {
    padding: 20
  }
});

interface MermaidRendererProps {
  content: string;
}

export function MermaidRenderer({ content }: MermaidRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hasError, setHasError] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const MERMAID_KEYWORDS = [
    "graph", "flowchart", "sequenceDiagram", "gantt", "classDiagram",
    "stateDiagram", "erDiagram", "journey", "gitGraph", "pie", "timeline",
    "quadrantChart", "requirementDiagram", "mindmap", "xychart-beta",
  ];

  const isValidMermaid = (text: string) => {
    const firstLine = text.trim().split("\n")[0].toLowerCase();
    return MERMAID_KEYWORDS.some((kw) => firstLine.startsWith(kw));
  };

  useEffect(() => {
    const renderDiagram = async () => {
      if (!containerRef.current) return;

      if (!content || !isValidMermaid(content)) {
        setErrorMsg("Invalid or unsupported diagram syntax.");
        setHasError(true);
        return;
      }

      try {
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(id, content);
        containerRef.current.innerHTML = svg;
        setHasError(false);
      } catch (err) {
        console.error("Mermaid rendering failed:", err);
        setErrorMsg(err instanceof Error ? err.message : "Unknown error");
        setHasError(true);
      }
    };

    void renderDiagram();
  }, [content]);

  if (hasError) {
    return (
      <div className="mermaid-error">
        <p>⚠️ Could not render diagram: <em>{errorMsg}</em></p>
        <details>
          <summary>Raw content</summary>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.75rem" }}>{content}</pre>
        </details>
      </div>
    );
  }

  return (
    <div 
      className="mermaid-container" 
      ref={containerRef} 
      style={{ overflowX: "auto", minWidth: "100%", padding: "1rem" }} 
    />
  );
}
