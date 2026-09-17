import type { ReactNode } from "react";

/**
 * The markdown subset the agent's prompt produces: `##`/`###` headings, dash
 * lists, `**bold**`, `` `code` ``, pipe tables, and `---`. ~80 lines beats a
 * dependency here, and it solves the one problem a generic renderer does not:
 * the streaming caret. The caret has to render INSIDE whatever block the last
 * token landed in (a list item, a table cell), so the source text carries a
 * sentinel character and every text leaf splits on it.
 */

const CURSOR = "\uE000";

function leaf(text: string, key: string): ReactNode[] {
  const at = text.indexOf(CURSOR);
  if (at < 0) return [text];
  const out: ReactNode[] = [];
  if (at > 0) out.push(text.slice(0, at));
  out.push(<span className="cur" key={`${key}-cur`} />);
  const rest = text.slice(at + 1);
  if (rest) out.push(rest);
  return out;
}

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*(.+?)\*\*|`([^`]+)`)/g;
  let match: RegExpExecArray | null = null;
  let last = 0;
  let n = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) out.push(...leaf(text.slice(last, match.index), `${key}t${n}`));
    n += 1;
    if (match[2] !== undefined) {
      out.push(
        <strong className="md-b" key={`${key}b${n}`}>
          {leaf(match[2], `${key}bi${n}`)}
        </strong>,
      );
    } else {
      out.push(
        <code className="md-c" key={`${key}c${n}`}>
          {leaf(match[3], `${key}ci${n}`)}
        </code>,
      );
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) out.push(...leaf(text.slice(last), `${key}e`));
  return out;
}

function table(rows: string[], key: string): ReactNode {
  const cells = (row: string) =>
    row
      .replace(/^\|/, "")
      .replace(/\|\s*$/, "")
      .split("|")
      .map((cell) => cell.trim());
  const head = cells(rows[0]);
  // rows[1] is the |---|---| separator
  const body = rows.slice(2).map(cells);
  return (
    <div className="md-tw" key={key}>
      <table className="md-t">
        <thead>
          <tr>
            {head.map((cell, i) => (
              <th className="md-th" key={i}>
                {inline(cell, `${key}h${i}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td className={ci === 0 ? "md-td md-td0" : "md-td"} key={ci}>
                  {inline(cell, `${key}d${ri}_${ci}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Markdown({ text, streaming = false }: { text: string; streaming?: boolean }) {
  const lines = (streaming ? text + CURSOR : text).split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  let k = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*$/.test(line)) {
      i += 1;
    } else if (/^---+\s*$/.test(line)) {
      out.push(<hr className="md-hr" key={k++} />);
      i += 1;
    } else if (/^###\s/.test(line)) {
      out.push(
        <h3 className="md-h3" key={k++}>
          {inline(line.replace(/^###\s*/, ""), `h${k}`)}
        </h3>,
      );
      i += 1;
    } else if (/^##\s/.test(line)) {
      out.push(
        <h2 className="md-h2" key={k++}>
          {inline(line.replace(/^##\s*/, ""), `h${k}`)}
        </h2>,
      );
      i += 1;
    } else if (/^[-*]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, ""));
        i += 1;
      }
      out.push(
        <ul className="md-ul" key={k++}>
          {items.map((item, j) => (
            <li className="md-li" key={j}>
              {inline(item, `l${k}_${j}`)}
            </li>
          ))}
        </ul>,
      );
    } else if (/^\|/.test(line)) {
      const rows: string[] = [];
      while (i < lines.length && /^\|/.test(lines[i])) {
        rows.push(lines[i]);
        i += 1;
      }
      out.push(table(rows, `tb${k++}`));
    } else {
      // Always consume the line the paragraph started on: a streaming
      // boundary can leave a line that no block branch claims but the
      // block-start exclusion below still matches (e.g. "---" or "##" with
      // the caret sentinel appended), and skipping it would loop forever.
      const para: string[] = [lines[i]];
      i += 1;
      while (i < lines.length && !/^\s*$/.test(lines[i]) && !/^(###|##|---|[-*]\s|\|)/.test(lines[i])) {
        para.push(lines[i]);
        i += 1;
      }
      out.push(
        <p className="md-p" key={k++}>
          {inline(para.join(" "), `p${k}`)}
        </p>,
      );
    }
  }
  return <div className="md">{out}</div>;
}
