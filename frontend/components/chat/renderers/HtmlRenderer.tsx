import React, { useEffect, useRef, useState } from "react";
import { apiUrl } from "../../../lib/api";

type HtmlRendererProps = {
  renderUrl: string;
};

export function HtmlRenderer({ renderUrl }: HtmlRendererProps) {
  const src = apiUrl(renderUrl);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [frameHeight, setFrameHeight] = useState<number>(520);

  useEffect(() => {
    setFrameHeight(520);

    function handleMessage(event: MessageEvent) {
      if (event.source !== iframeRef.current?.contentWindow) {
        return;
      }

      const data = event.data;
      if (!data || typeof data !== "object" || data.type !== "artifact:height") {
        return;
      }

      const nextHeight = Number(data.height);
      if (!Number.isFinite(nextHeight) || nextHeight <= 0) {
        return;
      }

      setFrameHeight(Math.min(Math.max(Math.ceil(nextHeight), 360), 12000));
    }

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [src]);

  return (
    <iframe
      ref={iframeRef}
      className="artifact-frame"
      src={src}
      title="Interactive artifact"
      sandbox="allow-scripts"
      referrerPolicy="no-referrer"
      style={{ height: `${frameHeight}px` }}
    />
  );
}
