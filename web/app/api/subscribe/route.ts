// POST /api/subscribe — Vercel-side port of backend routes/subscribe.py:
// 201 on a new subscriber, 200 when the email already existed, 422 on an
// invalid email (FastAPI's EmailStr behaviour), 500 on DB failure.

import { NextResponse } from "next/server";
import { subscribeEmail } from "@/lib/db";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(request: Request) {
  let email: unknown;
  try {
    ({ email } = await request.json());
  } catch {
    return NextResponse.json({ detail: "invalid body" }, { status: 422 });
  }
  if (typeof email !== "string" || !EMAIL_RE.test(email.trim())) {
    return NextResponse.json({ detail: "invalid email" }, { status: 422 });
  }
  try {
    const { created } = await subscribeEmail(email.trim());
    if (created) return NextResponse.json({ ok: true }, { status: 201 });
    return NextResponse.json({ ok: true, already: true }, { status: 200 });
  } catch {
    return NextResponse.json({ detail: "subscribe failed" }, { status: 500 });
  }
}
