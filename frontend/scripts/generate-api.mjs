import { writeFile } from "node:fs/promises";
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
const schema = `${COMMENT_HEADER}${astToString(await openapiTS(schemaUrl))}`;

await writeFile(outputUrl, schema, "utf8");
console.log(`Generated ${outputUrl.pathname} from ${schemaUrl.href}`);
