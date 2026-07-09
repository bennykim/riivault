import { Badge } from "@astryxdesign/core/Badge";
import type { BadgeVariant } from "@astryxdesign/core/Badge";
import { Card } from "@astryxdesign/core/Card";
import { ProgressBar } from "@astryxdesign/core/ProgressBar";
import type { ProgressBarVariant } from "@astryxdesign/core/ProgressBar";
import type { EmergingSignal, SignalType } from "@/lib/types";

function metaFor(type: SignalType): {
  badge: BadgeVariant;
  meter: ProgressBarVariant;
  label: string;
} {
  switch (type) {
    case "new_topic":
      return { badge: "success", meter: "success", label: "✦ New topic" };
    case "sentiment_flip":
      return { badge: "info", meter: "warning", label: "▼ Sentiment flip" };
    case "migration":
      return { badge: "warning", meter: "accent", label: "◆ Migration" };
    case "spike":
    default:
      return { badge: "warning", meter: "accent", label: "◆ Volume spike" };
  }
}

export default function EmergingSignals({
  emerging,
}: {
  emerging: EmergingSignal[];
}) {
  // Real emerging signals ship in Phase 3; until then hide the section rather
  // than render an empty grid.
  if (emerging.length === 0) return null;
  return (
    <section className="blk">
      <div className="sechead rv">
        <h2>Emerging signals</h2>
        <span className="sub">Caught before the spike · validated post-hoc</span>
      </div>
      <div className="cards">
        {emerging.map((signal) => {
          const meta = metaFor(signal.signal_type);
          return (
            <Card className="ecard rv" key={signal.signal_id}>
              <span>
                <Badge variant={meta.badge} label={meta.label} />
              </span>
              <div className="ent">{signal.entity}</div>
              <p className="desc">{signal.description}</p>
              <ProgressBar
                value={signal.strength}
                max={1}
                label="Signal strength"
                isLabelHidden
                variant={meta.meter}
              />
              <div className="foot">
                <span>Strength {signal.strength.toFixed(2)}</span>
                <span>{signal.detected_label}</span>
              </div>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
