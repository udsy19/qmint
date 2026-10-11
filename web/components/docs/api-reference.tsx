import * as React from "react";
import openapi from "@/lib/api/openapi.json";
import { Disclosure } from "@/components/ui/disclosure";
import { CodeBlock } from "./code-block";

/**
 * API reference rendered from the generated lib/api/openapi.json (pnpm gen:api), so it can never drift from the
 * running API. Schemas are resolved one $ref deep inline; deeper objects are named and expandable.
 */
type Schema = {
  $ref?: string;
  type?: string;
  enum?: unknown[];
  const?: unknown;
  anyOf?: Schema[];
  allOf?: Schema[];
  items?: Schema;
  properties?: Record<string, Schema>;
  required?: string[];
  description?: string;
  title?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  additionalProperties?: boolean | Schema;
};

type Operation = {
  summary?: string;
  description?: string;
  tags?: string[];
  parameters?: { name: string; in: string; required?: boolean; schema?: Schema; description?: string }[];
  requestBody?: { content: Record<string, { schema: Schema }>; required?: boolean };
  responses: Record<string, { description?: string; content?: Record<string, { schema: Schema }> }>;
};

const doc = openapi as unknown as {
  info: { title: string; version: string; description?: string };
  paths: Record<string, Record<string, Operation>>;
  components: { schemas: Record<string, Schema> };
};

export const API_INFO = doc.info;

function refName(ref: string) {
  return ref.split("/").pop() ?? ref;
}

function resolve(s: Schema): Schema {
  return s.$ref ? (doc.components.schemas[refName(s.$ref)] ?? s) : s;
}

export function typeLabel(s: Schema): string {
  if (s.$ref) return refName(s.$ref);
  if (s.const !== undefined) return JSON.stringify(s.const);
  if (s.enum) return s.enum.map((v) => JSON.stringify(v)).join(" | ");
  if (s.anyOf) return s.anyOf.map(typeLabel).join(" | ");
  if (s.allOf) return s.allOf.map(typeLabel).join(" & ");
  if (s.type === "array") return `${s.items ? typeLabel(s.items) : "unknown"}[]`;
  if (s.type === "object" && s.additionalProperties && typeof s.additionalProperties === "object") return `Record<string, ${typeLabel(s.additionalProperties)}>`;
  return s.type ?? "any";
}

function nestedRef(s: Schema): string | null {
  if (s.$ref) return refName(s.$ref);
  for (const sub of [...(s.anyOf ?? []), ...(s.allOf ?? [])]) {
    const r = nestedRef(sub);
    if (r) return r;
  }
  if (s.items) return nestedRef(s.items);
  return null;
}

function constraints(s: Schema): string {
  const out: string[] = [];
  if (s.minimum !== undefined) out.push(`≥ ${s.minimum}`);
  if (s.maximum !== undefined) out.push(`≤ ${s.maximum}`);
  if (s.default !== undefined && s.default !== null) out.push(`default ${JSON.stringify(s.default)}`);
  return out.join(" · ");
}

