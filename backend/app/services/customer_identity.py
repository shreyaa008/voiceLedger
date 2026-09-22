"""
Canonical customer identity.

Root cause of the duplicate-customer bug: customer lookups matched names
with an exact/case-sensitive string compare (`.eq("name", customer_name)`),
so "Shreya", "shreya", "SHREYA" and "श्रेया" (same person, four spellings)
each created a *different* customer row.

canonical_key() gives a single identity key for a name regardless of case,
whitespace, or script (Devanagari <-> Latin), so every write path can look
up "does this customer already exist?" the same way. It is a pure function
of the input string — nothing here is specific to any individual name.

How it works:
  1. Transliterate to Latin letters with `unidecode` (a generic script-to-
     ASCII transliterator — not a name list).
  2. Lowercase and strip everything but letters.
  3. Drop vowels, keeping only the consonant "skeleton".

Step 3 exists because Devanagari -> Latin transliteration of the same name
is not perfectly consistent about vowel length or schwa insertion, so
"श्रेया" romanizes to "shreyaa" while a shopkeeper typing the same name
types "shreya" (extra vowel), and "रमेश" romanizes to "rmesh" while the
typed form is "ramesh" (missing vowel). Consonants are what stays stable
across both spellings, so comparing consonant skeletons ("shry", "rmsh")
matches these correctly. This is a heuristic, not a linguistically perfect
transliteration — very short names, or two genuinely different names that
happen to share a consonant skeleton (e.g. "Manish"/"Manesh"), can in rare
cases collide. For a small shop's customer list this trade-off is worth it;
if it ever causes a real collision, merge_duplicate_customers.py's dry-run
report will show it before anything is merged.
"""
import re

try:
    from unidecode import unidecode
except ImportError:  # pragma: no cover
    # Falls back to "no transliteration" if the dependency isn't installed
    # yet — case-insensitive matching within one script still works.
    def unidecode(value: str) -> str:
        return value


_VOWELS_RE = re.compile(r"[aeiou]")
_NON_LETTERS_RE = re.compile(r"[^a-z]")


def canonical_key(name: str) -> str:
    """Script/case/whitespace-insensitive identity key for matching a
    customer name. 'Shreya', 'SHREYA', 'shreya ' and 'श्रेया' all return
    the same key."""
    if not name:
        return ""

    romanized = unidecode(name).lower()
    letters_only = _NON_LETTERS_RE.sub("", romanized)
    skeleton = _VOWELS_RE.sub("", letters_only)

    # Guard against reducing a very short/all-vowel name to "" (e.g. "Om").
    return skeleton or letters_only


def display_name(name: str) -> str:
    """Human-friendly stored form. Devanagari (or any non-Latin script) is
    kept exactly as spoken/typed; plain Latin names are trimmed and
    title-cased so 'shreya', 'SHREYA' and 'Shreya' all display the same
    way once they're the same customer row."""
    name = (name or "").strip()
    if re.fullmatch(r"[A-Za-z .'-]+", name):
        return name.title()
    return name