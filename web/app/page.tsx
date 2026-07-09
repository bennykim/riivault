import { getIssue } from "@/lib/api";
import { sampleIssue } from "@/lib/sample";
import Reveal from "@/components/fx/Reveal";
import Masthead from "@/components/Masthead";
import Lead from "@/components/Lead";
import PainPointsFeed from "@/components/PainPointsFeed";
import SignalCharts from "@/components/SignalCharts";
import EmergingSignals from "@/components/EmergingSignals";
import Footer from "@/components/Footer";

// Live data via no-store fetch; render at request time so a fresh issue is
// always reflected (and the sample fallback is exercised when the API is down).
export const dynamic = "force-dynamic";

export default async function Page() {
  const live = await getIssue();
  const issue = live ?? sampleIssue;
  const isSample = live === null;

  return (
    <>
      <Reveal />
      <div className="wrap">
        <Masthead issue={issue} />
        <Lead issue={issue} />
        <PainPointsFeed issue={issue} />
        <SignalCharts issue={issue} />
        <EmergingSignals emerging={issue.emerging} />
        <Footer isSample={isSample} />
      </div>
    </>
  );
}
