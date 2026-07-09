"use client";

import { useState } from "react";
import { Button } from "@astryxdesign/core/Button";
import { Card } from "@astryxdesign/core/Card";
import { TextInput } from "@astryxdesign/core/TextInput";

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
    <Card className="cta rv in s4">
      <div className="k">The Tuesday Signal</div>
      <h4>Get the Reddit signal, read for you.</h4>
      <p>
        One email, every Tuesday. The week&rsquo;s rising pains, sentiment flips,
        and emerging bets — synthesized, not scraped.
      </p>
      <form className="form" onSubmit={onSubmit}>
        <TextInput
          type="email"
          label="Email address"
          isLabelHidden
          value={email}
          onChange={(value) => setEmail(value)}
          placeholder="you@maker.co"
          htmlName="email"
        />
        <Button type="submit" variant="primary" label={buttonLabel} />
      </form>
      <p className="fine">{message}</p>
    </Card>
  );
}
