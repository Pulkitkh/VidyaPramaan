import { ExternalLink } from "lucide-react";
import { Card, PageHeader } from "../components/ui";
import { useI18n } from "../lib/i18n";

const SNIPPETS = [
  { title: "1. Dry-run validation from your ERP (nothing stored)", code: `curl -X POST https://<portal>/api/v1/students:validate \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '[{"apaar_id":"123456789012","roll_no":"0001BTCSE26001","name":"Asha Verma",
        "dob":"2008-02-11","gender":"F","category":"OBC","father_name":"Ravi Verma",
        "programme_code":"BTCSE","admission_type":"REGULAR","quota":"STATE_CAP",
        "admission_date":"2026-08-01"}]'` },
  { title: "2. Submit and commit in one call", code: `curl -X POST "https://<portal>/api/v1/students:submit?commit_now=true" \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @batch.json` },
  { title: "3. Certificate data for degree-awarding bodies", code: `curl https://<portal>/api/v1/certificate-data/{enrolment_id} -H "Authorization: Bearer $TOKEN"
# -> { "apaar_id": "...", "student_id": "...", "qr_payload": "https://<portal>/verify?t=..." }` },
  { title: "4. Verify a QR anywhere (public, no login)", code: `curl -X POST https://<portal>/api/verify/token -H "Content-Type: application/json" -d '{"token":"<from QR>"}'
curl https://<portal>/api/issuer/jwk     # Ed25519 public key for fully offline verification` },
];

export default function Integration() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader title={t("Integration API")} subtitle="Same validation engine as the upload screen, exposed as REST for institutional ERPs, university exam systems and AICTE portals."
        actions={<a className="btn-primary" href="/docs" target="_blank" rel="noreferrer"><ExternalLink size={15} /> Open API reference (OpenAPI)</a>} />
      <div className="grid gap-4 lg:grid-cols-2">
        {SNIPPETS.map((s) => (
          <Card key={s.title} title={s.title}>
            <pre className="mono overflow-x-auto rounded-lg bg-navy-900 p-4 text-[12px] leading-relaxed text-[#dbe7f7]">{s.code}</pre>
          </Card>
        ))}
      </div>
      <Card className="mt-5" title="Production integration notes">
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink-2">
          <li>Authentication: OAuth2 client credentials per institution (AICTE SSO / Keycloak), mTLS for server-to-server, rate limits and idempotency keys.</li>
          <li>APAAR lookups go through a registry adapter. The demo uses a mock registry; production plugs in DigiLocker / API Setu once AICTE is onboarded as a partner.</li>
          <li>Outbound: webhooks for flag raised / resolved, NAD/ABC push of verified records, AISHE-compatible exports.</li>
        </ul>
      </Card>
    </>
  );
}
