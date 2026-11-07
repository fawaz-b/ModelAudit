"""Manual connectivity test for the configured Groq provider."""

import asyncio

from app.llm import generate_item_response


async def main():
    response = await generate_item_response(
        'Return this exact JSON: {"connection": "successful"}'
    )
    print("Groq response:")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
