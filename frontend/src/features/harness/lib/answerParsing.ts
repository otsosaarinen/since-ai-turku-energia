import type { AnswerPoint, AnswerTable } from "../types";
import { parseModelTime } from "./modelTime";

/**
 * Where the table is in an answer: a ```csv block, any code block that starts like a table, or plain comma-separated lines
 * (small models often skip the fence). `text` is the answer without the table.
 */
export function splitAnswer(answer: string): { csv: string | null; text: string } {
  const csvBlock = answer.match(/```csv[ \t]*\n([\s\S]*?)```/);
  if (csvBlock) return { csv: csvBlock[1], text: answer.replace(csvBlock[0], "").trim() };
  for (const block of answer.matchAll(/```[a-z]*[ \t]*\n([\s\S]*?)```/g)) {
    const firstLine = block[1].trim().split("\n")[0].toLowerCase();
    if (firstLine.includes("time") && firstLine.includes("value")) return { csv: block[1], text: answer.replace(block[0], "").trim() };
  }
  const lines = answer.split("\n");
  const headerLine = lines.findIndex((line) => line.includes(",") && /(^|,)\s*time\s*(,|$)/i.test(line) && /(^|,)\s*value\s*(,|$)/i.test(line));
  if (headerLine < 0) return { csv: null, text: answer.trim() };
  let endLine = headerLine + 1;
  while (endLine < lines.length && lines[endLine].includes(",")) endLine++;
  return {
    csv: lines.slice(headerLine, endLine).join("\n"),
    text: [...lines.slice(0, headerLine), ...lines.slice(endLine)].join("\n").trim(),
  };
}

function splitCsvLine(line: string): string[] {
  const fields: string[] = [];
  let current = "";
  let insideQuotes = false;
  for (let position = 0; position < line.length; position++) {
    const character = line[position];
    if (character === '"') {
      if (insideQuotes && line[position + 1] === '"') { current += '"'; position++; }
      else insideQuotes = !insideQuotes;
    } else if (character === "," && !insideQuotes) {
      fields.push(current);
      current = "";
    } else current += character;
  }
  fields.push(current);
  return fields.map((field) => field.trim());
}

/** The table in an answer (header and rows), or null. Understands "quoted, fields". */
export function parseAnswerTable(answer: string): AnswerTable | null {
  const { csv } = splitAnswer(answer);
  if (!csv) return null;
  const lines = csv.trim().split("\n").filter((line) => line.trim()).map(splitCsvLine);
  return lines.length ? { header: lines[0], rows: lines.slice(1) } : null;
}

/** Points for the answer chart: value with its low-high range, from the time / value / low / high columns. */
export function toChartPoints(table: AnswerTable): AnswerPoint[] {
  const columnOf = (name: string) => table.header.indexOf(name);
  const cell = (row: string[], name: string) => (columnOf(name) >= 0 ? (row[columnOf(name)] ?? "") : "");
  if (columnOf("time") < 0 || columnOf("value") < 0) return [];
  return table.rows
    .map((row) => {
      const value = Number(row[columnOf("value")]);
      const low = columnOf("low") >= 0 && row[columnOf("low")] !== "" ? Number(row[columnOf("low")]) : value;
      const high = columnOf("high") >= 0 && row[columnOf("high")] !== "" ? Number(row[columnOf("high")]) : value;
      return {
        ms: parseModelTime(row[columnOf("time")]),
        value,
        base: Math.min(low, high, value),
        width: Math.max(Math.abs(high - low), 0),
        low,
        high,
        confidence: cell(row, "confidence"),
        drivers: cell(row, "drivers"),
      };
    })
    .filter((point) => Number.isFinite(point.ms) && Number.isFinite(point.value) && Number.isFinite(point.base) && Number.isFinite(point.width))
    .sort((a, b) => a.ms - b.ms);
}
