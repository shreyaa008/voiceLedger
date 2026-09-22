# TODO: Azure AI Language SDK setup (entity extraction)
import logging
import os
import re
from datetime import date

from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient

load_dotenv()

logger = logging.getLogger("voiceledger.extract")
if not logger.handlers:
    # Make sure these show up even if the app never calls logging.basicConfig()
    # elsewhere — debug visibility into the extraction pipeline shouldn't
    # depend on server-wide logging config.
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _classify_transaction_type(text: str) -> str | None:
    """Decide CREDIT vs PAYMENT from the sentence using phrase/semantic
    signals, checked in priority order — not isolated single-word matching.

    BUG THIS FIXES: the previous version matched bare "दिया"/"दिए"/"दी"
    ("gave"/"give") as a payment word. But "दिया" is *also* the verb used
    when giving credit ("उधार दिया" = "gave on credit"), and payment words
    were checked before credit words — so "Shreya ko udhaar diye" (a
    CREDIT) matched "दिए" and got silently reclassified as a PAYMENT.

    Fix: check strong, unambiguous phrase-level signals first (repayment
    words, then "उधार"/credit words), and only fall back to bare verbs
    when neither signal is present at all. Also written to recognize
    common Hinglish/romanized spellings ("udhaar", "wapas"), not just
    Devanagari — shopkeepers code-switch, and a mislabeled language tag
    from speech-to-text shouldn't make classification fail outright.
    """
    t = text.lower()

    # 1. Explicit repayment/settling signals — unambiguous even when
    #    "उधार/udhaar" also appears in the same sentence
    #    (e.g. "उधार चुका दिया" = settled the credit = a PAYMENT).
    payback_signals = [
        "वापस", "भुगतान", "चुका", "चुक",
        "wapas", "vapas", "bhugtan", "bhugtaan", "chuka", "chukaya", "chukaye",
        "paid back", "pay back", "settle",
    ]
    if any(sig in t for sig in payback_signals):
        return "payment"

    # 2. "उधार/udhaar" (credit, loan) is an unambiguous CREDIT signal in
    #    khata usage — checked before any bare give/take verb.
    credit_signals = [
        "उधार", "उधारी", "बाकी", "खाते में", "कर्ज़", "करज़",
        "udhar", "udhaar", "udhaari", "credit", "due", "borrowed", "owes",
    ]
    if any(sig in t for sig in credit_signals):
        return "credit"

    # 3. Plain English purchase/payment words.
    if any(w in t for w in ["bought", "purchase", "purchased"]):
        return "credit"
    if any(w in t for w in ["paid", "payment", "pay", "returned", "settled"]):
        return "payment"

    # 4. Last resort — bare give/take/receive verbs, only reached when no
    #    signal word above matched anywhere in the sentence. "लिया/liya"
    #    ("took") implies the customer took money/goods -> credit;
    #    "दिया/mila" ("gave"/"got") with no other signal -> payment.
    take_verbs = ["लिया", "लिए", "ली", "liya", "liye", "lee"]
    if any(w in t for w in take_verbs):
        return "credit"

    give_or_receive_verbs = [
        "दिया", "दिए", "दी", "मिला", "मिले", "मिली",
        "diya", "diye", "dee", "mila", "mile", "gave",
    ]
    if any(w in t for w in give_or_receive_verbs):
        return "payment"

    return None


# ---------------------------------------------------------------------------
# Fallback extraction (customer / amount)
#
# ROOT CAUSE: Azure's `recognize_entities` (general NER) only tags a number
# as a Quantity/"Currency" entity when the text also contains an explicit
# currency indicator — a symbol ("₹", "$") or a currency word ("rupees",
# "रुपये", "INR"). A shopkeeper's natural khata speech almost never includes
# that: "अजय को 2000 का उधार दिया" has no currency word at all, so Azure
# tags "2000" as Quantity/"Number" (or nothing), and the old code — which
# only accepted `subcategory == "Currency"` — silently dropped it, always
# leaving `amount` as None for exactly this (extremely common) phrasing.
#
# Person-entity recognition for common Hindi names is also not guaranteed
# for every name/sentence shape (case markers like "को"/"से" attached
# directly after the name in speech-recognized text can throw off the
# NER model). So both fields get a text-pattern fallback that only runs
# when Azure didn't already supply a value — it can only fill gaps, never
# override or downgrade a value Azure did find, so English parsing (which
# already works via Azure's Person + Currency entities) is untouched.
# ---------------------------------------------------------------------------

