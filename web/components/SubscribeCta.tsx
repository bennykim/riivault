"use client";

import { useState } from "react";

const INITIAL = "FREE · 3,400+ FOUNDERS & PMS · NO RAW CONTENT";
const SUCCESS = "SUBSCRIBED · FIRST ISSUE LANDS NEXT TUESDAY ✓";
const INVALID = "ENTER A VALID EMAIL TO GET TUESDAY'S SIGNAL";

export default function SubscribeCta() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState(INITIAL);
  const [buttonLabel, setButtonLabel] = useState("Subscribe");

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = email.trim();
    if (!value || value.indexOf("@") < 1) {
      setMessage(INVALID);
      return;
    }
    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: value }),
      });
      if (!res.ok) {
        setMessage(INVALID);
        return;
      }
    } catch {
      setMessage(INVALID);
      return;
    }
    setMessage(SUCCESS);
    setButtonLabel("Done");
    setEmail("");
  };

  return (
    <section className="panel span4 sub-panel">
      <div className="ph">
        <span>The Tuesday Signal</span>
      </div>
      <h3 className="sans">Get the signal, already read for you.</h3>
      <p className="sans">
        One email every Tuesday: rising pain points, sentiment flips, and
        emerging bets from 34 founder communities.
      </p>
      <form className="sub-form" onSubmit={onSubmit}>
        <input
          type="email"
          aria-label="Email address"
          placeholder="you@maker.co"
          name="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button type="submit">{buttonLabel}</button>
      </form>
      <p className="sub-fine">{message}</p>
    </section>
  );
}
