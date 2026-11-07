import { headingClass } from "@/lib/styles";
import { parseAnswerTable, splitAnswer, toChartPoints } from "../lib/answerParsing";
import { formatModelTime } from "../lib/modelTime";
import { AnswerChart } from "./AnswerChart";

const TABLE_COLUMNS = ["time", "metric", "value", "low", "high", "confidence"];

/** The model's final answer: a chart when it has several points, otherwise a table, then its own words. */
export function ForecastAnswer({ answer }: { answer: string }) {
  const table = parseAnswerTable(answer);
  const points = table ? toChartPoints(table) : [];
  const columns = table ? TABLE_COLUMNS.filter((column) => table.header.includes(column)) : [];
  const { text } = splitAnswer(answer);
  return (
    <div className="shrink-0">
      <h3 className={`${headingClass} text-lg`}>Forecast.</h3>
      {points.length > 1 && <div className="mt-2 rounded-lg border border-border bg-card p-3"><AnswerChart points={points} /></div>}
      {points.length <= 1 && table && columns.length > 0 && (
        <table className="mt-1 w-full text-left text-sm" data-testid="harness-table">
          <thead>
            <tr>{columns.map((column) => <th key={column} className="border-b border-border py-1 pr-3 font-medium text-foreground">{column}</th>)}</tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowNumber) => (
              <tr key={rowNumber}>
                {columns.map((column) => {
                  const value = row[table.header.indexOf(column)] ?? "";
                  return <td key={column} className="py-1 pr-3 tabular-nums text-foreground">{column === "time" ? formatModelTime(value) : value}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{text}</div>
    </div>
  );
}
