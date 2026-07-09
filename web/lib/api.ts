import type { IssueData } from "./types";
import { getCurrentIssue } from "./db";

/**
 * Fetch the current published issue straight from Neon (no FastAPI hop).
 * Returns null when no issue is published yet or on any DB error so the page
 * can fall back to bundled sample data.
 */
export async function getIssue(): Promise<IssueData | null> {
  try {
    return await getCurrentIssue();
  } catch {
    return null;
  }
}
