import { Badge } from "@astryxdesign/core/Badge";
import { Card } from "@astryxdesign/core/Card";

export default function Footer({ isSample }: { isSample: boolean }) {
  return (
    <footer>
      <Card className="compliance rv">
        <Badge variant="neutral" label="Built to last" />
        <p>
          <b>
            riivault publishes derived, aggregate insight — never raw or stored
            Reddit content.
          </b>{" "}
          Individual posts live only in a &lt;48h processing buffer; deletions
          are honored and the permanent asset is de-identified time-series.
          Staying non-commercial keeps collection inside Reddit&rsquo;s free tier
          — the exact trap that shut GummySearch down in Nov 2025.
        </p>
      </Card>
      <div className="foot-meta">
        <span>riivault · Reddit Signal Intelligence</span>
        <span>
          {isSample
            ? "Sample data — design preview · Astryx design system"
            : "Live index — derived aggregates only, never raw content"}
        </span>
      </div>
    </footer>
  );
}
