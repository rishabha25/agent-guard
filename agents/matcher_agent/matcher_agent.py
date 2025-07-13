import asyncio
import os
from typing import Any, Annotated

from dotenv import load_dotenv
from genai_session.session import GenAISession
from groq import Groq

load_dotenv()

GROQ_KEY = os.environ.get("GROQ_KEY")

client = Groq(api_key=GROQ_KEY)

session = GenAISession(
    jwt_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmZWZlMTQxOS1iZWUwLTQzNzQtODJmOC0wMWE3NzM4NTI0ZTMiLCJleHAiOjI1MzQwMjMwMDc5OSwidXNlcl9pZCI6IjhiMDFiM2M1LTJjNGItNDVjMC04OGRlLWQzMTQ1YTI2YWI4ZSJ9.qv4rDlbu1q-yUDjZEM8i8gQAuYy1AGIU309FoOqrXP8"
)

@session.bind(name="get_match_score_trial", description="Analyzes a patients medical record and history to provide a match score between 0-1 with a given clinical trial criteria after analyzing the inclusion and exclusion criterias")
async def get_match_score_trial(
        agent_context, patient_text: Annotated[str, "Patient medical record or history from text file"],
        trial_text: Annotated[str, "Details of clinical trial"]
) -> dict[str, Any]:
    agent_context.logger.info("Inside get_match_score_trial")
    prompt = f"""does this patient medical record {patient_text} \n\n match the clinical trial criateria {trial_text} \n\n 
    Provide score between 0-1 and explain which inclusion and exclusion criterias are fullfilled and which are not. 
    More inclusion criteria met should contribute to higher score. Highlight if any exclusion criteria is met that would disqualify the patient from the trial. If the score is 0, explain why the patient does not qualify for the trial. If any information is missing or not known do not treat it as disqualifying, highlight that in the response and adjust the score accordingly."""

    response = client.chat.completions.create(
    model="meta-llama/llama-4-scout-17b-16e-instruct",
    messages=[
      {
        "role": "user",
        "content": prompt
      }
    ],
    temperature=1,
    max_completion_tokens=1024,
    top_p=1,
    stream=False,
    stop=None,
)

    return {"score_explanation": response.choices[0].message.content.strip()}


async def main():
    await session.process_events()


if __name__ == "__main__":
    asyncio.run(main())
