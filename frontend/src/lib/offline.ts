/** Verify an issuer-signed QR token on this device with WebCrypto Ed25519, using a cached public key.
 *  Works without a network connection once the key has been fetched once. A signed revocation list is
 *  cached the same way, so an offline check also says whether the credential was revoked "as of" a time. */
const KEY_CACHE = "vp_issuer_jwk";
const LIST_CACHE = "vp_status_list";

function b64urlToBytes(s: string): Uint8Array {
  const pad = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  const bin = atob(pad);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

async function issuerJwk(): Promise<JsonWebKey | null> {
  try {
    const res = await fetch("/api/issuer/jwk");
    if (res.ok) {
      const j = await res.json();
      const jwk = { kty: j.kty, crv: j.crv, x: j.x };
      try { localStorage.setItem(KEY_CACHE, JSON.stringify(jwk)); } catch { /* storage unavailable */ }
      return jwk;
    }
  } catch { /* offline: fall back to the cached key */ }
  try { const c = localStorage.getItem(KEY_CACHE); return c ? JSON.parse(c) : null; } catch { return null; }
}

async function verifyJws(key: CryptoKey, token: string): Promise<Record<string, unknown> | null> {
  const parts = token.trim().split(".");
  if (parts.length !== 3) return null;
  const data = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
  if (!(await crypto.subtle.verify({ name: "Ed25519" }, key, b64urlToBytes(parts[2]), data))) return null;
  try { return JSON.parse(new TextDecoder().decode(b64urlToBytes(parts[1]))); } catch { return null; }
}

interface StatusList { iat: string; exp: string; revoked: string[]; superseded: string[] }

/** The latest revocation list: fetched when online, otherwise the cached copy. Its signature is checked
 *  on every use, so a list edited in local storage is ignored. */
async function statusList(key: CryptoKey): Promise<StatusList | null> {
  let token: string | null = null;
  try {
    const res = await fetch("/api/credentials/status-list");
    if (res.ok) {
      token = (await res.json()).token;
      try { localStorage.setItem(LIST_CACHE, token!); } catch { /* storage unavailable */ }
    }
  } catch { /* offline */ }
  if (!token) { try { token = localStorage.getItem(LIST_CACHE); } catch { token = null; } }
  if (!token) return null;
  const claims = await verifyJws(key, token);
  return claims && claims.typ === "revocation-list" ? (claims as unknown as StatusList) : null;
}

export type DeviceStatus = "NOT_REVOKED" | "REVOKED" | "SUPERSEDED" | "UNKNOWN";
export interface OfflineResult {
  supported: boolean; valid?: boolean; claims?: Record<string, unknown>;
  status?: DeviceStatus; listAt?: string; listExpired?: boolean;
}

export async function verifyOnDevice(token: string): Promise<OfflineResult> {
  if (!globalThis.crypto?.subtle) return { supported: false };
  const parts = token.trim().split(".");
  if (parts.length !== 3) return { supported: true, valid: false };
  const jwk = await issuerJwk();
  if (!jwk) return { supported: false };
  try {
    const key = await crypto.subtle.importKey("jwk", jwk, { name: "Ed25519" }, false, ["verify"]);
    const signed = await verifyJws(key, token);
    let claims: Record<string, unknown> | undefined;
    try { claims = JSON.parse(new TextDecoder().decode(b64urlToBytes(parts[1]))); } catch { /* unreadable */ }
    if (!signed) return { supported: true, valid: false, claims };
    const list = await statusList(key);
    if (!list) return { supported: true, valid: true, claims, status: "UNKNOWN" };
    const cid = String(signed.cid ?? "");
    const status: DeviceStatus = list.revoked.includes(cid) ? "REVOKED" : list.superseded.includes(cid) ? "SUPERSEDED" : "NOT_REVOKED";
    return { supported: true, valid: true, claims, status, listAt: list.iat, listExpired: new Date(list.exp) < new Date() };
  } catch {
    return { supported: false }; // browser without Ed25519 support
  }
}
