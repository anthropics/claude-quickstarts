"use client";

import { useState, useEffect } from "react";
import { Eye, EyeOff, ExternalLink, Loader2 } from "lucide-react";

export function SettingsView() {
  const [tmdbKey, setTmdbKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  useEffect(() => {
    fetch("/api/settings")
      .then((res) => res.json())
      .then((data) => {
        setTmdbKey(data.tmdb_api_key ?? "");
      })
      .catch(() => {
        setMessage({ type: "error", text: "Failed to load settings" });
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);

    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tmdb_api_key: tmdbKey }),
      });

      if (!res.ok) throw new Error("Failed to save");

      setMessage({ type: "success", text: "Settings saved!" });
    } catch {
      setMessage({ type: "error", text: "Failed to save settings" });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={24} className="animate-spin text-foreground-muted" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-semibold font-serif">Settings</h2>
        <p className="mt-1 text-sm text-foreground-muted">
          Configure API keys to enable media search.
        </p>
      </div>

      <section className="rounded-xl border border-border bg-background-elevated p-5 space-y-4">
        <div>
          <h3 className="text-base font-medium">TMDB API Key</h3>
          <p className="mt-1 text-sm text-foreground-muted">
            Required to search for films and TV shows. Get a free key from{" "}
            <a
              href="https://www.themoviedb.org/settings/api"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline inline-flex items-center gap-1"
            >
              themoviedb.org
              <ExternalLink size={12} />
            </a>
          </p>
        </div>

        <div className="relative">
          <input
            type={showKey ? "text" : "password"}
            value={tmdbKey}
            onChange={(e) => setTmdbKey(e.target.value)}
            placeholder="Enter your TMDB API key"
            className="w-full rounded-lg border border-border bg-background px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground"
          >
            {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>

          {message && (
            <p
              className={`text-sm ${
                message.type === "success"
                  ? "text-green-400"
                  : "text-red-400"
              }`}
            >
              {message.text}
            </p>
          )}
        </div>
      </section>

      <p className="text-xs text-foreground-subtle">
        Your API keys are stored securely and only used to fetch search results
        on your behalf.
      </p>
    </div>
  );
}
