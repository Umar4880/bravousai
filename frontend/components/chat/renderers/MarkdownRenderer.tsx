import React, { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { apiUrl } from "../../../lib/api";

type MarkdownRendererProps = {
  downloadUrl: string;
};

export function MarkdownRenderer({ downloadUrl }: MarkdownRendererProps) {
  const [content, setContent] = useState<string>("Loading markdown document...");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchMarkdown() {
      try {
        const url = apiUrl(downloadUrl);
        const inlineUrl = downloadUrl.includes("?") ? `${url}&inline=true` : `${url}?inline=true`;
        const res = await fetch(inlineUrl);
        if (!res.ok) {
          throw new Error("Failed to fetch markdown document.");
        }
        const text = await res.text();
        setContent(text);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error loading document.");
      }
    }
    
    fetchMarkdown();
  }, [downloadUrl]);

  if (error) {
    return (
      <div style={{ padding: "2rem", color: "red", fontFamily: "sans-serif" }}>
        Failed to load document: {error}
      </div>
    );
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif", overflowY: "auto", height: "100%", background: "#fff", color: "#333", lineHeight: 1.6 }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
