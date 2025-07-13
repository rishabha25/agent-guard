import asyncio
import os
from typing import Any, Annotated, List, Dict
from dotenv import load_dotenv
from genai_session.session import GenAISession
import aiohttp
from geopy.distance import geodesic
import requests
import json

load_dotenv()

session = GenAISession(jwt_token="")

CLINICAL_TRIALS_API = "https://clinicaltrials.gov/api/v2/studies"


async def fetch_trials_from_ctgov(session_http: aiohttp.ClientSession, condition: str):
    """
    Calls ClinicalTrials.gov v2 API to fetch trials related to a condition.
    """
    params = {
        "query": condition,
        "fields": "NCTId,BriefTitle,LocationFacility,LocationCity,LocationState,LocationCountry,BriefSummary",
        "limit": 100
    }
    async with session_http.get(CLINICAL_TRIALS_API, params=params) as response:
        data = await response.json()
        return data.get("studies", [])
    
def fetch_trials_from_ctgov_sy(session_http: aiohttp.ClientSession, condition: str):
    """
    Calls ClinicalTrials.gov v2 API to fetch trials related to a condition.
    """
    params = {
        "query": condition,
        "fields": "NCTId,BriefTitle,LocationFacility,LocationCity,LocationState,LocationCountry,BriefSummary",
        "limit": 100
    }
    with session_http.get(CLINICAL_TRIALS_API, params=params) as response:
        data = response.json()
        return data.get("studies", [])


@session.bind(
    name="search_and_rank_trials",
    description="Search and rank top 10 clinical trials by proximity and hospital name"
)
async def search_and_rank_trials(
    agent_context,
    medical_record: Annotated[str, "Patient's medical condition (e.g. 'lung cancer')"],
    patient_hospital: Annotated[str, "Hospital where the patient is being treated"],
    patient_location: Annotated[str, "Patient's location in 'lat,lng' format"]
) -> dict[str, Any]:
    agent_context.logger.info("Fetching trials from ClinicalTrials.gov...")

    async with aiohttp.ClientSession() as session_http:
        trials = await fetch_trials_from_ctgov(session_http, condition=medical_record)

    patient_coords = tuple(map(float, patient_location.split(",")))

    matching_trials = []
    for trial in trials:
        facility = trial.get("LocationFacility", "")
        if patient_hospital.lower() not in facility.lower():
            continue

        # For simplicity, fake geocoding using U.S. cities. Use real geocoding in production.
        location_str = f"{trial.get('LocationCity','')}, {trial.get('LocationState','')}, {trial.get('LocationCountry','')}"
        try:
            # In production, replace this with real lat/lng using geocoding API
            trial_coords = patient_coords  # Assume hospital is same location (mock)
            proximity_km = geodesic(patient_coords, trial_coords).km
        except:
            continue

        matching_trials.append({
            "nct_id": trial.get("NCTId"),
            "title": trial.get("BriefTitle"),
            "hospital": facility,
            "summary": trial.get("BriefSummary"),
            "distance_km": round(proximity_km, 2)
        })

    top_trials = sorted(matching_trials, key=lambda x: x["distance_km"])[:10]
    return {"top_trials": top_trials}


async def main():
    # await session.process_events()
    async with aiohttp.ClientSession() as session_http:
        trials = await fetch_trials_from_ctgov(session_http, condition="cancer")
        print(trials)  # Print first 5 trials for testing


def fetch_cancer_trials_by_location(condition: str = "cancer", location: str = "", max_distance: str = "50mi") -> List[Dict[str, Any]]:
    """
    Fetch cancer clinical trials from ClinicalTrials.gov API for a specific location.
    
    Args:
        condition: Medical condition to search for (default: "cancer")
        location: Location in format "latitude,longitude,distance" (e.g., "39.0035707,-77.1013313,50mi")
        max_distance: Maximum distance from location (default: "50mi")
    
    Returns:
        List of clinical trials matching the criteria
    """
    
    # Build parameters according to API documentation
    params = {
        "query.cond": condition,  # Use query.cond for condition search
        "format": "json",
        "pageSize": 100,  # Use pageSize instead of limit
        "fields": "NCTId,BriefTitle,BriefSummary,OverallStatus,LocationFacility,LocationCity,LocationState,LocationCountry,LocationGeoPoint,healthyVolunteers"
    }
    
    # Add location filter if provided
    if location:
        if not location.startswith("distance("):
            # If location is in "lat,lng,distance" format, convert to distance function
            parts = location.split(",")
            if len(parts) >= 3:
                lat, lng, dist = parts[0], parts[1], parts[2] if len(parts) > 2 else max_distance
                location = f"distance({lat},{lng},{dist})"
        params["filter.geo"] = location
    
    try:
        print(f"Querying ClinicalTrials.gov API for '{condition}' trials...")
        if location:
            print(f"Location filter: {location}")
        
        response = requests.get(CLINICAL_TRIALS_API, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        studies = data.get("studies", [])
        
        print(f"Found {len(studies)} trials")
        return studies
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching trials: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return []
    

def print_trial_summary(trials: List[Dict[str, Any]], max_trials: int = 10):
    """Print a summary of clinical trials."""
    
    if not trials:
        print("No trials found matching your criteria.")
        return
    
    print(f"\nFound {len(trials)} matching trials:")
    print("=" * 80)
    
    for i, trial in enumerate(trials[:max_trials], 1):
        print(f"Trial {trial}")
        print(f"\n{i}. {trial['title']}")
        print(f"   NCT ID: {trial['nct_id']}")
        print(f"   Status: {trial['status']}")
        
        # Handle facilities (could be string or list)
        facilities = trial['facilities']
        if isinstance(facilities, list) and facilities:
            print(f"   Facilities: {', '.join(facilities[:3])}")  # Show first 3
        elif isinstance(facilities, str):
            print(f"   Facility: {facilities}")
        
        # Handle cities
        cities = trial['cities']
        if isinstance(cities, list) and cities:
            print(f"   Cities: {', '.join(cities[:3])}")
        elif isinstance(cities, str):
            print(f"   City: {cities}")
        
        # Show brief summary (truncated)
        summary = trial['summary']
        if summary:
            summary_text = summary[:200] + "..." if len(summary) > 200 else summary
            print(f"   Summary: {summary_text}")
        
        print("-" * 80)






if __name__ == "__main__":
    # asyncio.run(main())
    """Example usage of the clinical trials API."""
    
    # Example 1: Search for cancer trials in Washington DC area
    print("Example 1: Cancer trials in Washington DC area")
    dc_location = "distance(38.9072,-77.0369,50mi)"  # Washington DC, 50 mile radius
    
    trials = fetch_cancer_trials_by_location(
        condition="cancer",
        location=dc_location
    )
    
    print_trial_summary(trials, max_trials=5)
    
