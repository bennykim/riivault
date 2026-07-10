import type { IssueData } from "@/lib/types";
import { dottedDate } from "@/lib/format";
import ThemeToggle from "@/components/ThemeToggle";

export default function Masthead({ issue }: { issue: IssueData }) {
  return (
    <header className="bar">
      <span className="wm">
        riivault<span>_</span>
      </span>
      <span className="sep">/</span>
      <span className="sys">REDDIT SIGNAL INTELLIGENCE</span>
      <div className="right">
        <span className="chip live">● Live</span>
        <span className="chip">Issue {issue.issue_no}</span>
        <span className="chip">{dottedDate(issue.week_end)}</span>
        <span className="chip">{issue.communities} communities</span>
        <ThemeToggle />
      </div>
    </header>
  );
}
