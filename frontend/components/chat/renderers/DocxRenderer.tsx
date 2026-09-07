import React, { useEffect, useState } from "react";
import mammoth from "mammoth";

import { apiUrl } from "../../../lib/api";

type DocxRendererProps = {
  downloadUrl: string;
};

export function DocxRenderer({ downloadUrl }: DocxRendererProps) {
  const [htmlContent, setHtmlContent] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchAndRenderDocx() {
      try {
        const url = apiUrl(downloadUrl);
        const inlineUrl = downloadUrl.includes("?") ? `${url}&inline=true` : `${url}?inline=true`;
        const res = await fetch(inlineUrl);
        if (!res.ok) {
          throw new Error("Failed to fetch DOCX document.");
        }
        
        const arrayBuffer = await res.arrayBuffer();
        
        // Convert docx to html using mammoth
        const result = await mammoth.convertToHtml({ arrayBuffer });
        setHtmlContent(result.value);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error loading document.");
      } finally {
        setLoading(false);
      }
    }
    
    fetchAndRenderDocx();
  }, [downloadUrl]);

  if (loading) {
    return (
      <div style={{ padding: "2rem", fontFamily: "sans-serif", color: "#666" }}>
        Loading document preview...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "2rem", color: "red", fontFamily: "sans-serif" }}>
        Failed to load document: {error}
      </div>
    );
  }

  return (
    <div 
      className="docx-preview"
      style={{ padding: "2rem", fontFamily: "sans-serif", overflowY: "auto", height: "100%", background: "#fff", color: "#333", lineHeight: 1.6 }}
      dangerouslySetInnerHTML={{ __html: htmlContent }} 
    />
  );
}
