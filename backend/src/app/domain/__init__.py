"""Domain-configuration layer (FR-012/FR-013). Loads and validates
backend/domain_config.json against backend/domain_config.schema.json, and
implements ADR-005's keyword/section-scored kb_search — no vector store,
no hardcoded hotel-specific strings/logic outside this file's JSON input
(AC-009)."""

from app.domain.loader import (
    DomainConfig,
    KBEntry,
    TaxonomyEntry,
    get_domain_config,
    kb_search,
    load_domain_config,
)

__all__ = [
    "DomainConfig",
    "KBEntry",
    "TaxonomyEntry",
    "get_domain_config",
    "kb_search",
    "load_domain_config",
]
