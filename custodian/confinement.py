"""The confinement rule: no agent prompt may contain a personal data value.

This is the architectural claim Custodian rests on, so it is implemented as a
mechanism rather than a convention. Agents receive *projections* of records —
field names, declared types, and opaque tokens — and reason over those. Raw
values live in a vault that agents have no tool binding to.

Tokens are deterministic within a run, which is what makes cross-store identity
resolution possible without exposure: the same normalized email in Cloud SQL and
in Firestore produces the same token, so an agent can join the two while never
learning the address. Across runs the salt changes, so tokens are not a stable
identifier for the subject.
"""

from __future__ import annotations

import hmac
import re
import secrets
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Iterable

# Values shorter than this are not scanned for leaks — a two-character value
# would match inside unrelated words and make the check useless.
MIN_SCANNABLE_LENGTH = 4


class ConfinementError(RuntimeError):
    """Raised when a raw personal data value is found somewhere it must not be."""


def normalize(value: str, kind: str) -> str:
    """Reduce a value to the form used for token derivation.

    Normalization is what lets the same person be recognized across stores that
    formatted the value differently. It deliberately does not attempt to link
    genuinely different identifiers — an alias address is a reasoning problem
    for the classifier, not a normalization one.

    Args:
        value: The raw value.
        kind: Declared type, such as "email", "phone" or "name".

    Returns:
        The normalized string used as token input.
    """
    v = value.strip()
    if kind == "email":
        return v.lower()
    if kind == "phone":
        digits = re.sub(r"\D", "", v)
        # Compare on the national significant number so +234 801… and 0801…
        # resolve alike.
        return digits[-10:] if len(digits) >= 10 else digits
    if kind in {"name", "address"}:
        return re.sub(r"\s+", " ", v).lower()
    return v


@dataclass
class TokenVault:
    """Holds raw values and issues opaque, run-scoped tokens for them.

    Only the executor resolves tokens. Discovery, classification and assessment
    agents hold the vault's *tokens*, never the vault.
    """

    run_id: str
    _salt: bytes = field(default_factory=lambda: secrets.token_bytes(32), repr=False)
    _by_token: dict[str, str] = field(default_factory=dict, repr=False)
    _kinds: dict[str, str] = field(default_factory=dict, repr=False)
    _seeded: list[tuple[str, str]] = field(default_factory=list, repr=False)

    def seed_values(self, pairs: Iterable[tuple[str, str]]) -> None:
        """Register the requesting subject's known identifiers and their variants.

        The erasure request tells us who we are looking for, so these values are
        known up front and can be redacted out of prose no regex would catch — a
        name or a street address written mid-sentence.

        Variants matter and must be supplied: an address written in full in one
        store often appears truncated in another, and exact matching will miss
        the short form. Hand-listing them is right for a fixed demo dataset;
        against real production prose this pass belongs to an entity extractor
        such as Cloud Sensitive Data Protection.

        Args:
            pairs: (raw value, kind) tuples.
        """
        for value, kind in pairs:
            if not value:
                continue
            self._seeded.append((str(value), kind))
            self.token_for(str(value), kind)

    def seeded_values(self) -> tuple[tuple[str, str], ...]:
        """The subject identifiers registered by seed_subject."""
        return tuple(self._seeded)

    def token_for(self, value: str, kind: str) -> str:
        """Return the token standing in for a value, minting it if new."""
        digest = hmac.new(
            self._salt,
            f"{self.run_id}|{kind}|{normalize(value, kind)}".encode(),
            sha256,
        ).hexdigest()[:12]
        token = f"tok_{kind}_{digest}"
        self._by_token[token] = value
        self._kinds[token] = kind
        return token

    def resolve(self, token: str) -> str:
        """Return the raw value behind a token. Executor-side only."""
        try:
            return self._by_token[token]
        except KeyError:
            raise ConfinementError(f"unknown token: {token}") from None

    def raw_values(self) -> tuple[str, ...]:
        """Every raw value the vault has seen, for leak scanning."""
        return tuple(self._by_token.values())

    def kind_of_value(self, value: str) -> str | None:
        """The declared kind for a raw value the vault already holds."""
        for token, held in self._by_token.items():
            if held == value:
                return self._kinds.get(token)
        return None

    def assert_no_raw_values(self, text: str, *, where: str = "prompt") -> None:
        """Fail loudly if any known raw value appears in text.

        Args:
            text: Outbound content — a prompt, a log line, a tool argument.
            where: Label used in the error, to locate the leak.

        Raises:
            ConfinementError: If a raw value is present.
        """
        haystack = text.lower()
        for value in self._by_token.values():
            if len(value) < MIN_SCANNABLE_LENGTH:
                continue
            if value.lower() in haystack:
                raise ConfinementError(
                    f"raw personal data value leaked into {where}: "
                    f"{value[:2]}…{value[-2:]} ({len(value)} chars)"
                )


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Nigerian formats in the fixture, international and national, plus separators.
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?0?\d{3}[\s-]?\d{3}[\s-]?\d{4}")

