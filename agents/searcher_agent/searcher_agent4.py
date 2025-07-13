import asyncio
import os
import requests
import json
from typing import List, Dict, Any, Annotated
from dotenv import load_dotenv
from genai_session.session import GenAISession
from groq import Groq

load_dotenv()

# GROQ_KEY = os.environ.get("GROQ_KEY")
CLINICAL_TRIALS_API = "https://clinicaltrials.gov/api/v2/studies"

# client = Groq(api_key=GROQ_KEY)

session = GenAISession(
    jwt_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJiMjM2ZDdhZC04OGZkLTQ4ODAtYjQxYi02OTU5ZTQxMDhjODQiLCJleHAiOjI1MzQwMjMwMDc5OSwidXNlcl9pZCI6IjhiMDFiM2M1LTJjNGItNDVjMC04OGRlLWQzMTQ1YTI2YWI4ZSJ9.AfDA9ckiedF1GL-2p3PfEO-2qMqfjPiPYdGZashOmcw"
)

def extract_eligibility_info(eligibility_module: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and format eligibility information from EligibilityModule.
    
    Args:
        eligibility_module: The EligibilityModule dict from the API response
        
    Returns:
        Formatted eligibility information
    """
    if not eligibility_module:
        return {}
    
    return {
        "criteria": eligibility_module.get("eligibilityCriteria", ""),
        "healthy_volunteers": eligibility_module.get("healthyVolunteers", False),
        "sex": eligibility_module.get("sex", ""),
        "minimum_age": eligibility_module.get("minimumAge", ""),
        "maximum_age": eligibility_module.get("maximumAge", "")
    }

def extract_locations_info(contacts_locations_module: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract and format location information from ContactsLocationsModule.
    
    Args:
        contacts_locations_module: The ContactsLocationsModule dict from the API response
        
    Returns:
        List of formatted location information
    """
    if not contacts_locations_module:
        return []
    
    locations = contacts_locations_module.get("locations", [])
    formatted_locations = []
    
    for location in locations:
        if isinstance(location, dict):
            formatted_location = {
                "facility": location.get("facility", ""),
                "city": location.get("city", ""),
                "state": location.get("state", ""),
                "country": location.get("country", ""),
                "geo_point": location.get("geoPoint", {})
            }
            formatted_locations.append(formatted_location)
    
    return formatted_locations

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
        "fields": "NCTId,BriefTitle,BriefSummary,OverallStatus,LocationFacility,LocationCity,LocationState,LocationCountry,LocationGeoPoint,EligibilityModule"
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

@session.bind(
    name="search_trials_by_hospital_and_location",
    description="Search for clinical trials by medical condition, hospital name, and geographic location. Returns matching trials with detailed information including eligibility criteria and locations."
)
async def search_trials_by_hospital_and_location(
    agent_context,
    condition: Annotated[str, "Medical condition of current patient to search for (e.g., 'lung cancer', 'breast cancer', 'diabetes')"] = "cancer",
    hospital_name: Annotated[str, "Name of hospital or medical facility to filter by (e.g., 'Johns Hopkins', 'Mayo Clinic')"] = "",
    location: Annotated[str, "Location in 'lat,lng,distance' format (e.g., '38.9072,-77.0369,50mi') or as distance function"] = "",
    max_distance: Annotated[str, "Maximum distance from location (e.g., '50mi', '100km')"] = "50mi"
) -> Dict[str, Any]:
    """
    Search for clinical trials by condition, hospital name, and location.
    
    Args:
        agent_context: The agent context from genai_session
        condition: Medical condition (e.g., "lung cancer", "breast cancer")
        hospital_name: Name of hospital to filter by
        location: Location in "lat,lng,distance" format
        max_distance: Maximum distance from location
    
    Returns:
        Dictionary containing matching trials and metadata
    """
    
    agent_context.logger.info(f"Searching for trials: condition='{condition}', hospital='{hospital_name}', location='{location}'")
    
    try:
        # Fetch all trials for the condition and location
        trials = fetch_cancer_trials_by_location(condition, location, max_distance)
        
        matching_trials = []
        
        for trial in trials:
            # Extract trial information from the nested structure
            protocol_section = trial.get("protocolSection", {})
            identification_module = protocol_section.get("identificationModule", {})
            description_module = protocol_section.get("descriptionModule", {})
            status_module = protocol_section.get("statusModule", {})
            contacts_locations_module = protocol_section.get("contactsLocationsModule", {})
            eligibility_module = protocol_section.get("eligibilityModule", {})
            
            # Extract locations for hospital filtering
            locations = extract_locations_info(contacts_locations_module)
            
            # Filter by hospital name if specified
            if hospital_name:
                hospital_match = False
                for location_info in locations:
                    facility = location_info.get("facility", "")
                    if hospital_name.lower() in facility.lower():
                        hospital_match = True
                
                if not hospital_match:
                    continue
            
            trial_info = {
                "nct_id": identification_module.get("nctId", ""),
                "title": identification_module.get("briefTitle", ""),
                "summary": description_module.get("briefSummary", ""),
                "status": status_module.get("overallStatus", ""),
                "locations": locations,
                "eligibility": extract_eligibility_info(eligibility_module)
            }
            
            matching_trials.append(trial_info)
        
        result = {
            "success": True,
            "total_trials_found": len(matching_trials),
            "search_parameters": {
                "condition": condition,
                "hospital_name": hospital_name,
                "location": location,
                "max_distance": max_distance
            },
            "trials": matching_trials
        }
        
        print(f"Found {len(matching_trials)} matching trials")
        agent_context.logger.info(f"Found {len(matching_trials)} matching trials")
        return get_trial_details_formatted(result, max_trials=5)
        
    except Exception as e:
        agent_context.logger.error(f"Error searching trials: {str(e)}")
        result = {
            "success": False,
            "error": str(e),
            "total_trials_found": 0,
            "search_parameters": {
                "condition": condition,
                "hospital_name": hospital_name,
                "location": location,
                "max_distance": max_distance
            },
            "trials": []
        }
        
        return get_trial_details_formatted(result, max_trials=5)
        


def get_trial_details_formatted(
    trials_data: Annotated[Dict[str, Any], "Dictionary containing trials data from search_trials_by_hospital_and_location"],
    max_trials: Annotated[int, "Maximum number of trials to format (default: 5)"] = 5
) -> Dict[str, Any]:
    """
    Format trial details into readable strings.
    
    Args:
        agent_context: The agent context from genai_session
        trials_data: Dictionary containing trials data
        max_trials: Maximum number of trials to format
    
    Returns:
        Dictionary with formatted trial details
    """
    
    try:
        if not trials_data.get("success", False):
            return {
                "success": False,
                "error": "Input trials data indicates failed search",
                "formatted_trials": []
            }
        
        trials = trials_data.get("trials", [])
        
        if not trials:
            return {
                "success": True,
                "formatted_trials": [],
                "error": "No trials found matching the criteria"
            }
        
        formatted_trials = []
        
        for trial in trials[:max_trials]:
            # Safe access to avoid KeyError
            title = trial.get('title', 'No title available')
            summary = trial.get('summary', 'No summary available')
            
            # Handle eligibility information
            eligibility = trial.get('eligibility', {})
            sex = eligibility.get('sex', 'Not specified')
            max_age = eligibility.get('maximum_age', 'Not specified')
            min_age = eligibility.get('minimum_age', 'Not specified')
            healthy_volunteers = eligibility.get('healthy_volunteers', 'Not specified')
            full_criteria = eligibility.get('criteria', 'No criteria available')
            
            # Format the trial details string
            trial_string = f"Title: {title}, Summary: {summary}, Eligibility - Sex: {sex}, Max Age: {max_age}, Minimum Age: {min_age}, Healthy Volunteer Required: {healthy_volunteers}, Full Eligibility Criteria: {full_criteria}"
            
            formatted_trials.append({
                "nct_id": trial.get('nct_id', ''),
                "formatted_text": trial_string,
                "raw_data": trial
            })
        
        return {
            "success": True,
            "formatted_trials": formatted_trials,
            "total_formatted": len(formatted_trials),
            "total_available": len(trials)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "formatted_trials": []
        }

async def main():
    await session.process_events()

if __name__ == "__main__":
    asyncio.run(main())