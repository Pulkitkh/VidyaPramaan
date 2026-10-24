/** Verify an issuer-signed QR token on this device with WebCrypto Ed25519, using a cached public key.
 *  Works without a network connection once the key has been fetched once. */
const KEY_CACHE = "vp_issuer_jwk";

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

export interface OfflineResult { supported: boolean; valid?: boolean; claims?: Record<string, unknown> }

export async function verifyOnDevice(token: string): Promise<OfflineResult> {
  if (!globalThis.crypto?.subtle) return { supported: false };
  const parts = token.trim().split(".");
  if (parts.length !== 3) return { supported: true, valid: false };
  const jwk = await issuerJwk();
  if (!jwk) return { supported: false };
  try {
    const key = await crypto.subtle.importKey("jwk", jwk, { name: "Ed25519" }, false, ["verify"]);
    const data = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
    const valid = await crypto.subtle.verify({ name: "Ed25519" }, key, b64urlToBytes(parts[2]), data);
    let claims: Record<string, unknown> | undefined;
    try { claims = JSON.parse(new TextDecoder().decode(b64urlToBytes(parts[1]))); } catch { /* unreadable */ }
    return { supported: true, valid, claims };
  } catch {
    return { supported: false }; // browser without Ed25519 support
  }
}
