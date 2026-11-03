"use client";

import { useState } from "react";
import Link from "next/link";
import { Mail, Lock, Chrome, Loader2, CheckCircle } from "lucide-react";
import { createClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleEmailSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setLoading(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: window.location.origin + "/auth/callback",
      },
    });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    setLoading(false);
    setSuccess(true);
  };

  const handleGoogleSignup = async () => {
    setError(null);
    setGoogleLoading(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: window.location.origin + "/auth/callback",
      },
    });

    if (error) {
      setError(error.message);
      setGoogleLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Branding */}
        <div className="mb-8 text-center">
          <h1 className="font-serif text-4xl font-semibold tracking-tight text-foreground">
            Recall
          </h1>
          <p className="mt-2 text-sm text-foreground-muted">
            Your personal media memory
          </p>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-border bg-background-card p-6">
          {success ? (
            /* Success state */
            <div className="py-4 text-center">
              <CheckCircle
                size={40}
                className="mx-auto text-green-400"
              />
              <h2 className="mt-4 font-serif text-lg font-medium text-foreground">
                Check your email
              </h2>
              <p className="mt-2 text-sm text-foreground-muted">
                We sent a confirmation link to{" "}
                <span className="font-medium text-foreground">{email}</span>.
                Click it to activate your account.
              </p>
              <Link
                href="/login"
                className="mt-6 inline-block text-sm font-medium text-primary transition-colors hover:text-primary-hover"
              >
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <h2 className="font-serif text-lg font-medium text-foreground">
                Create your account
              </h2>
              <p className="mt-1 text-sm text-foreground-muted">
                Start logging your media journey
              </p>

              {/* Error message */}
              {error && (
                <div className="mt-4 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              {/* Email/Password form */}
              <form onSubmit={handleEmailSignup} className="mt-6 space-y-4">
                <div>
                  <label
                    htmlFor="email"
                    className="mb-1.5 block text-sm font-medium text-foreground-muted"
                  >
                    Email
                  </label>
                  <div className="relative">
                    <Mail
                      size={16}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle"
                    />
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      required
                      className="w-full rounded-lg border border-border bg-background-elevated py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-foreground-subtle transition-colors focus:border-primary"
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="password"
                    className="mb-1.5 block text-sm font-medium text-foreground-muted"
                  >
                    Password
                  </label>
                  <div className="relative">
                    <Lock
                      size={16}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle"
                    />
                    <input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="At least 6 characters"
                      required
                      minLength={6}
                      className="w-full rounded-lg border border-border bg-background-elevated py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-foreground-subtle transition-colors focus:border-primary"
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="confirm-password"
                    className="mb-1.5 block text-sm font-medium text-foreground-muted"
                  >
                    Confirm password
                  </label>
                  <div className="relative">
                    <Lock
                      size={16}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle"
                    />
                    <input
                      id="confirm-password"
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Confirm your password"
                      required
                      minLength={6}
                      className="w-full rounded-lg border border-border bg-background-elevated py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-foreground-subtle transition-colors focus:border-primary"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Creating account...
                    </>
                  ) : (
                    "Create account"
                  )}
                </button>
              </form>

              {/* Divider */}
              <div className="my-6 flex items-center gap-3">
                <div className="h-px flex-1 bg-border" />
                <span className="text-xs text-foreground-subtle">or</span>
                <div className="h-px flex-1 bg-border" />
              </div>

              {/* Google OAuth */}
              <button
                onClick={handleGoogleSignup}
                disabled={googleLoading}
                className="flex w-full items-center justify-center gap-3 rounded-lg border border-border bg-transparent py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-background-elevated disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {googleLoading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Chrome size={16} />
                )}
                Continue with Google
              </button>
            </>
          )}
        </div>

        {/* Login link */}
        {!success && (
          <p className="mt-6 text-center text-sm text-foreground-muted">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-medium text-primary transition-colors hover:text-primary-hover"
            >
              Sign in
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
