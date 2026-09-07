"use client";

import React, { type ClassAttributes, type HTMLAttributes } from "react";
import { MermaidRenderer } from "./MermaidRenderer";
import { SvgRenderer } from "./SvgRenderer";
import { HtmlCardRenderer } from "./HtmlCardRenderer";
import { DataChartRenderer } from "./DataChartRenderer";

type CodeProps = ClassAttributes<HTMLElement> & HTMLAttributes<HTMLElement> & {
  inline?: boolean;
};

export function InlineVisualRenderer({ className, children, ...props }: CodeProps) {
  const match = /language-(\w+)/.exec(className || "");
  const language = match ? match[1] : null;
  const content = String(children).replace(/\n$/, "");

  if (!props.inline && language) {
    if (language === "mermaid") {
      return <MermaidRenderer content={content} />;
    }
    if (language === "svg") {
      return <SvgRenderer content={content} />;
    }
    if (language === "html-card") {
      return <HtmlCardRenderer content={content} />;
    }
    if (language === "data-chart") {
      return <DataChartRenderer content={content} />;
    }
  }

  // Default fallback for normal code blocks
  return (
    <code className={className} {...props}>
      {children}
    </code>
  );
}
