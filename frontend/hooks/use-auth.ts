"use client";

import { useCallback, useEffect, useState } from "react";
import type { AuthUser } from "../lib/chat-api";
import { AUTH_STORAGE_KEY, readStoredAuthUser } from "../components/chat/storage";

export type AuthMode = "signin" | "signup";

export function useAuth() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [hasLoadedSession, setHasLoadedSession] = useState(false);
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = readStoredAuthUser();
    if (stored) {
      setAuthUser(stored);
    }
    setHasLoadedSession(true);
  }, []);

  const openSignIn = useCallback(() => {
    setAuthMode("signin");
    setIsAuthModalOpen(true);
    setAuthError("");
  }, []);

  const openSignUp = useCallback(() => {
    setAuthMode("signup");
    setIsAuthModalOpen(true);
    setAuthError("");
  }, []);

  const closeAuthModal = useCallback(() => {
    setIsAuthModalOpen(false);
    setAuthMode(null);
    setAuthError("");
  }, []);

  const handleAuthenticated = useCallback((user: AuthUser) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
    }
    setAuthUser(user);
    setIsAuthModalOpen(false);
    setAuthMode(null);
    setAuthError("");
  }, []);

  const handleSignOut = useCallback(() => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
    }
    setAuthUser(null);
    setAuthMode(null);
    setIsAuthModalOpen(false);
  }, []);

  return {
    authUser,
    authMode,
    isAuthModalOpen,
    hasLoadedSession,
    authError,
    setAuthError,
    setAuthMode,
    openSignIn,
    openSignUp,
    closeAuthModal,
    handleAuthenticated,
    handleSignOut,
  };
}
