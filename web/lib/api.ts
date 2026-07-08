import type { IssueData } from "./types";

// Server-side fetch prefers API_URL, falling back to the public var, then localhost.
const API_URL =
  process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Fetch the current published issue. Returns null on 404 (no issue yet) or any
 * network/parse error so the page can fall back to bundled sample data.
 */
export async function getIssue(): Promise<IssueData | null> {
  try {
    const res = await fetch(`${API_URL}/api/v1/issue/current`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as IssueData;
  } catch {
    return null;
  }
}
