import type { TrackedEntity } from "@/lib/types";
import { sparkColor, sparkPoints } from "@/lib/chart";
import { pctLabel } from "@/lib/format";

export default function TrackedRail({ tracked }: { tracked: TrackedEntity[] }) {
  return (
    <div className="rv in s3">
      <h3>Tracked entities</h3>
      <div className="track">
        {tracked.map((t) => {
          const up = t.change_pct >= 0;
          return (
            <div className="row" key={t.entity_id}>
              <div className="name">
                {t.name} <span>{t.context}</span>
              </div>
              <svg width="72" height="22" viewBox="0 0 72 22" aria-hidden="true">
                <polyline
                  points={sparkPoints(t.spark)}
                  fill="none"
                  stroke={sparkColor(t.spark)}
                  strokeWidth="1.8"
                />
              </svg>
              <div className={`chg ${up ? "up" : "down"} tnum`}>
                {pctLabel(t.change_pct)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
