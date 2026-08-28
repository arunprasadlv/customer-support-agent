/**
 * Shared types for the `GET /taxonomy` quick-reply endpoint.
 *
 * @frontend.eng, *develop-fe (chat.md quick-reply chips, frontend.md §12).
 * Mirrors `CommonQuery`/`TaxonomyEntry` in `backend/src/app/main.py`
 * exactly (read directly, not guessed) — 4 domain categories, 3
 * `common_queries` each, used to build ChatWindow's two-step
 * category -> common-question quick-reply chips.
 */

export interface CommonQuery {
  kb_entry_id: string;
  query: string;
}

export interface TaxonomyEntry {
  intent: string;
  label: string;
  common_queries: CommonQuery[];
}
