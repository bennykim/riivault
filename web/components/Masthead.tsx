import type { IssueData } from "@/lib/types";
import { dottedDate } from "@/lib/format";

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
          <span className="pill">
            <span className="live"></span>Live index
          </span>
          <br />
          <b>Issue {issue.issue_no}</b> · {dottedDate(issue.week_end)}
          <br />
          r/{issue.niche} &amp; <b>{issue.communities}</b> communities
        </div>
      </div>
      <div className="rule"></div>
      <nav className="strip">
        <a href="#" className="active">
          This Week
        </a>
        <a href="#">Pain Points</a>
        <a href="#">Signals</a>
        <a href="#">Tracked</a>
        <a href="#">Communities</a>
        <a href="#">Archive</a>
      </nav>
    </header>
  );
}
