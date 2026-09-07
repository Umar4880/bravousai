"use client";

import React from "react";

interface SvgRendererProps {
  content: string;
}

export function SvgRenderer({ content }: SvgRendererProps) {
  return (
    <div
      className="svg-container"
      style={{ maxWidth: "100%", height: "auto", overflow: "hidden" }}
      dangerouslySetInnerHTML={{ __html: content }}
    />
  );
}
