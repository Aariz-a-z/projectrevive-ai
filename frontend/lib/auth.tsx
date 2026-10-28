"use client";

/**
 * Session state for the browser.
 *
 * The session cookie is httpOnly, so the client cannot read it directly. The
 * only way to know whether someone is signed in is to ask the API, which this
 * provider does once on mount and then keeps in memory.
 *
 * `status` is three-valued on purpose: "loading" is distinct from "anonymous"
 * so a protected page shows a skeleton on first paint instead of flashing the
 * sign-in redirect at someone who is in fact signed in.
 */

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import * as api from "@/lib/api";
import type { UserPublic } from "@/lib/types";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthValue {
  user: UserPublic | null;
  status: Status;
  signup: (email: string, password: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const router = useRouter();

  useEffect(() => {
    let active = true;
    api
      .getMe()
      .then((me) => {
        if (!active) return;
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => {
        if (!active) return;
        setUser(null);
        setStatus("anonymous");
      });
    return () => {
      active = false;
    };
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const me = await api.signup(email, password);
    setUser(me);
    setStatus("authenticated");
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const me = await api.login(email, password);
    setUser(me);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      setStatus("anonymous");
      router.push("/");
    }
  }, [router]);

  const value = useMemo(
    () => ({ user, status, signup, login, logout }),
    [user, status, signup, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return value;
}

/** Redirects to /login once we know for certain nobody is signed in. */
export function useRequireAuth(): { user: UserPublic | null; ready: boolean } {
  const { user, status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  return { user, ready: status === "authenticated" };
}
