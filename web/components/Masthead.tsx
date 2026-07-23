import type { IssueData } from "@/lib/types";
import { dottedDate } from "@/lib/format";
import ThemeToggle from "@/components/ThemeToggle";

export default function Masthead({
  issue,
  isSample,
}: {
  issue: IssueData;
  isSample: boolean;
}) {
  return (
    <header className="bar">
      <span className="wm">
        riivault<span>_</span>
      </span>
      <span className="sep">/</span>
      <span className="sys">BUILDER SIGNAL INTELLIGENCE</span>
      <div className="right">
        {/* Must agree with the Footer's SAMPLE/LIVE line — never claim Live
            while rendering the bundled sample fallback. */}
        <span className={isSample ? "chip" : "chip live"}>
          {isSample ? "○ Sample" : "● Live"}
        </span>
        <span className="chip">Issue {issue.issue_no}</span>
        <span className="chip">{dottedDate(issue.week_end)}</span>
        <span className="chip">{issue.sources.length} sources</span>
        <ThemeToggle />
      </div>
    </header>
  );
}
