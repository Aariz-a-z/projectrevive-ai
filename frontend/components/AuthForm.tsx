"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { IconShield } from "@/components/icons";
import { Button, Field, Notice, Panel, inputClass } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const MIN_LENGTH = 10;

/**
 * Client-side mirror of backend/app/auth/policy.py.
 *
 * This is guidance while typing, not a security control -- the backend applies
 * the real policy and is the only thing that can reject a password. Keeping
 * the rules in both places means the user is not surprised on submit.
 */
function passwordHints(password: string, email: string) {
  const local = email.split("@")[0]?.toLowerCase() ?? "";
  return [
    {
      ok: password.length >= MIN_LENGTH,
      label: `At least ${MIN_LENGTH} characters`,
    },
    {
      ok: password.length === 0 || new Set(password).size >= 5,
      label: "Uses at least 5 different characters",
    },
    {
      ok: password.length === 0 || !/^\d+$/.test(password),
      label: "Not only digits",
    },
    {
      ok:
        password.length === 0 ||
        local.length < 4 ||
        !password.toLowerCase().includes(local),
      label: "Does not contain your email address",
    },
  ];
}

export function AuthForm({ mode }: { mode: "signup" | "login" }) {
  const isSignup = mode === "signup";
  const router = useRouter();
  const auth = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const hints = passwordHints(password, email);
  const canSubmit =
    email.includes("@") &&
    password.length > 0 &&
    (!isSignup || hints.every((h) => h.ok)) &&
    !busy;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;

    setBusy(true);
    setError(null);
    try {
      if (isSignup) {
        await auth.signup(email, password);
      } else {
        await auth.login(email, password);
      }
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err
          : new ApiError(0, "unknown", "Something went wrong. Try again."),
      );
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-5 py-6">
      <div className="space-y-2 text-center">
        <span className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-cyan to-violet p-2.5 text-[#04121c]">
          <IconShield />
        </span>
        <h1 className="text-2xl font-semibold tracking-tight">
          {isSignup ? "Create your account" : "Welcome back"}
        </h1>
        <p className="text-sm text-muted">
          {isSignup
            ? "Your analyses stay private to your account."
            : "Sign in to reach your saved analyses."}
        </p>
      </div>

      <Panel className="p-5">
        <form onSubmit={submit} className="space-y-4" noValidate>
          <Field label="Email">
            <input
              type="email"
              name="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className={inputClass}
            />
          </Field>

          <Field label="Password">
            <div className="relative">
              <input
                type={reveal ? "text" : "password"}
                name="password"
                autoComplete={isSignup ? "new-password" : "current-password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isSignup ? "A phrase you can remember" : "Your password"}
                className={`${inputClass} pr-16`}
              />
              <button
                type="button"
                onClick={() => setReveal((v) => !v)}
                className="absolute inset-y-0 right-2 my-auto h-6 rounded px-2 text-[11px] text-muted hover:text-fg"
              >
                {reveal ? "Hide" : "Show"}
              </button>
            </div>
          </Field>

          {isSignup && (
            <ul className="space-y-1">
              {hints.map((hint) => (
                <li
                  key={hint.label}
                  className={`flex items-center gap-2 text-xs ${
                    hint.ok ? "text-green" : "text-muted"
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`inline-block h-1.5 w-1.5 rounded-full ${
                      hint.ok ? "bg-green" : "bg-[#2a3a5e]"
                    }`}
                  />
                  {hint.label}
                </li>
              ))}
            </ul>
          )}

          {error && (
            <Notice tone="error" title="That did not work">
              {error.message}
            </Notice>
          )}

          <Button type="submit" disabled={!canSubmit} className="w-full">
            {busy
              ? isSignup
                ? "Creating account…"
                : "Signing in…"
              : isSignup
                ? "Create account"
                : "Sign in"}
          </Button>
        </form>
      </Panel>

      <p className="text-center text-sm text-muted">
        {isSignup ? "Already have an account? " : "No account yet? "}
        <Link
          href={isSignup ? "/login" : "/signup"}
          className="text-cyan hover:underline"
        >
          {isSignup ? "Sign in" : "Create one"}
        </Link>
      </p>

      {isSignup && (
        <p className="text-center text-[11px] leading-relaxed text-muted">
          Passwords are hashed with Argon2id and never stored in readable form.
          Your session is kept in a cookie that page scripts cannot read.
        </p>
      )}
    </div>
  );
}
