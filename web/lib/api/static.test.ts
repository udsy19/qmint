import { describe, expect, it } from "vitest";
import { canonicalJson, sha256Hex, snapshotPath } from "./static";

// Same body and digest as tests/unit/api/test_static_snapshot.py: the browser and
// scripts/build_static_site.py must derive identical snapshot keys.
const BODY = { z: [1.0, 1e-9, null, true, 'é/"x'], a: { lo: 6e-6, hi: 40000000 }, m: 0.17453292519943295 };
const CANON = '{"a":{"hi":40000000,"lo":0.000006},"m":0.17453292519943295,"z":[1,1e-9,null,true,"é/\\"x"]}';
const KEY = "233cfcf1a7dda50a973938b0551b5bf0c4d89d2a4527dbc0d22400e6139a8014";

describe("static snapshot keys", () => {
  it("canonicalises with sorted keys and JS number text", () => {
    expect(canonicalJson(BODY)).toBe(CANON);
    expect(canonicalJson({ b: undefined, a: 1 })).toBe('{"a":1}');
  });

  it("hashes identically to the Python generator", async () => {
    expect(await sha256Hex(canonicalJson(BODY))).toBe(KEY);
  });

  it("maps a request to <method>/<path>/<key>.json", async () => {
    expect(await snapshotPath("POST", "/api/v1/lab/attack", BODY)).toBe(`post/api/v1/lab/attack/${KEY}.json`);
    expect(await snapshotPath("GET", "/api/v1/meta", undefined)).toBe("get/api/v1/meta/44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a.json");
  });
});
