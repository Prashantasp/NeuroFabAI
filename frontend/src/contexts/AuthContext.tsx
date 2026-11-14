"use client";

/**
 * Session and workspace state.
 *
 * The access token is held in the API client's memory, never in localStorage.
 * On mount (and after a hard refresh) the session is re-established from the
 * HttpOnly refresh cookie, so a page reload keeps the user signed in without
 * ever exposing a credential to JavaScript.
 */

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  api,
  getActiveWorkspaceId,
  setAccessToken,
  setActiveWorkspaceId,
  setAuthExpiredHandler,
  type User,
  type Workspace,
} from "@/lib/api";

interface AuthContextValue {
  user: User | null;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  /** True only while the initial session probe is running. */
  isLoading: boolean;
  isAuthenticated: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  selectWorkspace: (workspaceId: string) => void;
  refreshWorkspaces: () => Promise<Workspace[]>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUserState] = useState<User | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  /** Pick the workspace to show: last used in this browser, then the server's
   *  remembered choice, then the first available. */
  const resolveActive = useCallback((available: Workspace[], profile: User | null) => {
    if (available.length === 0) return null;
    const preferredId = getActiveWorkspaceId() ?? profile?.last_workspace_id ?? null;
    return available.find((w) => w.id === preferredId) ?? available[0];
  }, []);

  const loadWorkspaces = useCallback(
    async (profile: User | null): Promise<Workspace[]> => {
      const available = await api.listWorkspaces();
      if (!mounted.current) return available;

      setWorkspaces(available);
      const active = resolveActive(available, profile);
      setActiveWorkspace(active);
      setActiveWorkspaceId(active?.id ?? null);
      return available;
    },
    [resolveActive],
  );

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setActiveWorkspaceId(null);
    setUserState(null);
    setWorkspaces([]);
    setActiveWorkspace(null);
  }, []);

  // Restore the session once on mount.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        await api.restoreSession();
        const profile = await api.me();
        if (cancelled || !mounted.current) return;
        setUserState(profile);
        await loadWorkspaces(profile);
      } catch {
        // No valid refresh cookie: an anonymous visitor, not an error.
        if (!cancelled) clearSession();
      } finally {
        if (!cancelled && mounted.current) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [loadWorkspaces, clearSession]);

  // When a refresh fails mid-session, drop straight to sign-in.
  useEffect(() => {
    setAuthExpiredHandler(() => {
      if (!mounted.current) return;
      clearSession();
      const { pathname, search } = window.location;
      const isAuthPage = pathname === "/login" || pathname === "/register" || pathname === "/";
      if (!isAuthPage) {
        router.replace(`/login?redirect=${encodeURIComponent(pathname + search)}`);
      }
    });
    return () => setAuthExpiredHandler(null);
  }, [clearSession, router]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      await api.login(email, password);
      const profile = await api.me();
      setUserState(profile);
      await loadWorkspaces(profile);
    },
    [loadWorkspaces],
  );

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      clearSession();
      router.replace("/login");
    }
  }, [clearSession, router]);

  const selectWorkspace = useCallback(
    (workspaceId: string) => {
      const next = workspaces.find((w) => w.id === workspaceId);
      if (!next || next.id === activeWorkspace?.id) return;

      setActiveWorkspace(next);
      setActiveWorkspaceId(next.id);
      // Persist server-side so the choice follows the user to another device.
      // Failure is not worth interrupting the switch for.
      void api.rememberWorkspace(next.id).catch(() => undefined);
    },
    [workspaces, activeWorkspace?.id],
  );

  const refreshWorkspaces = useCallback(() => loadWorkspaces(user), [loadWorkspaces, user]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      workspaces,
      activeWorkspace,
      isLoading,
      isAuthenticated: Boolean(user),
      signIn,
      signOut,
      selectWorkspace,
      refreshWorkspaces,
      setUser: setUserState,
    }),
    [
      user,
      workspaces,
      activeWorkspace,
      isLoading,
      signIn,
      signOut,
      selectWorkspace,
      refreshWorkspaces,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
