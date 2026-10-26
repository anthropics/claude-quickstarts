"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Eye,
  EyeOff,
  ExternalLink,
  Loader2,
  Music,
  Youtube,
  Check,
  LogOut,
  Unlink,
} from "lucide-react";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";

// PKCE helpers
function generateRandomString(length: number): string {
  const possible =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  const values = crypto.getRandomValues(new Uint8Array(length));
  return Array.from(values)
    .map((x) => possible[x % possible.length])
    .join("");
}

async function sha256(plain: string): Promise<ArrayBuffer> {
  const encoder = new TextEncoder();
  const data = encoder.encode(plain);
  return crypto.subtle.digest("SHA-256", data);
}

function base64encode(input: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(input)))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

interface ConnectionStatus {
  spotify: boolean;
  youtube: boolean;
}

export function SettingsView() {
  const [tmdbKey, setTmdbKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [connections, setConnections] = useState<ConnectionStatus>({
    spotify: false,
    youtube: false,
  });
  const [connectingSpotify, setConnectingSpotify] = useState(false);
  const [connectingYoutube, setConnectingYoutube] = useState(false);
  const supabase = createClient();

  const checkConnections = useCallback(async () => {
    const [spotifyRes, youtubeRes] = await Promise.allSettled([
      fetch("/api/spotify/recently-played"),
      fetch("/api/youtube/recently-watched"),
    ]);

    setConnections({
      spotify:
        spotifyRes.status === "fulfilled" && spotifyRes.value.ok,
      youtube:
        youtubeRes.status === "fulfilled" && youtubeRes.value.ok,
    });
  }, []);

  useEffect(() => {
    Promise.all([
      fetch("/api/settings")
        .then((res) => res.json())
        .then((data) => setTmdbKey(data.tmdb_api_key ?? ""))
        .catch(() =>
          setMessage({ type: "error", text: "Failed to load settings" })
        ),
      checkConnections(),
    ]).finally(() => setLoading(false));
  }, [checkConnections]);

  // Handle OAuth callback from popup
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.data?.type === "spotify-callback") {
        handleSpotifyCallback(event.data.code);
      }
      if (event.data?.type === "youtube-callback") {
        handleYoutubeCallback(event.data.code);
      }
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  });

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

  // Spotify OAuth PKCE flow
  const handleConnectSpotify = async () => {
    const clientId = process.env.NEXT_PUBLIC_SPOTIFY_CLIENT_ID;
    if (!clientId) {
      toast.error("Spotify client ID not configured.");
      return;
    }

    setConnectingSpotify(true);
    const codeVerifier = generateRandomString(64);
    const hashed = await sha256(codeVerifier);
    const codeChallenge = base64encode(hashed);

    // Store verifier for callback
    sessionStorage.setItem("spotify_code_verifier", codeVerifier);

    const redirectUri = `${window.location.origin}/settings`;
    sessionStorage.setItem("spotify_redirect_uri", redirectUri);

    const scopes = "user-read-recently-played";
    const authUrl = new URL("https://accounts.spotify.com/authorize");
    authUrl.searchParams.set("response_type", "code");
    authUrl.searchParams.set("client_id", clientId);
    authUrl.searchParams.set("scope", scopes);
    authUrl.searchParams.set("redirect_uri", redirectUri);
    authUrl.searchParams.set("code_challenge_method", "S256");
    authUrl.searchParams.set("code_challenge", codeChallenge);

    window.location.href = authUrl.toString();
  };

  // YouTube/Google OAuth PKCE flow
  const handleConnectYoutube = async () => {
    const clientId = process.env.NEXT_PUBLIC_YOUTUBE_CLIENT_ID;
    if (!clientId) {
      toast.error("YouTube client ID not configured.");
      return;
    }

    setConnectingYoutube(true);
    const codeVerifier = generateRandomString(64);
    const hashed = await sha256(codeVerifier);
    const codeChallenge = base64encode(hashed);

    sessionStorage.setItem("youtube_code_verifier", codeVerifier);

    const redirectUri = `${window.location.origin}/settings`;
    sessionStorage.setItem("youtube_redirect_uri", redirectUri);

    const scopes = "https://www.googleapis.com/auth/youtube.readonly";
    const authUrl = new URL("https://accounts.google.com/o/oauth2/v2/auth");
    authUrl.searchParams.set("response_type", "code");
    authUrl.searchParams.set("client_id", clientId);
    authUrl.searchParams.set("scope", scopes);
    authUrl.searchParams.set("redirect_uri", redirectUri);
    authUrl.searchParams.set("code_challenge_method", "S256");
    authUrl.searchParams.set("code_challenge", codeChallenge);
    authUrl.searchParams.set("access_type", "offline");
    authUrl.searchParams.set("prompt", "consent");

    window.location.href = authUrl.toString();
  };

  // Handle Spotify OAuth callback (from URL params after redirect)
  const handleSpotifyCallback = async (code: string) => {
    const codeVerifier = sessionStorage.getItem("spotify_code_verifier");
    const redirectUri = sessionStorage.getItem("spotify_redirect_uri");

    if (!codeVerifier || !redirectUri) {
      toast.error("Missing OAuth state. Please try again.");
      return;
    }

    try {
      const res = await fetch("/api/spotify/callback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          code_verifier: codeVerifier,
          redirect_uri: redirectUri,
        }),
      });

      if (res.ok) {
        toast.success("Spotify connected!");
        setConnections((prev) => ({ ...prev, spotify: true }));
      } else {
        toast.error("Failed to connect Spotify.");
      }
    } catch {
      toast.error("Failed to connect Spotify.");
    } finally {
      sessionStorage.removeItem("spotify_code_verifier");
      sessionStorage.removeItem("spotify_redirect_uri");
      setConnectingSpotify(false);
    }
  };

  const handleYoutubeCallback = async (code: string) => {
    const codeVerifier = sessionStorage.getItem("youtube_code_verifier");
    const redirectUri = sessionStorage.getItem("youtube_redirect_uri");

    if (!codeVerifier || !redirectUri) {
      toast.error("Missing OAuth state. Please try again.");
      return;
    }

    try {
      const res = await fetch("/api/youtube/callback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          code_verifier: codeVerifier,
          redirect_uri: redirectUri,
        }),
      });

      if (res.ok) {
        toast.success("YouTube connected!");
        setConnections((prev) => ({ ...prev, youtube: true }));
      } else {
        toast.error("Failed to connect YouTube.");
      }
    } catch {
      toast.error("Failed to connect YouTube.");
    } finally {
      sessionStorage.removeItem("youtube_code_verifier");
      sessionStorage.removeItem("youtube_redirect_uri");
      setConnectingYoutube(false);
    }
  };

  // Handle callback if returning from OAuth redirect
  useEffect(() => {
    const url = new URL(window.location.href);
    const code = url.searchParams.get("code");

    if (code) {
      // Determine which OAuth flow this is based on stored verifiers
      if (sessionStorage.getItem("spotify_code_verifier")) {
        handleSpotifyCallback(code);
      } else if (sessionStorage.getItem("youtube_code_verifier")) {
        handleYoutubeCallback(code);
      }

      // Clean URL
      url.searchParams.delete("code");
      url.searchParams.delete("state");
      window.history.replaceState({}, "", url.pathname);
    }
  // Run once on mount
  }, []);

  const handleDisconnectSpotify = async () => {
    try {
      await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tmdb_api_key: tmdbKey,
          spotify_access_token: null,
          spotify_refresh_token: null,
          spotify_token_expires_at: null,
        }),
      });
      setConnections((prev) => ({ ...prev, spotify: false }));
      toast.success("Spotify disconnected.");
    } catch {
      toast.error("Failed to disconnect.");
    }
  };

  const handleDisconnectYoutube = async () => {
    try {
      await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tmdb_api_key: tmdbKey,
          youtube_access_token: null,
          youtube_refresh_token: null,
          youtube_token_expires_at: null,
        }),
      });
      setConnections((prev) => ({ ...prev, youtube: false }));
      toast.success("YouTube disconnected.");
    } catch {
      toast.error("Failed to disconnect.");
    }
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    window.location.href = "/login";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={24} className="animate-spin text-foreground-muted" />
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-20">
      <div>
        <h2 className="text-2xl font-semibold font-serif">Settings</h2>
        <p className="mt-1 text-sm text-foreground-muted">
          Configure API keys and connected services.
        </p>
      </div>

      {/* TMDB API Key */}
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

      {/* Connected Services */}
      <section className="rounded-xl border border-border bg-background-elevated p-5 space-y-5">
        <div>
          <h3 className="text-base font-medium">Connected Services</h3>
          <p className="mt-1 text-sm text-foreground-muted">
            Connect your accounts to see recently consumed media and log with
            one tap.
          </p>
        </div>

        {/* Spotify */}
        <div className="flex items-center justify-between gap-4 rounded-lg bg-background p-4 border border-border-subtle">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#1DB954]/10">
              <Music size={20} className="text-[#1DB954]" />
            </div>
            <div>
              <p className="text-sm font-medium">Spotify</p>
              <p className="text-xs text-foreground-muted">
                {connections.spotify
                  ? "Connected — recently played tracks will appear on your timeline"
                  : "See your recently played tracks"}
              </p>
            </div>
          </div>
          {connections.spotify ? (
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1 text-xs text-green-400">
                <Check size={12} />
                Connected
              </span>
              <button
                onClick={handleDisconnectSpotify}
                className="p-1.5 rounded-lg text-foreground-subtle hover:text-foreground hover:bg-background-elevated transition-colors"
                title="Disconnect"
              >
                <Unlink size={14} />
              </button>
            </div>
          ) : (
            <button
              onClick={handleConnectSpotify}
              disabled={connectingSpotify}
              className="rounded-lg bg-[#1DB954] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#1DB954]/90 disabled:opacity-50"
            >
              {connectingSpotify ? "Connecting..." : "Connect"}
            </button>
          )}
        </div>

        {/* YouTube */}
        <div className="flex items-center justify-between gap-4 rounded-lg bg-background p-4 border border-border-subtle">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f97316]/10">
              <Youtube size={20} className="text-[#f97316]" />
            </div>
            <div>
              <p className="text-sm font-medium">YouTube</p>
              <p className="text-xs text-foreground-muted">
                {connections.youtube
                  ? "Connected — recently watched videos will appear on your timeline"
                  : "See your recently watched videos"}
              </p>
            </div>
          </div>
          {connections.youtube ? (
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1 text-xs text-green-400">
                <Check size={12} />
                Connected
              </span>
              <button
                onClick={handleDisconnectYoutube}
                className="p-1.5 rounded-lg text-foreground-subtle hover:text-foreground hover:bg-background-elevated transition-colors"
                title="Disconnect"
              >
                <Unlink size={14} />
              </button>
            </div>
          ) : (
            <button
              onClick={handleConnectYoutube}
              disabled={connectingYoutube}
              className="rounded-lg bg-[#f97316] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#f97316]/90 disabled:opacity-50"
            >
              {connectingYoutube ? "Connecting..." : "Connect"}
            </button>
          )}
        </div>
      </section>

      {/* Account */}
      <section className="rounded-xl border border-border bg-background-elevated p-5 space-y-4">
        <h3 className="text-base font-medium">Account</h3>
        <button
          onClick={handleSignOut}
          className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm text-foreground-muted border border-border hover:text-foreground hover:bg-background transition-colors"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </section>

      <p className="text-xs text-foreground-subtle">
        Your API keys and tokens are stored securely and only used on your
        behalf.
      </p>
    </div>
  );
}
