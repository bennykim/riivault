export default function Footer({ isSample }: { isSample: boolean }) {
  return (
    <footer className="span12">
      <div className="foot sans">
        <b>
          riivault publishes derived, aggregate insight and never raw or stored
          source content.
        </b>{" "}
        Individual posts live only in a 48-hour processing buffer, and deletions
        are honored. The permanent asset is de-identified time series, built
        from public APIs under each provider&rsquo;s terms.
      </div>
      <div className="foot-meta">
        <span>RIIVAULT · BUILDER SIGNAL INTELLIGENCE</span>
        <span>
          {isSample
            ? "SAMPLE DATA · DESIGN PREVIEW · TERMINAL INTELLIGENCE"
            : "LIVE INDEX · DERIVED AGGREGATES ONLY · NEVER RAW CONTENT"}
        </span>
      </div>
    </footer>
  );
}
