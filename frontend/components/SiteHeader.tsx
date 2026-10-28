"use client";

import Link from "next/link";

import { IconLogout, IconSpark, IconUser } from "@/components/icons";
import { useAuth } from "@/lib/auth";

export function SiteHeader() {
  const { user, status, logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 border-b border-edge bg-[#070b16]/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-cyan to-violet text-[#04121c]">
            <IconSpark className="h-5 w-5" />
          </span>
          <span className="text-base font-semibold tracking-tight">
            ProjectRevive <span className="grad-text">AI</span>
          </span>
        </Link>

        <nav className="flex items-center gap-2 text-sm">
          {status === "loading" && (
            <span className="h-8 w-28 animate-pulse rounded-lg bg-panel-inset" />
          )}

          {status === "anonymous" && (
            <>
              <Link
                href="/login"
                className="rounded-lg px-3 py-1.5 text-fg-dim hover:text-fg"
              >
                Sign in
              </Link>
              <Link
                href="/signup"
                className="rounded-lg bg-gradient-to-r from-cyan to-blue px-3.5 py-1.5 font-semibold text-[#04121c] hover:brightness-110"
              >
                Create account
              </Link>
            </>
          )}

          {status === "authenticated" && user && (
            <>
              <Link
                href="/dashboard"
                className="rounded-lg px-3 py-1.5 text-fg-dim hover:text-fg"
              >
                Dashboard
              </Link>
              <span
                className="hidden items-center gap-1.5 rounded-lg border border-edge bg-panel-inset px-2.5 py-1.5 text-xs text-fg-dim sm:flex"
                title={user.email}
              >
                <IconUser className="h-3.5 w-3.5 text-cyan" />
                <span className="max-w-[140px] truncate">{user.email}</span>
              </span>
              <button
                type="button"
                onClick={logout}
                title="Sign out"
                className="rounded-lg border border-edge bg-panel-inset p-2 text-fg-dim hover:border-rose/40 hover:text-rose"
              >
                <IconLogout className="h-4 w-4" />
                <span className="sr-only">Sign out</span>
              </button>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
