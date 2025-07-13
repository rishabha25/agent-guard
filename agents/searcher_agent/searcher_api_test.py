import requests
from typing import List, Dict, Any
from geopy.distance import geodesic
import json

CLINICAL_TRIALS_API = "https://clinicaltrials.gov/api/v2/studies"

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

def search_trials_by_hospital_and_location(
    condition: str = "cancer",
    hospital_name: str = "",
    location: str = "",
    max_distance: str = "50mi"
) -> List[Dict[str, Any]]:
    """
    Search for clinical trials by condition, hospital name, and location.
    
    Args:
        condition: Medical condition (e.g., "lung cancer", "breast cancer")
        hospital_name: Name of hospital to filter by
        location: Location in "lat,lng,distance" format
        max_distance: Maximum distance from location
    
    Returns:
        List of matching trials with additional proximity information
    """
    
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
    print(f"Found {len(matching_trials)} matching trials")
    
    return matching_trials


    
    """Print a summary of clinical trials."""
    
    if not trials:
        print("No trials found matching your criteria.")
        return
    
    print(f"\nFound {len(trials)} matching trials:")
    print("=" * 80)
    
    for i, trial in enumerate(trials[:max_trials], 1):
        # Safe access to avoid KeyError
        title = trial.get('title', 'No title available')
        nct_id = trial.get('nct_id', 'No NCT ID')
        status = trial.get('status', 'Unknown status')
        
        print(f"\n{i}. {title}")
        print(f"   NCT ID: {nct_id}")
        print(f"   Status: {status}")
        
        # Handle locations
        locations = trial.get('locations', [])
        if locations:
            print(f"   Locations:")
            for j, location in enumerate(locations[:3], 1):
                facility = location.get('facility', 'Unknown facility')
                city = location.get('city', 'Unknown city')
                state = location.get('state', 'Unknown state')
                print(f"     {j}. {facility} - {city}, {state}")
            
            if len(locations) > 3:
                print(f"     ... and {len(locations) - 3} more locations")
        
        # Show eligibility information
        eligibility = trial.get('eligibility', {})
        if eligibility:
            print(f"   Eligibility:")
            if eligibility.get('sex'):
                print(f"     Sex: {eligibility['sex']}")
            if eligibility.get('minimum_age'):
                print(f"     Min Age: {eligibility['minimum_age']}")
            if eligibility.get('maximum_age'):
                print(f"     Max Age: {eligibility['maximum_age']}")
            if eligibility.get('healthy_volunteers'):
                print(f"     Healthy Volunteers: {eligibility['healthy_volunteers']}")
            
            # Show truncated criteria
            criteria = eligibility.get('criteria', '')
            if criteria:
                criteria_text = criteria[:300] + "..." if len(criteria) > 300 else criteria
                print(f"     Criteria: {criteria_text}")
        
        # Show brief summary (truncated)
        summary = trial.get('summary', '')
        if summary:
            summary_text = summary[:200] + "..." if len(summary) > 200 else summary
            print(f"   Summary: {summary_text}")
        
        print("-" * 80)


def get_trial_details(trials: List[Dict[str, Any]], max_trials: int = 5) -> List[str]:
    """Return a list of clinical trial details as formatted strings."""
    
    if not trials:
        return []
    
    trial_details = []
    
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
        
        trial_details.append(trial_string)
    
    return trial_details

# Example usage functions
def main():
    """Example usage of the clinical trials API."""
    dc_location = "distance(38.9072,-77.0369,50mi)"  # Washington DC, 50 mile radius
    
    # Example 2: Search for lung cancer trials at specific hospital
    print("\n" + "="*80)
    print("Example 2: Search trials by condition hospital and location")
    
    # johns_hopkins_trials = search_trials_by_hospital_and_location(
    #     condition="Abdominal aortic aneurysm",
    #     hospital_name="Johns Hopkins",
    #     location="38.9072,-77.0369,50mi"
    # )

    md_anderson_trials = search_trials_by_hospital_and_location(
        condition="cancer",
        hospital_name="M D Anderson",
        location="29.7070,-95.3971,50mi"
    )
    
    get_trial_details(md_anderson_trials, max_trials=3)

if __name__ == "__main__":
    main()