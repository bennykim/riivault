"use client";

import { useState } from "react";
import { Tab, TabList } from "@astryxdesign/core/TabList";

const TABS = [
  "This Week",
  "Pain Points",
  "Signals",
  "Tracked",
  "Communities",
  "Archive",
];

export default function MastheadNav() {
  const [tab, setTab] = useState(TABS[0]);
  return (
    <nav className="strip" aria-label="Sections">
      <TabList value={tab} onChange={setTab} size="sm" layout="hug">
        {TABS.map((t) => (
          <Tab key={t} value={t} label={t} />
        ))}
      </TabList>
    </nav>
  );
}
