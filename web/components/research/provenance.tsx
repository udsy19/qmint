import { StatusMark } from "@/components/shell/status-mark";
import { Disclosure } from "@/components/ui/disclosure";
import { TBody, THead, Table, Td, Th, Tr } from "@/components/ui/table";
import type { Schemas } from "@/lib/api/client";

/** "abcdef12…9a8b7c6d" — hashes are truncated in the middle; the full value is in the title. */
export function MiddleHash({ value }: { value: string }) {
  return (
    <span title={value} className="font-mono">
      {value.slice(0, 10)}…{value.slice(-8)}
    </span>
  );
}

export function StatusGlossary({ items }: { items: Schemas["GlossaryItem"][] }) {
  return (
    <Disclosure title="Verification status definitions" meta={`${items.length} statuses`}>
      <dl className="grid gap-x-6 gap-y-2.5 sm:grid-cols-[220px_minmax(0,1fr)]">
        {items.map((g) => (
          <div key={g.status} className="contents">
            <dt>
              <StatusMark status={g.status} />
            </dt>
            <dd className="text-sm text-muted">
              {g.definition} <span className="font-mono text-xs text-subtle">{g.source_file}</span>
            </dd>
          </div>
        ))}
      </dl>
    </Disclosure>
  );
}

export function SourceFiles({ files, snapshot }: { files: Schemas["SourceFile"][]; snapshot: string | null }) {
  return (
    <Disclosure title="Source files" meta={snapshot ? `snapshot ${snapshot}` : undefined}>
      <Table>
        <THead>
          <Tr>
            <Th>File</Th>
            <Th numeric>Entries</Th>
            <Th className="hidden sm:table-cell">sha256</Th>
          </Tr>
        </THead>
        <TBody>
          {files.map((f) => (
            <Tr key={f.path}>
              <Td className="font-mono text-xs">{f.path}</Td>
              <Td numeric>{f.entries}</Td>
              <Td className="hidden text-xs text-subtle sm:table-cell">{f.sha256 ? <MiddleHash value={f.sha256} /> : "missing"}</Td>
            </Tr>
          ))}
        </TBody>
      </Table>
    </Disclosure>
  );
}
