import asyncio
import os
from typing import Any, Annotated, List
from dotenv import load_dotenv
from genai_session.session import GenAISession
from groq import Groq
import aiohttp
from geopy.distance import geodesic

load_dotenv()

GROQ_KEY = os.environ.get("GROQ_KEY")

client = Groq(api_key=GROQ_KEY)

GRQCLOUD_API_KEY = os.environ.get("GRQCLOUD_API_KEY")
GRQCLOUD_ENDPOINT = "https://api.grqcloud.com/clinical-trials/search"  # Placeholder

openai_client = OpenAI(api_key=OPENAPI_KEY)

session = GenAISession(jwt_token="")


async def get_embedding(text: str) -> List[float]:
    response = openai_client.embeddings.create(
        input=[text],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding


async def fetch_trials(patient_hospital: str, session_http: aiohttp.ClientSession):
    headers = {
        "Authorization": f"Bearer {GRQCLOUD_API_KEY}",
        "Content-Type": "application/json"
    }
    params = {"hospital": patient_hospital}
    async with session_http.get(GRQCLOUD_ENDPOINT, headers=headers, params=params) as resp:
        return await resp.json()


def calculate_similarity(embedding1, embedding2):
    from numpy import dot
    from numpy.linalg import norm
    return dot(embedding1, embedding2) / (norm(embedding1) * norm(embedding2))


@session.bind(name="search_and_rank_trials", description="Search and rank top 10 clinical trials based on medical input and proximity")
async def search_and_rank_trials(
    agent_context,
    medical_record: Annotated[str, "Patient's medical condition/record"],
    patient_hospital: Annotated[str, "Hospital where the patient is being treated"],
    patient_location: Annotated[str, "Patient's location (lat,lng)"]
) -> dict[str, Any]:
    agent_context.logger.info("Fetching trials and computing ranking...")

    async with aiohttp.ClientSession() as session_http:
        trials_data = await fetch_trials(patient_hospital, session_http)

    patient_embedding = await get_embedding(medical_record)
    patient_coords = tuple(map(float, patient_location.split(",")))

    ranked_trials = []
    for trial in trials_data.get("trials", []):
        trial_desc = trial.get("description", "")
        trial_coords = tuple(map(float, trial.get("location", "0,0").split(",")))

        similarity = calculate_similarity(patient_embedding, await get_embedding(trial_desc))
        proximity_km = geodesic(patient_coords, trial_coords).km

        # Score can be adjusted; here we blend similarity and proximity (closer = better)
        score = similarity - (proximity_km / 1000)  # Normalize impact of distance
        ranked_trials.append({
            "trial_id": trial["id"],
            "title": trial["title"],
            "hospital": trial["hospital"],
            "similarity_score": round(similarity, 4),
            "distance_km": round(proximity_km, 2),
            "score": score
        })

    top_trials = sorted(ranked_trials, key=lambda x: x["score"], reverse=True)[:10]
    return {"top_trials": top_trials}


async def main():
    await session.process_events()


if __name__ == "__main__":
    asyncio.run(main())