export function SchemaProps({ name, depth = 0 }: { name: string; depth?: number }) {
  const s = doc.components.schemas[name];
  if (!s) return <p className="text-xs text-subtle">Unknown schema {name}.</p>;
  if (s.enum) return <p className="font-mono text-xs text-muted">{typeLabel(s)}</p>;
  const props = Object.entries(s.properties ?? {});
  if (!props.length) return <p className="font-mono text-xs text-muted">{typeLabel(s)}</p>;
  const required = new Set(s.required ?? []);
  return (
    <ul className="grid divide-y divide-hairline border-y border-hairline">
      {props.map(([key, p]) => {
        const ref = nestedRef(p);
        const refSchema = ref ? doc.components.schemas[ref] : undefined;
        const expandable = depth < 2 && ref && refSchema && (refSchema.properties || refSchema.enum);
        const extra = constraints(p);
        return (
          <li key={key} className="grid gap-1 py-2">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <code className="font-mono text-[0.8125rem] text-foreground">{key}</code>
              <span className="font-mono text-xs break-all text-muted">{typeLabel(p)}</span>
              {required.has(key) ? <span className="label-mono text-subtle">required</span> : null}
              {extra ? <span className="font-mono text-xs text-subtle">{extra}</span> : null}
            </div>
            {p.description ? <p className="text-xs text-muted">{p.description}</p> : null}
            {expandable ? (
              <div className="pl-3">
                <Disclosure title={ref} meta={refSchema.enum ? "enum" : `${Object.keys(refSchema.properties ?? {}).length} fields`} className="border-t-0">
                  <SchemaProps name={ref} depth={depth + 1} />
                </Disclosure>
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function bodySchemaName(c?: Record<string, { schema: Schema }>): string | null {
  const s = c?.["application/json"]?.schema;
  return s ? nestedRef(s) : null;
}

export function operationsForTag(tag: string) {
  const out: { method: string; path: string; op: Operation }[] = [];
  for (const [path, item] of Object.entries(doc.paths)) {
    for (const [method, op] of Object.entries(item)) {
      if (op.tags?.includes(tag)) out.push({ method: method.toUpperCase(), path, op });
    }
  }
  return out.sort((a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method));
}

export function allTags(): string[] {
  return Array.from(new Set(Object.values(doc.paths).flatMap((item) => Object.values(item).flatMap((op) => op.tags ?? []))));
}

function sampleValue(s: Schema): unknown {
  const r = resolve(s);
  if (r.const !== undefined) return r.const;
  if (r.enum?.length) return r.enum[0];
  if (r.anyOf) return sampleValue(r.anyOf.find((x) => x.type !== "null") ?? r.anyOf[0]!);
  if (r.type === "integer" || r.type === "number") return r.minimum ?? 1;
  if (r.type === "boolean") return false;
  if (r.type === "array") return [];
  if (r.type === "object") return exampleBody(r);
  return "…";
}

/** Smallest valid-looking body: required fields only (with their first enum value or minimum); optional fields use defaults. */
function exampleBody(s: Schema): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of s.required ?? []) {
    const p = s.properties?.[k];
    if (p) out[k] = sampleValue(p);
  }
  return out;
}

function exampleCurl(method: string, path: string, body: string | null) {
  const url = `localhost:8787${path.replace(/\{(\w+)\}/g, (_, p) => (p === "entry_id" ? "P01" : `<${p}>`))}`;
  if (method === "GET") return `$ curl -s ${url}`;
  const json = body ? JSON.stringify(exampleBody(doc.components.schemas[body] ?? {})) : "{}";
  return `$ curl -s -X ${method} ${url} \\\n    -H 'content-type: application/json' -d '${json}'`;
}

export function TagOperations({ tag }: { tag: string }) {
  const ops = operationsForTag(tag);
  if (!ops.length) return <p className="text-sm text-subtle">No endpoints are tagged {tag} in this build.</p>;
  return (
    <div className="grid gap-8">
      {ops.map(({ method, path, op }) => {
        const req = bodySchemaName(op.requestBody?.content);
        const ok = bodySchemaName(op.responses["200"]?.content);
        const errors = Object.entries(op.responses).filter(([code]) => code !== "200");
        const anchor = `${method}-${path}`.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "");
        return (
          <div key={`${method} ${path}`} id={anchor} className="grid scroll-mt-[calc(var(--header-h)+16px)] gap-3 border-t border-border pt-5">
            <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className={method === "GET" ? "font-mono text-xs font-medium text-muted" : "font-mono text-xs font-medium text-foreground"}>{method}</span>
              <code className="font-mono text-[0.9375rem] break-all text-foreground">{path}</code>
            </div>
            <p className="text-sm text-muted">{op.description ?? op.summary ?? "No description."}</p>
            {op.parameters?.length ? (
              <div className="grid gap-1.5">
                <p className="label-mono text-subtle">Parameters</p>
                <ul className="grid gap-1">
                  {op.parameters.map((p) => (
                    <li key={p.name} className="flex flex-wrap gap-x-2 font-mono text-xs">
                      <span className="text-foreground">{p.name}</span>
                      <span className="text-muted">{p.schema ? typeLabel(p.schema) : "string"}</span>
                      <span className="text-subtle">
                        {p.in}
                        {p.required ? " · required" : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {req ? (
              <div className="grid gap-1.5">
                <p className="label-mono text-subtle">
                  Request body · <span className="normal-case">{req}</span>
                </p>
                <SchemaProps name={req} />
              </div>
            ) : null}
            {ok ? (
              <Disclosure title={<span className="font-mono text-[0.8125rem]">200 · {ok}</span>} meta="response">
                <SchemaProps name={ok} />
              </Disclosure>
            ) : null}
            {errors.length ? (
              <p className="font-mono text-xs text-subtle">
                {errors.map(([code, r]) => `${code} ${r.description ?? ""}`.trim()).join(" · ")} — body: ApiError
              </p>
            ) : null}
            <CodeBlock code={exampleCurl(method, path, req)} />
          </div>
        );
      })}
    </div>
  );
}
