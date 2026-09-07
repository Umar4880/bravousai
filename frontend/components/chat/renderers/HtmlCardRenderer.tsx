"use client";

import React, { useEffect, useRef } from "react";

interface HtmlCardRendererProps {
  content: string;
}

export function HtmlCardRenderer({ content }: HtmlCardRendererProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const handleResize = (event: MessageEvent) => {
      if (iframeRef.current && event.source === iframeRef.current.contentWindow) {
        if (event.data.type === "resize") {
          iframeRef.current.style.height = `${event.data.height}px`;
        }
      }
    };
    window.addEventListener("message", handleResize);
    return () => window.removeEventListener("message", handleResize);
  }, []);

  const srcDoc = `
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          body { margin: 0; padding: 0; font-family: system-ui, -apple-system, sans-serif; }
        </style>
      </head>
      <body>
        ${content}
        <script>
          function sendHeight() {
            window.parent.postMessage({ type: 'resize', height: document.body.scrollHeight }, '*');
          }
          window.addEventListener('load', sendHeight);
          window.addEventListener('resize', sendHeight);
          const observer = new MutationObserver(sendHeight);
          observer.observe(document.body, { childList: true, subtree: true, attributes: true });
        </script>
      </body>
    </html>
  `;

  return (
    <div className="html-card-container">
      <iframe
        ref={iframeRef}
        srcDoc={srcDoc}
        sandbox="allow-scripts"
        style={{
          width: "100%",
          border: "none",
          overflow: "hidden",
          minHeight: "100px",
          background: "transparent",
        }}
        title="HTML Card"
      />
    </div>
  );
}
