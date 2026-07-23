import { getIssue } from "@/lib/api";
import { sampleIssue } from "@/lib/sample";
import Masthead from "@/components/Masthead";
import Ticker from "@/components/Ticker";
import Lead from "@/components/Lead";
import TrackedRail from "@/components/TrackedRail";
import KpiCards from "@/components/KpiCards";
import HeroChart from "@/components/HeroChart";
import SubscribeCta from "@/components/SubscribeCta";
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
    <div className="page">
      <Masthead issue={issue} isSample={isSample} />
      <Ticker issue={issue} />
      <div className="grid">
        <Lead issue={issue} />
        <TrackedRail tracked={issue.tracked} />
        <KpiCards issue={issue} />
        <HeroChart lead={issue.lead} />
        <SubscribeCta />
        <PainPointsFeed issue={issue} />
        <SignalCharts issue={issue} />
        <EmergingSignals emerging={issue.emerging} />
        <Footer isSample={isSample} />
      </div>
    </div>
  );
}
