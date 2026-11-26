import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
import instructor
from pydantic import BaseModel

load_dotenv()


class TestOutput(BaseModel):
    status: str


async def test():

    api_key = os.getenv("JUDGE_GROQ") or os.getenv("GROQ_API_KEY")

    print("API key found:", bool(api_key))

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    client = instructor.from_openai(
        client,
        mode=instructor.Mode.JSON,
    )

    result = await client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",
                "content": "Return the status as ok."
            }
        ],
        response_model=TestOutput,
        temperature=0,
    )

    print("STRUCTURED RESPONSE:")
    print(result)
    print("STATUS:", result.status)


if __name__ == "__main__":
    asyncio.run(test())