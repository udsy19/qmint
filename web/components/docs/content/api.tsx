import { API_TAGS } from "../registry";
import { API_INFO, SchemaProps, TagOperations } from "../api-reference";
import { CodeBlock } from "../code-block";
import { C, P, UL } from "../prose";

export const content: Record<string, React.ReactNode> = {
  conventions: (
    <>
      <P>
        {API_INFO.title} {API_INFO.version}. {API_INFO.description} Base path <C>/api/v1</C>; JSON only; the web app calls it
        same-origin through a Next.js rewrite.
      </P>
      <UL>
        <li>
          Every response is an envelope: <C>status</C> (<C>OK</C>, <C>DEMO_ADAPTER</C> or <C>NOT_AVAILABLE</C>),{" "}
          <C>evidence_kind</C> of the headline numbers, <C>provenance</C>, <C>reason</C> (required unless <C>OK</C>) and{" "}
          <C>data</C>.
        </li>
        <li>
          Every displayable number is a <C>Quantity</C>. <C>value: null</C> means not available — never 0.
        </li>
        <li>This page is generated from <C>web/lib/api/openapi.json</C>; regenerate it with <C>pnpm gen:api</C>.</li>
      </UL>
      <p className="label-mono text-subtle">Quantity</p>
      <SchemaProps name="Quantity" />
      <p className="label-mono text-subtle">ApiProvenance</p>
      <SchemaProps name="ApiProvenance" />
    </>
  ),
  ...Object.fromEntries(API_TAGS.map((t) => [`tag-${t}`, <TagOperations key={t} tag={t} />])),
  errors: (
    <>
      <P>
        Every 4xx and 5xx response, including request validation, has the same body. Validation errors are{" "}
        <C>422 validation_error</C> with pydantic&apos;s error list in <C>detail</C>; unknown routes and research ids are{" "}
        <C>404 not_found</C>.
      </P>
      <CodeBlock code={`{ "error": { "code": "not_found", "message": "unknown research entry 'NOPE'", "detail": null } }`} lang="json" />
      <SchemaProps name="ApiErrorBody" />
    </>
  ),
};
