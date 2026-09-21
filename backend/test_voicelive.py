import asyncio
import os

from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.voicelive.aio import connect

load_dotenv()


async def main():
    endpoint = os.getenv("AZURE_VOICELIVE_ENDPOINT")
    api_key = os.getenv("AZURE_VOICELIVE_API_KEY")
    model = os.getenv("AZURE_VOICELIVE_MODEL", "gpt-realtime")
    api_version = os.getenv(
        "AZURE_VOICELIVE_API_VERSION",
        "2026-04-10"
    )

    if not endpoint:
        raise RuntimeError("AZURE_VOICELIVE_ENDPOINT is missing")

    if not api_key:
        raise RuntimeError("AZURE_VOICELIVE_API_KEY is missing")

    print("Endpoint:", endpoint)
    print("Model:", model)
    print("API Version:", api_version)
    print("Region: Korea Central")
    print("Connecting to Voice Live...")

    async with connect(
        endpoint=endpoint,
        credential=AzureKeyCredential(api_key),
        model=model,
        api_version=api_version,
    ) as connection:

        print()
        print("======================================")
        print("VOICE LIVE CONNECTION SUCCESSFUL!")
        print("======================================")
        print("Model:", model)
        print("Region: Korea Central")
        print("API Version:", api_version)

    print("Connection closed.")


if __name__ == "__main__":
    asyncio.run(main())