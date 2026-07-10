import type { IssueData } from "@/lib/types";
import CountUp from "@/components/fx/CountUp";

export default function Lead({ issue }: { issue: IssueData }) {
  const { lead } = issue;
  return (
    <section className="panel lead-panel span8">
      <div className="eyebrow">{lead.eyebrow}</div>
      <h1 className="head sans">{lead.headline}</h1>
      <p className="dek sans">{lead.dek}</p>
      <p className="srcline">
        SRC:{" "}
        <b>
          <CountUp end={lead.threads} comma />
        </b>{" "}
        threads
        {lead.comments != null && (
          <>
            {" "}
            ·{" "}
            <b>
              <CountUp end={lead.comments} comma />
            </b>{" "}
            comments
          </>
        )}{" "}
        · {lead.subreddits.join(" ")} · window <b>{lead.window_weeks}w</b>
      </p>
    </section>
  );
}