# Postpositions that mark the person in a khata sentence:
#   "X को ... दिया"  = "gave (to) X"        -> X is the customer
#   "X से ... लिया"  = "took (from) X"      -> X is the customer
#   "X ne ... diya/liya" (Hinglish "ने")    -> X is the customer
# Matches Devanagari or romanized (Hinglish) spellings, case-insensitively.
_CUSTOMER_MARKER_RE = re.compile(
    r"([A-Za-z\u0900-\u097F]+)\s*(?:को|से|ने|\bko\b|\bse\b|\bne\b)",
    re.IGNORECASE,
)

# A bare amount: digits, optionally grouped with commas, optional decimal.
# Deliberately currency-word-agnostic — this is exactly the case Azure's
# entity recognizer misses (see ROOT CAUSE above).
_AMOUNT_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _fallback_extract_customer(text: str) -> str | None:
    match = _CUSTOMER_MARKER_RE.search(text)
    if not match:
        return None
    candidate = match.group(1).strip()
    return candidate or None


def _fallback_extract_amount(text: str) -> float | None:
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    amount_text = match.group(0).replace(",", "")
    try:
        return float(amount_text)
    except ValueError:
        return None


def extract_transaction(text: str, language: str = "en") -> dict:
    endpoint = os.getenv("AZURE_LANGUAGE_ENDPOINT")
    key = os.getenv("AZURE_LANGUAGE_KEY")

    if not endpoint:
        raise RuntimeError("AZURE_LANGUAGE_ENDPOINT is missing from .env")

    if not key:
        raise RuntimeError("AZURE_LANGUAGE_KEY is missing from .env")

    client = TextAnalyticsClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key)
    )

    results = client.recognize_entities(
        documents=[text],
        language=language
    )

    result = results[0]

    if result.is_error:
        raise RuntimeError(f"Azure Language error: {result.error}")

    customer = None
    amount = None
    # Azure Quantity entity found with category "Number" but no explicit
    # currency indicator — kept as a lower-confidence candidate in case no
    # bare-digit regex match is found later either (belt and suspenders).
    amount_number_candidate = None
    extracted_date = date.today()

    for entity in result.entities:

        # Customer
        if entity.category == "Person" and customer is None:
            customer = entity.text

        # Amount — explicit currency entity ("₹2,000", "2000 rupees") is
        # the high-confidence case.
        elif (
            entity.category == "Quantity"
            and entity.subcategory == "Currency"
            and amount is None
        ):
            amount_text = entity.text

            # Remove currency symbols and commas
            amount_text = re.sub(r"[^\d.]", "", amount_text)

            if amount_text:
                amount = float(amount_text)

        # Amount — bare number with no currency word at all (e.g. "2000 का
        # उधार"). Azure tags this as Quantity/"Number", not "Currency". Keep
        # it as a candidate; only used if nothing better turns up below.
        elif (
            entity.category == "Quantity"
            and entity.subcategory in (None, "Number")
            and amount_number_candidate is None
        ):
            amount_text = re.sub(r"[^\d.]", "", entity.text)
            if amount_text:
                amount_number_candidate = float(amount_text)

        # Date
        elif entity.category == "DateTime":
            # Azure detects the date expression.
            # For "today", use today's date.
            if entity.subcategory == "Date":
                extracted_date = date.today()

    if amount is None:
        amount = amount_number_candidate

    # --- Fallbacks: only fill gaps Azure left, never override what it found ---
    if customer is None:
        customer = _fallback_extract_customer(text)

    if amount is None:
        amount = _fallback_extract_amount(text)

    transaction_type = _classify_transaction_type(text)

    logger.info("transcript=%r language=%r", text, language)

    transaction = {
        "customer": customer,
        "amount": amount,
        "type": transaction_type,
        "date": extracted_date.isoformat(),
        "language": language
    }

    logger.info("extracted transaction=%r", transaction)

    return transaction