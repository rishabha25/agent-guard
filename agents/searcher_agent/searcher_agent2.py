import asyncio
import os
from typing import Any, Annotated
from dotenv import load_dotenv
from genai_session.session import GenAISession
import aiohttp
from geopy.distance import geodesic

load_dotenv()

GROQ_KEY = os.environ.get("GROQ_KEY")
client = Groq(api_key=GROQ_KEY)

session = GenAISession(jwt_token="")


async def fetch_trials(patient_hospital: str, session_http: aiohttp.ClientSession):
    headers = {
        "Authorization": f"Bearer {GRQCLOUD_API_KEY}",
        "Content-Type": "application/json"
    }
    params = {"hospital": patient_hospital}
    async with session_http.get(GRQCLOUD_ENDPOINT, headers=headers, params=params) as resp:
        return await resp.json()


@session.bind(
    name="search_and_rank_trials",
    description="Search and rank top 10 clinical trials by proximity and same hospital"
)
async def search_and_rank_trials(
    agent_context,
    medical_record: Annotated[str, "Patient's medical condition/record (not used for ranking)"],
    patient_hospital: Annotated[str, "Hospital where the patient is being treated"],
    patient_location: Annotated[str, "Patient's location in 'lat,lng' format"]
) -> dict[str, Any]:
    agent_context.logger.info("Fetching clinical trials...")

    async with aiohttp.ClientSession() as session_http:
        trials_data = await fetch_trials(patient_hospital, session_http)

    patient_coords = tuple(map(float, patient_location.split(",")))

    ranked_trials = []
    for trial in trials_data.get("trials", []):
        trial_coords_str = trial.get("location", "0,0")
        try:
            trial_coords = tuple(map(float, trial_coords_str.split(",")))
            proximity_km = geodesic(patient_coords, trial_coords).km
        except Exception:
            continue  # skip invalid locations

        ranked_trials.append({
            "trial_id": trial.get("id"),
            "title": trial.get("title"),
            "hospital": trial.get("hospital"),
            "distance_km": round(proximity_km, 2),
        })

    # Sort by distance ascending
    top_trials = sorted(ranked_trials, key=lambda x: x["distance_km"])[:10]
    return {"top_trials": top_trials}


async def main():
    await session.process_events()


if __name__ == "__main__":
    asyncio.run(main())
