import { createHash } from "node:crypto";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");

const assets = [
  {
    packageName: "htmx.org",
    source: join(root, "node_modules", "htmx.org", "dist", "htmx.min.js"),
    target: join(root, "src", "secguard_advisor", "web", "static", "js", "htmx.min.js"),
  },
  {
    packageName: "flowbite",
    source: join(root, "node_modules", "flowbite", "dist", "flowbite.min.js"),
    target: join(root, "src", "secguard_advisor", "web", "static", "js", "flowbite.min.js"),
  },
];

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

const rows = [];
for (const asset of assets) {
  const pkg = readJson(join(root, "node_modules", asset.packageName, "package.json"));
  mkdirSync(dirname(asset.target), { recursive: true });
  copyFileSync(asset.source, asset.target);
  rows.push({
    name: asset.packageName,
    version: pkg.version,
    license: typeof pkg.license === "string" ? pkg.license : "ver paquete",
    sha256: sha256(asset.target),
    source: asset.source.replace(`${root}/`, ""),
    target: asset.target.replace(`${root}/`, ""),
  });
}

const manifest = [
  "# Recursos vendorizados",
  "",
  "Generado por `npm run copy:vendor`. No editar a mano.",
  "",
  "| Recurso | Versión | Licencia | SHA-256 | Origen | Destino |",
  "|---|---|---|---|---|---|",
  ...rows.map(
    (row) =>
      `| ${row.name} | ${row.version} | ${row.license} | \`${row.sha256}\` | \`${row.source}\` | \`${row.target}\` |`,
  ),
  "",
].join("\n");

const manifestPath = join(
  root,
  "src",
  "secguard_advisor",
  "web",
  "static",
  "vendor",
  "MANIFEST.md",
);
mkdirSync(dirname(manifestPath), { recursive: true });
writeFileSync(manifestPath, manifest, "utf8");
console.log(`Recursos copiados y manifiesto escrito en ${manifestPath.replace(`${root}/`, "")}`);
