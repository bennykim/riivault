import type { TrackedEntity } from "@/lib/types";
import { sparkColor, sparkPoints } from "@/lib/chart";

export default function TrackedRail({ tracked }: { tracked: TrackedEntity[] }) {
  return (
    <section className="panel span4">
      <div className="ph">
        <span>Tracked entities</span>
        <b>7d Δ</b>
      </div>
      <table className="ttab">
        <tbody>
          {tracked.map((t) => {
            // change_pct is null when the prior 7-day window had no mentions.
            const up = t.change_pct != null && t.change_pct >= 0;
            return (
              <tr key={t.entity_id}>
                <td>
                  <span className="en">{t.name}</span>
                  <br />
                  <span className="ec">{t.context ?? ""}</span>
                </td>
                <td className="spk">
                  <svg width="72" height="22" viewBox="0 0 72 22" aria-hidden="true">
                    <polyline
                      points={sparkPoints(t.spark)}
                      fill="none"
                      stroke={sparkColor(t.spark)}
                      strokeWidth="1.8"
                    />
                  </svg>
                </td>
                <td className={`delta ${up ? "up" : "down"}`}>
                  {t.change_pct == null
                    ? "—"
                    : `${up ? "▲" : "▼"} ${Math.abs(Math.round(t.change_pct))}%`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
