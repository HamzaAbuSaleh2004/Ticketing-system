import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { Role, TokenResponse, User } from "../api/types";
import { session, type Session } from "./session";

type AuthState = {
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  register: (name: string, email: string, password: string) => Promise<User>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function homeFor(role: Role): string {
  return role === "admin" ? "/admin" : role === "agent" ? "/agent" : "/";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<Session | null>(session.get);
  const queryClient = useQueryClient();

  useEffect(() => {
    const unsubscribe = session.subscribe((next) => {
      setCurrent(next);
      // Never show one user's cached data to the next.
      if (!next) queryClient.clear();
    });
    return () => {
      unsubscribe();
    };
  }, [queryClient]);

  // Refresh the stored user (role/team may have changed since sign-in); a
  // 401 here clears the session via the API client.
  useEffect(() => {
    const token = session.get()?.token;
    if (!token) return;
    api<User>("/auth/me")
      .then((user) => {
        const s = session.get();
        // Only if the same session is still signed in when the reply lands.
        if (s?.token === token) session.set({ ...s, user });
      })
      .catch(() => undefined);
  }, []);

  const value = useMemo<AuthState>(() => {
    const accept = (resp: TokenResponse) => {
      queryClient.clear();
      session.set({ token: resp.access_token, user: resp.user });
      return resp.user;
    };
    return {
      user: current?.user ?? null,
      login: async (email, password) =>
        accept(await api<TokenResponse>("/auth/login", { method: "POST", body: { email: email.trim(), password } })),
      register: async (name, email, password) =>
        accept(
          await api<TokenResponse>("/auth/register", { method: "POST", body: { name, email: email.trim(), password } }),
        ),
      logout: () => session.clear(),
    };
  }, [current, queryClient]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
