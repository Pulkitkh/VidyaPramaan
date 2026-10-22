import { ChevronRight } from "lucide-react";
import type { StoredFinding } from "../lib/api";
import { Empty, RuleBadge } from "./ui";

export default function FindingList({ items, onOpen, showInstitution = false }: {
  items: StoredFinding[]; onOpen?: (f: StoredFinding) => void; showInstitution?: boolean;
}) {
  if (!items.length) return <Empty>No open items.</Empty>;
  return (
    <ul className="divide-y divide-line">
      {items.map((f) => (
        <li key={f.id}>
          <button onClick={() => onOpen?.(f)} disabled={!onOpen}
            className="flex w-full items-start gap-3 px-5 py-3 text-left hover:bg-navy-50/40 disabled:cursor-default disabled:hover:bg-transparent">
            <RuleBadge code={f.rule_code} severity={f.severity} />
            <div className="min-w-0 flex-1">
              <div className="text-sm">{f.message}</div>
              <div className="mt-0.5 text-[11px] text-ink-3">
                {showInstitution && f.institution && <>{f.institution} · </>}
                {f.source === "SCAN" ? "National scan" : "Upload validation"} · ruleset {f.rule_version}
                {f.status !== "OPEN" && <> · {f.status}</>}
              </div>
            </div>
            {onOpen && <ChevronRight size={16} className="mt-0.5 text-ink-3" />}
          </button>
        </li>
      ))}
    </ul>
  );
}
