export default function Footer({ isSample }: { isSample: boolean }) {
  return (
    <footer className="span12">
      <div className="foot sans">
        <b>
          riivault publishes derived, aggregate insight and never raw or stored
          Reddit content.
        </b>{" "}
        Individual posts live only in a 48-hour processing buffer, and deletions
        are honored. The permanent asset is de-identified time series. Staying
        non-commercial keeps collection inside Reddit&rsquo;s free tier, the
        exact trap that shut GummySearch down in November 2025.
      </div>
      <div className="foot-meta">
        <span>RIIVAULT · REDDIT SIGNAL INTELLIGENCE</span>
        <span>
          {isSample
            ? "SAMPLE DATA · DESIGN PREVIEW · TERMINAL INTELLIGENCE"
            : "LIVE INDEX · DERIVED AGGREGATES ONLY · NEVER RAW CONTENT"}
        </span>
      </div>
    </footer>
  );
}
