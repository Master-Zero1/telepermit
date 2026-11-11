// Meters table view (design section 13, rows from section 6).
import type { MeterRow } from '../meters';

export interface MetersProps {
  rows: MeterRow[];
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function Meters({ rows }: MetersProps) {
  return (
    <table className="meters">
      <caption>Meters. Limits are the home permit and stay fixed for the whole replay.</caption>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key}>
            <th scope="row">{row.label}</th>
            <td>
              <div className="meter-bar" aria-hidden="true">
                <div
                  className={`meter-fill ${row.over ? 'over' : 'ok'}`}
                  style={{ width: `${row.percent}%` }}
                />
              </div>
            </td>
            <td>
              {formatNumber(row.observed)} / {formatNumber(row.limit)}
              {row.over ? <strong className="over-limit"> OVER LIMIT</strong> : null}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
