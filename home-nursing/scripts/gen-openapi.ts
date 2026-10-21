/**
 * Generates public/openapi.json from the route files: every path, method and required permission.
 * Request schemas are extracted from the inline Zod `body:` definitions by importing each route module's
 * registered schema where available. Run: npm run openapi
 */
import fs from "node:fs";
import path from "node:path";

const root = path.join(__dirname, "../src/app/api/v1");
const out: Record<string, Record<string, unknown>> = {};

function walk(dir: string) {
  for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, f.name);
    if (f.isDirectory()) walk(p);
    else if (f.name === "route.ts") {
      const src = fs.readFileSync(p, "utf8");
      const rel = "/api/v1/" + path.relative(root, path.dirname(p)).split(path.sep).map((s) => s.replace(/^\[(.+)\]$/, "{$1}")).join("/");
      const doc = src.match(/\/\*\*\s*([\s\S]*?)\*\//)?.[1]?.replace(/\n\s*\*\s?/g, " ").trim();
      for (const m of src.matchAll(/export (?:const|async function) (GET|POST|PUT|PATCH|DELETE)\b([\s\S]*?)(?=export (?:const|async function)|$)/g)) {
        const method = m[1]!.toLowerCase();
        const body = m[2]!;
        const perm = body.match(/permission:\s*"([^"]+)"/)?.[1];
        const hasBody = /body:\s*z\./.test(body);
        const params = [...rel.matchAll(/\{(\w+)\}/g)].map((x) => ({ name: x[1], in: "path", required: true, schema: { type: "string" } }));
        (out[rel] ??= {})[method] = {
          summary: doc,
          ...(params.length ? { parameters: params } : {}),
          ...(perm ? { security: [{ session: [] }], "x-permission": perm } : { security: [] }),
          ...(hasBody ? { requestBody: { required: true, content: { "application/json": { schema: { type: "object", description: "Validated by the Zod schema in " + path.relative(path.join(__dirname, ".."), p) } } } } } : {}),
          responses: { "200": { description: "{ data: ... }" }, "4XX": { $ref: "#/components/responses/Error" } },
        };
      }
    }
  }
}
walk(root);

const spec = {
  openapi: "3.1.0",
  info: { title: "HomeNurse India API", version: "1.0.0", description: "Generated from route files. Errors: { error: { code, message, details } }." },
  servers: [{ url: "/" }],
  components: {
    securitySchemes: { session: { type: "apiKey", in: "cookie", name: "hn_session" } },
    responses: { Error: { description: "Error", content: { "application/json": { schema: { type: "object", properties: { error: { type: "object", properties: { code: { type: "string" }, message: { type: "string" }, details: {} } } } } } } } },
  },
  paths: Object.fromEntries(Object.entries(out).sort(([a], [b]) => a.localeCompare(b))),
};
fs.mkdirSync(path.join(__dirname, "../public"), { recursive: true });
fs.writeFileSync(path.join(__dirname, "../public/openapi.json"), JSON.stringify(spec, null, 2));
console.log(`openapi.json: ${Object.keys(out).length} paths`);
