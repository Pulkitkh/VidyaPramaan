import { createContext, useContext, useState, type ReactNode } from "react";
import { api, getStoredUser, storeSession, type User } from "./api";

interface AuthState {
  user: User | null;
  login: (username: string) => Promise<User>;
  logout: () => void;
}

const Ctx = createContext<AuthState>({ user: null, login: async () => { throw new Error("no provider"); }, logout: () => {} });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(getStoredUser);
  const login = async (username: string) => {
    const res = await api<{ token: string; user: User }>("/api/auth/demo-login", { method: "POST", json: { username } });
    storeSession(res.token, res.user);
    setUser(res.user);
    return res.user;
  };
  const logout = () => {
    storeSession(null, null);
    setUser(null);
  };
  return <Ctx.Provider value={{ user, login, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);

export function homeFor(role: string): string {
  switch (role) {
    case "AICTE_ADMIN":
    case "AUDITOR":
      return "/aicte";
    case "INSTITUTION_ADMIN":
      return "/institution";
    case "VERIFIER":
      return "/verify";
    case "STUDENT":
      return "/student";
    default:
      return "/";
  }
}
