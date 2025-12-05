"use client";

import React, { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  User,
  DollarSign,
  Info,
  Wrench,
  Zap,
  Building2,
  Scale,
  ChartBarBig,
  CircleHelp,
} from "lucide-react";

interface ThinkingContent {
  id: string;
  content: string;
  user_mood?: string;
  matched_categories?: string[];
  debug?: {
    context_used: boolean;
  };
}

const getDebugPillColor = (value: boolean): string => {
  return value
    ? "bg-green-100 text-green-800 border-green-300" // Success
    : "bg-yellow-100 text-yellow-800 border-yellow-300"; // Not Used/Not Relevant
};

const getMoodColor = (mood: string): string => {
  const colors: { [key: string]: string } = {
    positive: "bg-green-100 text-green-800",
    negative: "bg-red-100 text-red-800",
    curious: "bg-blue-100 text-blue-800",
    frustrated: "bg-orange-100 text-orange-800",
    confused: "bg-yellow-100 text-yellow-800",
    neutral: "bg-gray-100 text-gray-800",
  };
  return colors[mood?.toLowerCase()] || "bg-gray-100 text-gray-800";
};

const MAX_THINKING_HISTORY = 15;

const LeftSidebar: React.FC = () => {
  const [thinkingContents, setThinkingContents] = useState<ThinkingContent[]>(
    [],
  );

  useEffect(() => {
    const handleUpdateSidebar = (event: CustomEvent<ThinkingContent>) => {
      if (event.detail && event.detail.id) {
        console.log("🔍 DEBUG: Sidebar Event:", event.detail);
        setThinkingContents((prev) => {
          const exists = prev.some((item) => item.id === event.detail.id);
          if (!exists) {
            console.log(
              "📝 New thinking entry: ",
              event.detail.content.slice(0, 50) + "...",
            ); // Shows first 50 chars

            // Add a timestamp!
            const enhancedEntry = {
              ...event.detail,
              timestamp: new Date().toISOString(),
            };

            const newHistory = [enhancedEntry, ...prev].slice(
              0,
              MAX_THINKING_HISTORY,
            ); // Always keep latest 20

            return newHistory;
          }
          return prev;
        });
      } else {
        console.warn("Missing 'id' in sidebar event detail:", event.detail);
      }
    };

    window.addEventListener(
      "updateSidebar",
      handleUpdateSidebar as EventListener,
    );
    return () =>
      window.removeEventListener(
        "updateSidebar",
        handleUpdateSidebar as EventListener,
      );
  }, []);

  return (
    <aside className="w-[380px] pl-4 overflow-hidden pb-4">
      <Card className="h-full overflow-hidden">
        <CardHeader>
          <CardTitle className="text-sm font-medium leading-none">
            Assistant Thinking
          </CardTitle>
        </CardHeader>
        <CardContent className="overflow-y-auto h-[calc(100%-45px)]">
          {thinkingContents.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              The assistant inner dialogue will appear here for you to debug it
            </div>
          ) : (
            thinkingContents.map((content) => (
              <Card
                key={content.id}
                className="mb-4 animate-fade-in-up"
                style={{
                  animationDuration: "600ms",
                  animationFillMode: "backwards",
                  animationTimingFunction: "cubic-bezier(0.2, 0.8, 0.2, 1)", // This adds bounce
                }}
              >
                <CardContent className="py-4">
                  <div className="text-sm text-muted-foreground">
                    {content.content}
                  </div>
                  {content.user_mood && content.debug && (
                    <div className="flex items-center space-x-2 mt-4 text-xs">
                      {/* Mood */}
                      <span
                        className={`px-2 py-1 rounded-full ${getMoodColor(content.user_mood)}`}
                      >
                        {content.user_mood.charAt(0).toUpperCase() +
                          content.user_mood.slice(1)}
                      </span>

                      <span
                        className={`px-2 py-1 rounded-full ${getDebugPillColor(content.debug.context_used)}`}
                      >
                        Context: {content.debug.context_used ? "✅" : "❌"}
                      </span>
                    </div>
                  )}
                  {content.matched_categories &&
                    content.matched_categories.length > 0 && (
                      <div className="mt-2">
                        {content.matched_categories.map((category) => (
                          <div
                            key={category}
                            className="inline-flex items-center mr-2 mt-2 text-muted-foreground text-xs py-0"
                          >
                            {category === "account" && (
                              <User className="w-3 h-3 mr-1" />
                            )}
                            {category === "billing" && (
                              <DollarSign className="w-3 h-3 mr-1" />
                            )}
                            {category === "feature" && (
                              <Zap className="w-3 h-3 mr-1" />
                            )}
                            {category === "internal" && (
                              <Building2 className="w-3 h-3 mr-1" />
                            )}
                            {category === "legal" && (
                              <Scale className="w-3 h-3 mr-1" />
                            )}
                            {category === "other" && (
                              <CircleHelp className="w-3 h-3 mr-1" />
                            )}
                            {category === "technical" && (
                              <Wrench className="w-3 h-3 mr-1" />
                            )}
                            {category === "usage" && (
                              <ChartBarBig className="w-3 h-3 mr-1" />
                            )}
                            {category
                              .split("_")
                              .map(
                                (word) =>
                                  word.charAt(0).toUpperCase() + word.slice(1),
                              )
                              .join(" ")}
                          </div>
                        ))}
                      </div>
                    )}
                </CardContent>
              </Card>
            ))
          )}
        </CardContent>
      </Card>
    </aside>
  );
};

export default LeftSidebar;
