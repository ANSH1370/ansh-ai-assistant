"""Tenants: one demo (or client) = one config + one Qdrant collection.

The portfolio assistant is the implicit default tenant ("ansh") and keeps the
original prompts and the `ansh_corpus` collection. Every other tenant lives in
`tenants/<slug>/tenant.json` with its corpus in `tenants/<slug>/corpus/*.md`
and its vectors in the collection `demo_<slug>` — fully isolated from the
portfolio assistant and from each other.
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.config import settings

ROOT = Path(__file__).resolve().parents[1]
TENANTS_DIR = ROOT / "tenants"
DEFAULT_SLUG = "ansh"


@dataclass(frozen=True)
class Tenant:
    slug: str
    name: str
    short_name: str
    site: str
    description: str
    industry: str = "business"
    languages: tuple[str, ...] = ("en",)
    accent: str = "#7c3aed"
    contact: str = ""
    starters: tuple[str, ...] = ()
    welcome: str = ""
    disclaimer: str = ""
    lead_email: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def is_default(self) -> bool:
        return self.slug == DEFAULT_SLUG

    @property
    def collection(self) -> str:
        return settings.collection if self.is_default else f"demo_{self.slug}"

    @property
    def corpus_dir(self) -> Path:
        return ROOT / "corpus" if self.is_default else TENANTS_DIR / self.slug / "corpus"

    @property
    def multilingual(self) -> bool:
        return any(lang != "en" for lang in self.languages)

    def public(self) -> dict:
        """What the demo page is allowed to know (no prompts, no emails)."""
        return {
            "slug": self.slug,
            "name": self.name,
            "short_name": self.short_name,
            "site": self.site,
            "description": self.description,
            "industry": self.industry,
            "languages": list(self.languages),
            "accent": self.accent,
            "starters": list(self.starters),
            "welcome": self.welcome,
            "disclaimer": self.disclaimer,
        }


DEFAULT_TENANT = Tenant(
    slug=DEFAULT_SLUG,
    name="Ansh Mangukiya",
    short_name="Ansh",
    site="https://anshmangukiya.vercel.app",
    description="AI engineer — production RAG, LLM and agent systems",
)


def _load(path: Path) -> Tenant:
    raw = json.loads(path.read_text(encoding="utf-8"))
    slug = raw.get("slug") or path.parent.name
    if slug != path.parent.name:
        raise ValueError(f"{path}: slug '{slug}' must match folder name '{path.parent.name}'")
    known = {f for f in Tenant.__dataclass_fields__ if f != "extra"}
    kwargs = {k: v for k, v in raw.items() if k in known}
    for key in ("languages", "starters"):
        if key in kwargs:
            kwargs[key] = tuple(kwargs[key])
    kwargs.setdefault("short_name", kwargs.get("name", slug))
    kwargs["slug"] = slug
    kwargs["extra"] = {k: v for k, v in raw.items() if k not in known}
    return Tenant(**kwargs)


@lru_cache(maxsize=1)
def all_tenants() -> dict[str, Tenant]:
    """Every tenant on disk (folders starting with '_' are templates and skipped)."""
    found: dict[str, Tenant] = {DEFAULT_SLUG: DEFAULT_TENANT}
    if TENANTS_DIR.exists():
        for cfg in sorted(TENANTS_DIR.glob("*/tenant.json")):
            if cfg.parent.name.startswith("_"):
                continue
            t = _load(cfg)
            found[t.slug] = t
    return found


def get_tenant(slug: str | None) -> Tenant | None:
    return all_tenants().get(slug or DEFAULT_SLUG)
