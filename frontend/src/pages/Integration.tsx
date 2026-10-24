import { Copy, ExternalLink, KeyRound, Trash2 } from "lucide-react";
import { useState } from "react";
import { Card, ErrorNote, PageHeader } from "../components/ui";
import { api, fmt } from "../lib/api";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

interface Key { id: number; label: string; prefix: string; created_at: string; last_used_at: string | null; revoked: boolean }

const SNIPPETS = [
  { title: "1. Dry-run validation from your ERP (nothing stored)", code: `curl -X POST https://<portal>/api/v1/students:validate \\
  -H "X-API-Key: $VP_KEY" -H "Content-Type: application/json" \\
  -d '[{"APAAR No":"123456789012","Consent":"Yes","Roll Number":"0001BTCSE26001",
        "Student Name":"Asha Verma","Date of Birth":"11-02-2008","Sex":"Female",
        "Category":"OBC","Mother's Name":"Sunita Verma","Course Code":"BTCSE",
        "Entry Type":"Regular","Quota":"State Cap","Date of Admission":"01-08-2026"}]'
# Your ERP's own column names are recognised (Student Name, APAAR No, Date of Birth ...)` },
  { title: "2. Submit and commit, safe to retry", code: `curl -X POST "https://<portal>/api/v1/students:submit?commit_now=true" \\
  -H "X-API-Key: $VP_KEY" -H "Idempotency-Key: admissions-2026-batch-07" \\
  -H "Content-Type: application/json" -d @batch.json
# Sending the same Idempotency-Key again returns the first result: no double admissions.` },
  { title: "3. Certificate data for degree-awarding bodies", code: `curl https://<portal>/api/v1/certificate-data/{enrolment_id} -H "Authorization: Bearer $TOKEN"
# -> { "apaar_id": "...", "student_id": "...", "qr_payload": "https://<portal>/verify?t=..." }` },
  { title: "4. Verify a QR anywhere (public, no login)", code: `curl -X POST https://<portal>/api/verify/token -H "Content-Type: application/json" -d '{"token":"<from QR>"}'
curl https://<portal>/api/issuer/jwk          # Ed25519 public key for fully offline verification
curl https://<portal>/api/audit/checkpoints   # signed audit-chain heads anyone can archive` },
];

export default function Integration() {
  const { t } = useI18n();
  const keys = useApi<Key[]>("/api/institution/api-keys");
  const [label, setLabel] = useState("ERP nightly sync");
  const [fresh, setFresh] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const create = async () => {
    setErr(null);
    try {
      const r = await api<{ key: string }>("/api/institution/api-keys", { method: "POST", json: { label } });
      setFresh(r.key);
      keys.reload();
    } catch (e) { setErr((e as Error).message); }
  };
  const revoke = async (id: number) => { await api(`/api/institution/api-keys/${id}`, { method: "DELETE" }); keys.reload(); };

  return (
    <>
      <PageHeader title={t("Integration API")} subtitle="Same validation engine as the upload screen, exposed as REST for institutional ERPs, university exam systems and AICTE portals."
        actions={<a className="btn-primary" href="/docs" target="_blank" rel="noreferrer"><ExternalLink size={15} /> Open API reference (OpenAPI)</a>} />

      <Card className="mb-5" title={<span className="inline-flex items-center gap-2"><KeyRound size={16} /> API keys for your ERP</span>}
        subtitle="Each key belongs to your institution only. The key is shown once; the portal keeps only a hash. Revoke a key the moment a system is retired.">
        {err && <div className="mb-3"><ErrorNote message={err} /></div>}
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[220px] flex-1"><label className="label" htmlFor="key-label">Label</label>
            <input id="key-label" className="input" value={label} onChange={(e) => setLabel(e.target.value)} /></div>
          <button className="btn-primary" onClick={create} disabled={label.trim().length < 3}>Create key</button>
        </div>
        {fresh && (
          <div className="mt-3 rounded-lg border border-saffron-100 bg-saffron-50/60 p-3 text-sm" role="status">
            <div className="font-medium">Copy this key now; it will not be shown again.</div>
            <div className="mt-1 flex items-center gap-2"><code className="mono break-all text-xs">{fresh}</code>
              <button className="btn-ghost btn-sm" onClick={() => navigator.clipboard?.writeText(fresh)}><Copy size={13} /> Copy</button></div>
          </div>
        )}
        {(keys.data ?? []).length > 0 && (
          <table className="mt-4 w-full text-sm">
            <thead><tr><th className="th">Label</th><th className="th">Key</th><th className="th">Created</th><th className="th">Last used</th><th className="th" /></tr></thead>
            <tbody>
              {keys.data!.map((k) => (
                <tr key={k.id} className={k.revoked ? "text-ink-3" : ""}>
                  <td className="td">{k.label}</td><td className="td mono text-xs">{k.prefix}…</td>
                  <td className="td text-xs">{fmt.dateTime(k.created_at)}</td><td className="td text-xs">{k.last_used_at ? fmt.dateTime(k.last_used_at) : "never"}</td>
                  <td className="td text-right">{k.revoked ? <span className="chip bg-[#f1f0ec]">revoked</span> :
                    <button className="btn-ghost btn-sm" onClick={() => revoke(k.id)}><Trash2 size={13} /> Revoke</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {SNIPPETS.map((s) => (
          <Card key={s.title} title={s.title}>
            <pre className="mono overflow-x-auto rounded-lg bg-navy-900 p-4 text-[12px] leading-relaxed text-[#dbe7f7]">{s.code}</pre>
          </Card>
        ))}
      </div>
      <Card className="mt-5" title="Production integration notes">
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink-2">
          <li>Authentication: per-institution API keys today; production adds OAuth2 client credentials (AICTE SSO / Keycloak) and mTLS for server-to-server calls.</li>
          <li>APAAR lookups go through a registry adapter. The demo uses a mock registry; production plugs in DigiLocker / API Setu once AICTE is onboarded as a partner.</li>
          <li>Outbound: webhooks for flag raised / resolved, NAD/ABC push of verified records, AISHE-compatible exports.</li>
        </ul>
      </Card>
    </>
  );
}
