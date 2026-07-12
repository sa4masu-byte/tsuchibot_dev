"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "./api";

type SessionState = "checking" | "authenticated" | "unavailable";

export function useRequiredSession(): SessionState {
  const router = useRouter();
  const [state, setState] = useState<SessionState>("checking");

  useEffect(() => {
    apiFetch<{ authenticated: boolean }>("/auth/session")
      .then(() => setState("authenticated"))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          router.replace("/login");
          return;
        }
        setState("unavailable");
      });
  }, [router]);

  return state;
}
