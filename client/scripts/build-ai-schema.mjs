// Bundles every block schema into one self-contained JSON Schema for the
// backend tool definition: src/components/ai-document.schema.json
//
//   npm run schema
//
// Run it after editing any *.schema.json under src/components.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "components");
const read = (p) => JSON.parse(readFileSync(join(root, p), "utf8"));

const charts = {
  bar_chart: "charts/bar-chart/bar-chart.schema.json",
  line_chart: "charts/line-chart/line-chart.schema.json",
  histogram: "charts/histogram/histogram.schema.json",
  pie_chart: "charts/pie-chart/pie-chart.schema.json",
  scatter_plot: "charts/scatter-plot/scatter-plot.schema.json",
  gantt_chart: "charts/gantt-chart/gantt-chart.schema.json",
};

const text = read("blocks/text-blocks.schema.json").$defs;

const defs = { ...text };
for (const [type, path] of Object.entries(charts)) {
  const { $schema: _s, ...schema } = read(path);
  defs[type] = schema;
}

const leafTypes = Object.keys(defs);
const variant = (type) => ({
  type: "object",
  description: defs[type].description,
  required: ["type", "props"],
  additionalProperties: false,
  properties: {
    type: { const: type },
    props: { $ref: `#/$defs/${type}` },
  },
});

const schema = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  title: "AiDocument",
  description: [
    "A visual answer for the user, rendered top to bottom as an ordered list of blocks.",
    "Mix text and charts freely, e.g. heading → stats → bar_chart → heading → paragraph → pie_chart.",
    "Guidelines: open with the answer (a lead paragraph or stats), then evidence.",
    "Give every chart a nearby sentence saying what to notice; don't repeat the chart's numbers in prose.",
    "Use a row to show 2–3 related charts side by side (they stack on phones).",
    "Prefer one well-chosen chart over several similar ones.",
  ].join(" "),
  type: "object",
  required: ["blocks"],
  additionalProperties: false,
  properties: {
    blocks: { type: "array", minItems: 1, items: { $ref: "#/$defs/block" } },
  },
  $defs: {
    block: { oneOf: [...leafTypes.map(variant), { $ref: "#/$defs/rowBlock" }] },
    leafBlock: { oneOf: leafTypes.map(variant) },
    rowBlock: {
      type: "object",
      description: "Place 2–3 blocks side by side (usually charts or stats). Stacks vertically on small screens. Rows can't be nested.",
      required: ["type", "props"],
      additionalProperties: false,
      properties: {
        type: { const: "row" },
        props: {
          type: "object",
          required: ["blocks"],
          additionalProperties: false,
          properties: {
            columns: { type: "integer", enum: [1, 2, 3], description: "Defaults to the number of blocks (max 3)." },
            blocks: { type: "array", minItems: 1, maxItems: 3, items: { $ref: "#/$defs/leafBlock" } },
          },
        },
      },
    },
    ...defs,
  },
};

const out = join(root, "ai-document.schema.json");
writeFileSync(out, JSON.stringify(schema, null, 2) + "\n");
console.log(`wrote ${out} (${leafTypes.length} block types + row)`);
