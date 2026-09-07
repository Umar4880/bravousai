"use client";

import { useEffect, useRef, useState } from "react";

import { type ChatArtifact, apiUrl } from "../../lib/api";

import { MarkdownRenderer } from "./renderers/MarkdownRenderer";
import { DocxRenderer } from "./renderers/DocxRenderer";
import { HtmlRenderer } from "./renderers/HtmlRenderer";

type ArtifactFrameProps = {
  artifact: ChatArtifact;
};

export function ArtifactFrame({ artifact }: ArtifactFrameProps) {
  const src = apiUrl(artifact.render_url);

  const renderContent = () => {
    if (artifact.extension === "md" && artifact.download_url) {
      return (
        <div className="artifact-frame">
          <MarkdownRenderer downloadUrl={artifact.download_url} />
        </div>
      );
    }
    
    if (artifact.extension === "docx" && artifact.download_url) {
      return (
        <div className="artifact-frame">
          <DocxRenderer downloadUrl={artifact.download_url} />
        </div>
      );
    }

    return <HtmlRenderer renderUrl={artifact.render_url} />;
  };

  return (
    <div className="artifact-frame-card">
      <div className="artifact-frame-header">
        <span>{artifact.title || "Interactive artifact"}</span>
        <div className="artifact-frame-actions" style={{ display: "flex", gap: "12px" }}>
          <a href={src} target="_blank" rel="noreferrer">
            Open
          </a>
          {artifact.download_url && (
            <a href={apiUrl(artifact.download_url)} target="_blank" rel="noreferrer" download>
              Download
            </a>
          )}
        </div>
      </div>
      {renderContent()}
    </div>
  );
}
