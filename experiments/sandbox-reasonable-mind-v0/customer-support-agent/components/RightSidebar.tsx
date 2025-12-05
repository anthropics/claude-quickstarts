"use client";

import React, { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { FileIcon, MessageCircleIcon } from "lucide-react";
import FullSourceModal from "./FullSourceModal";

interface RAGSource {
  id: string;
  fileName: string;
  snippet: string;
  score: number;
  timestamp?: string;
}

interface RAGHistoryItem {
  sources: RAGSource[];
  timestamp: string;
  query: string;
}

interface DebugInfo {
  context_used: boolean;
}

interface SidebarEvent {
  id: string;
  content: string;
  user_mood?: string;
  debug?: DebugInfo;
}

const truncateSnippet = (text: string): string => {
  return text?.length > 150 ? `${text.slice(0, 100)}...` : text || "";
};

const getScoreColor = (score: number): string => {
  if (score > 0.6) return "bg-green-100 text-green-800";
  if (score > 0.4) return "bg-yellow-100 text-yellow-800";
  return "bg-red-100 text-red-800";
};

const MAX_HISTORY = 15;

const RightSidebar: React.FC = () => {
  const [ragHistory, setRagHistory] = useState<RAGHistoryItem[]>([]);
  const [shouldShowSources, setShouldShowSources] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState<RAGSource | null>(null);

  useEffect(() => {
    const updateRAGSources = (
      event: CustomEvent<{
        sources: RAGSource[];
        query: string;
        debug?: DebugInfo;
      }>,
    ) => {
      console.log("🔍 RAG event received:", event.detail);
      const { sources, query, debug } = event.detail;

      const shouldDisplaySources = debug?.context_used;

      if (
        Array.isArray(sources) &&
        sources.length > 0 &&
        shouldDisplaySources
      ) {
        const cleanedSources = sources.map((source) => ({
          ...source,
          snippet: source.snippet || "No preview available",
          fileName:
            (source.fileName || "").replace(/_/g, " ").replace(".txt", "") ||
            "Unnamed",
          timestamp: new Date().toISOString(),
        }));

        const historyItem: RAGHistoryItem = {
          sources: cleanedSources,
          timestamp: new Date().toISOString(),
          query: query || "Unknown query",
        };

        setRagHistory((prev) => {
          const newHistory = [historyItem, ...prev];
          return newHistory.slice(0, MAX_HISTORY);
        });

        console.log(
          "🔍 Sources displayed:",
          shouldDisplaySources ? "YES" : "NO",
        );
      }
    };

    const updateDebug = (event: CustomEvent<SidebarEvent>) => {
      const debug = event.detail.debug;
      const shouldShow = debug?.context_used ?? false;
      setShouldShowSources(shouldShow);
    };

    window.addEventListener(
      "updateRagSources" as any,
      updateRAGSources as EventListener,
    );
    window.addEventListener(
      "updateSidebar" as any,
      updateDebug as EventListener,
    );

    return () => {
      window.removeEventListener(
        "updateRagSources" as any,
        updateRAGSources as EventListener,
      );
      window.removeEventListener(
        "updateSidebar" as any,
        updateDebug as EventListener,
      );
    };
  }, []);

  const handleViewFullSource = (source: RAGSource) => {
    setSelectedSource(source);
    setIsModalOpen(true);
  };

  const fadeInUpClass = "animate-fade-in-up";
  const fadeStyle = {
    animationDuration: "600ms",
    animationFillMode: "backwards",
    animationTimingFunction: "cubic-bezier(0.2, 0.8, 0.2, 1)",
  };

  return (
    <aside className="w-[380px] pr-4 overflow-hidden pb-4">
      <Card
        className={`${fadeInUpClass} h-full overflow-hidden`}
        style={fadeStyle}
      >
        <CardHeader>
          <CardTitle className="text-sm font-medium leading-none">
            Knowledge Base History
          </CardTitle>
        </CardHeader>
        <CardContent className="overflow-y-auto h-[calc(100%-45px)]">
          {ragHistory.length === 0 && (
            <div className="text-sm text-muted-foreground">
              The assistant will display sources here once finding them
            </div>
          )}
          {ragHistory.map((historyItem, index) => (
            <div
              key={historyItem.timestamp}
              className={`mb-6 ${fadeInUpClass}`}
              style={{ ...fadeStyle, animationDelay: `${index * 50}ms` }}
            >
              <div className="flex items-center text-xs text-muted-foreground mb-2 gap-1">
                <MessageCircleIcon
                  size={14}
                  className="text-muted-foreground"
                />
                <span>{historyItem.query}</span>
              </div>
              {historyItem.sources.map((source, sourceIndex) => (
                <Card
                  key={source.id}
                  className={`mb-2 ${fadeInUpClass}`}
                  style={{
                    ...fadeStyle,
                    animationDelay: `${index * 100 + sourceIndex * 75}ms`,
                  }}
                >
                  <CardContent className="py-4">
                    <p className="text-sm text-muted-foreground">
                      {truncateSnippet(source.snippet)}
                    </p>
                    <div className="flex flex-col gap-2">
                      <div
                        className={`${getScoreColor(source.score)} px-2 py-1 mt-4 rounded-full text-xs inline-block w-fit`}
                      >
                        {(source.score * 100).toFixed(0)}% match
                      </div>
                      <div
                        className="inline-flex items-center mr-2 mt-2 text-muted-foreground text-xs py-0 cursor-pointer hover:text-gray-600"
                        onClick={() => handleViewFullSource(source)}
                      >
                        <FileIcon className="w-4 h-4 min-w-[12px] min-h-[12px] mr-2" />
                        <span className="text-xs underline">
                          {truncateSnippet(source.fileName || "Unnamed")}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ))}
        </CardContent>
      </Card>
      <FullSourceModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        source={selectedSource}
      />
    </aside>
  );
};

export default RightSidebar;
