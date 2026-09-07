import { useEffect, useRef, useState } from "react";
import { apiUrl } from "../../lib/api";
import { FiMaximize2, FiMinimize2, FiExternalLink } from "react-icons/fi";

interface InlineArtifactCardProps {
  artifactId: string;
  versionId: string;
  renderUrl: string;
  title?: string;
}

export function InlineArtifactCard({ artifactId, versionId, renderUrl, title }: InlineArtifactCardProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState<number>(300);
  const [isExpanded, setIsExpanded] = useState(false);
  const [htmlContent, setHtmlContent] = useState<string | null>(null);

  // Fetch the raw HTML once so we can use srcdoc (avoids mixed-content issues and allows ResizeObserver inside)
  useEffect(() => {
    let isMounted = true;
    async function fetchHtml() {
      try {
        const fullUrl = renderUrl.startsWith("http") ? renderUrl : apiUrl(renderUrl);
        const res = await fetch(fullUrl);
        if (res.ok) {
          const html = await res.text();
          if (isMounted) {
            // Inject a ResizeObserver script into the HTML to send messages back to parent
            const injectedHtml = html.replace(
              "</body>",
              `<script>
                const ro = new ResizeObserver(() => {
                  window.parent.postMessage({ type: 'resize', height: document.documentElement.scrollHeight, id: '${versionId}' }, '*');
                });
                ro.observe(document.body);
              </script></body>`
            );
            setHtmlContent(injectedHtml);
          }
        }
      } catch (err) {
        console.error("Failed to load artifact HTML", err);
      }
    }
    fetchHtml();
    return () => { isMounted = false; };
  }, [renderUrl, versionId]);

  // Listen for resize messages from the iframe
  useEffect(() => {
    const handleMessage = (e: MessageEvent) => {
      if (e.data && e.data.type === 'resize' && e.data.id === versionId) {
        // Add a small buffer to prevent scrollbars
        setHeight(Math.max(300, e.data.height + 20));
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [versionId]);

  if (!htmlContent) {
    return (
      <div className="w-full h-32 flex items-center justify-center border border-gray-200 rounded-xl bg-gray-50 animate-pulse">
        <span className="text-gray-400 text-sm font-medium">Loading briefing...</span>
      </div>
    );
  }

  const toggleExpand = () => setIsExpanded(!isExpanded);
  const openExternal = () => window.open(apiUrl(renderUrl), "_blank");

  return (
    <div className={`flex flex-col border border-gray-200 rounded-xl overflow-hidden bg-white shadow-sm transition-all duration-300 ${isExpanded ? 'fixed inset-4 z-50 shadow-2xl' : 'w-full my-4'}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 bg-gray-50/50">
        <span className="text-sm font-semibold text-gray-700 truncate">{title || "Interactive Briefing"}</span>
        <div className="flex items-center gap-2">
          <button 
            onClick={openExternal}
            className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
            title="Open in new tab"
          >
            <FiExternalLink className="w-4 h-4" />
          </button>
          <button 
            onClick={toggleExpand}
            className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
            title={isExpanded ? "Collapse" : "Expand"}
          >
            {isExpanded ? <FiMinimize2 className="w-4 h-4" /> : <FiMaximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Iframe Container */}
      <div 
        className="w-full relative bg-white overflow-hidden transition-all duration-300" 
        style={{ height: isExpanded ? '100%' : `${Math.min(height, 800)}px` }}
      >
        <iframe
          ref={iframeRef}
          srcDoc={htmlContent}
          sandbox="allow-scripts allow-same-origin"
          className="absolute inset-0 w-full h-full border-0"
          title={title || "Artifact Render"}
        />
        {!isExpanded && height > 800 && (
          <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-white to-transparent pointer-events-none" />
        )}
      </div>
      
      {!isExpanded && height > 800 && (
        <button 
          onClick={toggleExpand}
          className="w-full py-2 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 transition-colors"
        >
          View Full Dashboard
        </button>
      )}
    </div>
  );
}
