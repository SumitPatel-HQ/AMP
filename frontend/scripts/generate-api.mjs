import { writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, {
  astToString,
  COMMENT_HEADER,
} from "openapi-typescript";

const apiBaseUrl = (process.env.AMIS_API_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
const schemaUrl = new URL(`${apiBaseUrl}/openapi.json`);
const outputUrl = new URL("../src/api/schema.ts", import.meta.url);

let schemaSource = schemaUrl;
try {
  const res = await fetch(schemaUrl);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  schemaSource = await res.json();
} catch {
  // If API server is not running, generate directly from python app
  const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
  const pythonPath = process.platform === "win32"
    ? resolve(projectRoot, ".venv/Scripts/python.exe")
    : resolve(projectRoot, ".venv/bin/python");
  const pyExe = existsSync(pythonPath) ? pythonPath : "python";
  try {
    const stdout = execFileSync(
      pyExe,
      ["-c", "import json; from amis.api import app; print(json.dumps(app.openapi()))"],
      { cwd: projectRoot, encoding: "utf8", maxBuffer: 10 * 1024 * 1024 }
    );
    schemaSource = JSON.parse(stdout);
  } catch (pyErr) {
    if (existsSync(fileURLToPath(outputUrl))) {
      console.warn("Could not reach API server or python; keeping existing schema.ts.");
      process.exit(0);
    }
    throw pyErr;
  }
}

const schema = `${COMMENT_HEADER}${astToString(await openapiTS(schemaSource))}`;

await writeFile(outputUrl, schema, "utf8");
console.log(`Generated ${outputUrl.pathname}`);
