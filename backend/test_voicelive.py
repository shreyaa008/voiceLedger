import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.voicelive.aio import connect


# Load the exact .env file
env_file = Path(__file__).parent / "backend" / ".env"
load_dotenv(env_file)

endpoint = os.getenv("AZURE_VOICELIVE_ENDPOINT")
api_key = os.getenv("AZURE_VOICELIVE_API_KEY")
model = os.getenv("AZURE_VOICELIVE_MODEL")
api_version = os.getenv("AZURE_VOICELIVE_API_VERSION")

print("Endpoint:", endpoint)
print("Model:", model)
print("API version:", api_version)
print("API key loaded:", bool(api_key))
print("API key length:", len(api_key) if api_key else 0)


async def main():
    try:
        async with connect(
            credential=AzureKeyCredential(api_key),
            endpoint=endpoint,
            api_version=api_version,
            model=model,
        ) as connection:

            print("\n================================")
            print("SUCCESS: Connected to Azure Voice Live!")
            print("================================")

    except Exception as e:
        print("\n================================")
        print("CONNECTION FAILED")
        print("================================")
        print("Error type:", type(e).__name__)
        print("Error:", str(e))


asyncio.run(main())