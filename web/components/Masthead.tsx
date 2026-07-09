import { Badge } from "@astryxdesign/core/Badge";
import type { IssueData } from "@/lib/types";
import { dottedDate } from "@/lib/format";
import MastheadNav from "@/components/MastheadNav";

export default function Masthead({ issue }: { issue: IssueData }) {
  return (
    <header className="masthead">
      <div className="top-row">
        <div className="brand rv in">
          <div className="wordmark">
            riivault<span className="dot">.</span>
          </div>
          <div className="kicker">
            Reddit Signal
            <br />
            Intelligence
          </div>
        </div>
        <div className="issue rv in s1">
          <Badge variant="success" label="Live index" />
          <br />
          <b>Issue {issue.issue_no}</b> · {dottedDate(issue.week_end)}
          <br />
          r/{issue.niche} &amp; <b>{issue.communities}</b> communities
        </div>
      </div>
      <div className="rule"></div>
      <MastheadNav />
    </header>
  );
}
