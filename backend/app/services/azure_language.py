# TODO: Azure AI Language SDK setup (entity extraction)
import os
import re
from datetime import date

from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient

load_dotenv()


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

    # Determine transaction type from the text
    text_lower = text.lower()

    if language == "en":
        payment_words = [
            "paid",
            "payment",
            "pay",
            "gave",
            "returned",
            "settled"
        ]

        credit_words = [
            "bought",
            "purchase",
            "credit",
            "due",
            "owes",
            "borrowed"
        ]

    else:
        payment_words = [
            "दिया",
            "दिए",
            "दी",
            "भुगतान",
            "चुकाया",
            "चुकाए",
            "दे दिया",
            "दे दिए",
            "पैसे दिए",
            "रुपये दिए",
            "रुपए दिए"
        ]   

        credit_words = [
            "उधार",
            "बाकी",
            "लिए",
            "लिया",
            "खाते में"
        ]

    transaction_type = None

    if any(word in text_lower for word in payment_words):
        transaction_type = "payment"

    elif any(word in text_lower for word in credit_words):
        transaction_type = "credit"

    return {
        "customer": customer,
        "amount": amount,
        "type": transaction_type,
        "date": extracted_date.isoformat(),
        "language": language
    }