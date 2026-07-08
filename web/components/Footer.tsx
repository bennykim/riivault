export default function Footer({ isSample }: { isSample: boolean }) {
  return (
    <footer>
      <div className="compliance rv">
        <span className="badge">Built to last</span>
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
      </div>
      <div className="foot-meta">
        <span>riivault · Reddit Signal Intelligence</span>
        <span>
          {isSample
            ? "Sample data — design preview · Editorial × Living-Intelligence UX"
            : "Live index — derived aggregates only, never raw content"}
        </span>
      </div>
    </footer>
  );
}
