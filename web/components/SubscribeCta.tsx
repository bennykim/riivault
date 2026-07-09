"use client";

import { useState } from "react";

const INITIAL = "Free · 3,400+ founders & PMs · no raw content, ever.";
const SUCCESS = "Subscribed — first issue lands next Tuesday. ✓";
const INVALID = "Enter a valid email to get Tuesday’s signal.";

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
    <div className="cta rv in s4">
      <div className="k">The Tuesday Signal</div>
      <h4>Get the Reddit signal, read for you.</h4>
      <p>
        One email, every Tuesday. The week&rsquo;s rising pains, sentiment flips,
        and emerging bets — synthesized, not scraped.
      </p>
      <form className="form" onSubmit={onSubmit}>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@maker.co"
          aria-label="Email address"
          required
        />
        <button type="submit">{buttonLabel}</button>
      </form>
      <p className="fine">{message}</p>
    </div>
  );
}
