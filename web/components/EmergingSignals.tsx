import type { EmergingSignal, SignalType } from "@/lib/types";
import { vars } from "@/lib/format";
import TiltCard from "@/components/fx/TiltCard";

function metaFor(type: SignalType): {
  cls: string;
  label: string;
  color: string;
} {
  switch (type) {
    case "new_topic":
      return { cls: "newtopic", label: "✦ New topic", color: "var(--pos)" };
    case "sentiment_flip":
      return { cls: "flip", label: "▼ Sentiment flip", color: "var(--neg)" };
    case "migration":
      return { cls: "spike", label: "◆ Migration", color: "var(--ember)" };
    case "spike":
    default:
      return { cls: "spike", label: "◆ Volume spike", color: "var(--ember)" };
  }
}

export default function EmergingSignals({
  emerging,
}: {
  emerging: EmergingSignal[];
}) {
  return (
    <section className="blk">
      <div className="sechead rv">
        <h2>Emerging signals</h2>
        <span className="sub">Caught before the spike · validated post-hoc</span>
      </div>
      <div className="cards">
        {emerging.map((signal) => {
          const meta = metaFor(signal.signal_type);
          const width = `${Math.round(signal.strength * 100)}%`;
          return (
            <TiltCard className={`ecard ${meta.cls} rv`} key={signal.signal_id}>
              <span className="type">{meta.label}</span>
              <div className="ent">{signal.entity}</div>
              <p className="desc">{signal.description}</p>
              <div className="meter">
                <i style={vars({ "--w": width, background: meta.color })}></i>
              </div>
              <div className="foot">
                <span>Strength {signal.strength.toFixed(2)}</span>
                <span>{signal.detected_label}</span>
              </div>
            </TiltCard>
          );
        })}
      </div>
    </section>
  );
}
