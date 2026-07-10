import type { EmergingSignal, SignalType } from "@/lib/types";

function metaFor(type: SignalType): { color: string; label: string } {
  switch (type) {
    case "new_topic":
      return { color: "var(--pos)", label: "✦ NEW TOPIC" };
    case "sentiment_flip":
      return { color: "var(--sentiment)", label: "▼ SENTIMENT FLIP" };
    case "migration":
      return { color: "var(--primary-hi)", label: "◆ MIGRATION" };
    case "spike":
    default:
      return { color: "var(--primary-hi)", label: "◆ VOLUME SPIKE" };
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
    <>
      {emerging.map((signal) => {
        const meta = metaFor(signal.signal_type);
        const w = Math.round(signal.strength * 100);
        return (
          <section className="panel span4 sig-panel" key={signal.signal_id}>
            <div>
              <span
                className="kindtag"
                style={{ color: meta.color, borderColor: meta.color }}
              >
                {meta.label}
              </span>
            </div>
            <h3 className="sans">{signal.entity}</h3>
            <p className="sans">{signal.description}</p>
            <div className="strength">
              <span
                className="bar"
                style={{
                  background: `linear-gradient(to right, ${meta.color} ${w}%, var(--panel2) ${w}%)`,
                }}
              ></span>
              <span>
                STR {signal.strength.toFixed(2)} ·{" "}
                {signal.detected_label.toUpperCase()}
              </span>
            </div>
          </section>
        );
      })}
    </>
  );
}
