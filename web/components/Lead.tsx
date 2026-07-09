import type { IssueData } from "@/lib/types";
import CountUp from "@/components/fx/CountUp";
import HeroChart from "@/components/HeroChart";
import TrackedRail from "@/components/TrackedRail";
import SubscribeCta from "@/components/SubscribeCta";

export default function Lead({ issue }: { issue: IssueData }) {
  const { lead } = issue;
  return (
    <div className="lead">
      <article className="story">
        <div className="eyebrow rv in s1">
          <span className="bar"></span>
          {lead.eyebrow}
        </div>
        <h1 className="head rv in s2">{lead.headline}</h1>
        <p className="dek rv in s3">{lead.dek}</p>
        <div className="byline rv in s3">
          <span>
            Synthesized from{" "}
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
            )}
          </span>
          <span>{lead.subreddits.join(" · ")}</span>
          <span>
            Window: <b>{lead.window_weeks} weeks</b>
          </span>
        </div>
        <HeroChart lead={lead} />
      </article>
      <aside className="rail">
        <TrackedRail tracked={issue.tracked} />
        <SubscribeCta />
      </aside>
    </div>
  );
}