# Marks a field as human-written prose. Tokenizing the whole blob would leave an
# agent nothing to reason about, so these are redacted span by span instead.
FREETEXT = "freetext"


def redact_text(text: str, vault: "TokenVault") -> str:
    """Replace personal spans inside prose, leaving the rest readable.

    Two passes. First, values the vault already knows — the subject's own
    identifiers, seeded from the erasure request — because those are exactly
    what discovery is looking for and they appear in prose the regexes cannot
    catch, such as a name inside a sentence. Second, generic email and phone
    patterns, which catch identifiers belonging to anyone.

    Args:
        text: Free-text content read from a datastore.
        vault: Vault that mints tokens and holds the seeded subject values.

    Returns:
        The same prose with personal spans replaced by tokens.
    """
    out = text

    # Everything the vault knows: the seeded subject identifiers plus any value
    # already tokenized while reading structured stores. The second group is
    # what keeps a third party's name out of a prompt when it appears in prose.
    #
    # Longest first, so "14 Bourdillon Road, Ikoyi, Lagos" is replaced before a
    # shorter overlapping value can fragment it.
    known = list(vault.seeded_values()) + [
        (v, vault.kind_of_value(v)) for v in vault.raw_values()
    ]
    for value, kind in sorted(known, key=lambda p: len(p[0]), reverse=True):
        if not kind or len(value) < MIN_SCANNABLE_LENGTH:
            continue
        out = re.sub(
            re.escape(value), vault.token_for(value, kind), out, flags=re.IGNORECASE
        )

    out = EMAIL_RE.sub(lambda m: vault.token_for(m.group(0), "email"), out)
    out = PHONE_RE.sub(lambda m: vault.token_for(m.group(0), "phone"), out)
    return out


@dataclass(frozen=True)
class FieldSpec:
    """Declares whether a field carries personal data, and of what kind.

    `kind=None` passes through in the clear; `kind=FREETEXT` is redacted span by
    span; anything else tokenizes the whole value.
    """

    name: str
    kind: str | None


def project(
    record: dict, spec: tuple[FieldSpec, ...], vault: TokenVault
) -> dict:
    """Build the agent-safe view of a record.

    Personal fields become tokens; everything else passes through, because an
    agent still needs order totals and timestamps to reason about retention.

    Args:
        record: The raw record as read from a datastore.
        spec: Field declarations for that store.
        vault: Vault that mints the tokens.

    Returns:
        A dict safe to place in a prompt.
    """
    out: dict = {}
    for f in spec:
        if f.name not in record:
            continue
        value = record[f.name]
        if f.kind is None or value is None:
            out[f.name] = value
        elif f.kind == FREETEXT:
            out[f.name] = redact_text(str(value), vault)
        else:
            out[f.name] = vault.token_for(str(value), f.kind)
    return out
