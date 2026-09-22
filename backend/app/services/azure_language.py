# TODO: Azure AI Language SDK setup (entity extraction)
import os
import re
from datetime import date

from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient

load_dotenv()


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
    extracted_date = date.today()

    for entity in result.entities:

        # Customer
        if entity.category == "Person" and customer is None:
            customer = entity.text

        # Amount
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

        # Date
        elif entity.category == "DateTime":
            # Azure detects the date expression.
            # For "today", use today's date.
            if entity.subcategory == "Date":
                extracted_date = date.today()

    transaction_type = _classify_transaction_type(text)

    return {
        "customer": customer,
        "amount": amount,
        "type": transaction_type,
        "date": extracted_date.isoformat(),
        "language": language
    }