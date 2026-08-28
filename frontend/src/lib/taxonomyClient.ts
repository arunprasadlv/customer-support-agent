import { apiFetch } from "./apiClient";
import type { TaxonomyEntry } from "../types/taxonomy";

/**
 * `GET /taxonomy` — domain categories + per-category suggested questions,
 * powering ChatWindow's quick-reply chips (frontend.md §12). Kept as its
 * own module rather than folded into `mockInquiryClient.ts`: this is a
 * distinct read-only resource, not part of the `InquiryFlow` request/
 * response contract that file documents and whose swap-boundary docstring
 * this avoids disturbing.
 *
 * No fallback/mock value on failure — a rejected promise here is handled
 * by the caller (ChatWindow) as "skip the chips silently, chat stays
 * usable via free text," never a fabricated taxonomy. That's the same
 * never-fabricate posture as `sendInquiry`'s `UNREACHABLE_REPLY`, just
 * surfaced as an absence of chips rather than a canned message, since
 * there's no guest-facing question being answered by this call.
 */
export function getTaxonomy(): Promise<TaxonomyEntry[]> {
  return apiFetch<TaxonomyEntry[]>("/taxonomy");
}
