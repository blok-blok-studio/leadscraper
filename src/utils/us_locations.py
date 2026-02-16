"""US location utilities for targeting."""

from __future__ import annotations

# Major US cities by state for broad scraping
US_MAJOR_CITIES = {
    "AL": ["Birmingham", "Montgomery", "Huntsville", "Mobile"],
    "AK": ["Anchorage", "Fairbanks", "Juneau"],
    "AZ": ["Phoenix", "Tucson", "Mesa", "Scottsdale"],
    "AR": ["Little Rock", "Fort Smith", "Fayetteville"],
    "CA": ["Los Angeles", "San Francisco", "San Diego", "San Jose", "Sacramento", "Oakland", "Fresno"],
    "CO": ["Denver", "Colorado Springs", "Aurora", "Fort Collins"],
    "CT": ["Hartford", "New Haven", "Stamford", "Bridgeport"],
    "DE": ["Wilmington", "Dover", "Newark"],
    "FL": ["Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale", "St Petersburg"],
    "GA": ["Atlanta", "Savannah", "Augusta", "Columbus"],
    "HI": ["Honolulu", "Hilo", "Kailua"],
    "ID": ["Boise", "Idaho Falls", "Meridian"],
    "IL": ["Chicago", "Springfield", "Naperville", "Rockford"],
    "IN": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend"],
    "IA": ["Des Moines", "Cedar Rapids", "Iowa City"],
    "KS": ["Wichita", "Kansas City", "Topeka", "Overland Park"],
    "KY": ["Louisville", "Lexington", "Bowling Green"],
    "LA": ["New Orleans", "Baton Rouge", "Shreveport"],
    "ME": ["Portland", "Bangor", "Lewiston"],
    "MD": ["Baltimore", "Annapolis", "Rockville", "Frederick"],
    "MA": ["Boston", "Worcester", "Springfield", "Cambridge"],
    "MI": ["Detroit", "Grand Rapids", "Ann Arbor", "Lansing"],
    "MN": ["Minneapolis", "St Paul", "Rochester", "Duluth"],
    "MS": ["Jackson", "Gulfport", "Hattiesburg"],
    "MO": ["Kansas City", "St Louis", "Springfield", "Columbia"],
    "MT": ["Billings", "Missoula", "Great Falls"],
    "NE": ["Omaha", "Lincoln", "Bellevue"],
    "NV": ["Las Vegas", "Reno", "Henderson"],
    "NH": ["Manchester", "Nashua", "Concord"],
    "NJ": ["Newark", "Jersey City", "Trenton", "Princeton"],
    "NM": ["Albuquerque", "Santa Fe", "Las Cruces"],
    "NY": ["New York", "Buffalo", "Rochester", "Albany", "Syracuse"],
    "NC": ["Charlotte", "Raleigh", "Durham", "Greensboro", "Wilmington"],
    "ND": ["Fargo", "Bismarck", "Grand Forks"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron"],
    "OK": ["Oklahoma City", "Tulsa", "Norman"],
    "OR": ["Portland", "Salem", "Eugene", "Bend"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Harrisburg"],
    "RI": ["Providence", "Warwick", "Cranston"],
    "SC": ["Charleston", "Columbia", "Greenville", "Myrtle Beach"],
    "SD": ["Sioux Falls", "Rapid City", "Aberdeen"],
    "TN": ["Nashville", "Memphis", "Knoxville", "Chattanooga"],
    "TX": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "El Paso"],
    "UT": ["Salt Lake City", "Provo", "Ogden", "St George"],
    "VT": ["Burlington", "Montpelier", "Rutland"],
    "VA": ["Richmond", "Virginia Beach", "Arlington", "Norfolk", "Alexandria"],
    "WA": ["Seattle", "Tacoma", "Spokane", "Bellevue"],
    "WV": ["Charleston", "Huntington", "Morgantown"],
    "WI": ["Milwaukee", "Madison", "Green Bay"],
    "WY": ["Cheyenne", "Casper", "Laramie"],
    "DC": ["Washington"],
}


def get_locations(states: list[str] = None, cities: list[str] = None) -> list[str]:
    """
    Build a list of location strings for scraping.

    Args:
        states: List of state abbreviations to target. Empty = all states.
        cities: List of specific cities. If provided, overrides state lookup.

    Returns:
        List of "City, ST" formatted strings.
    """
    if cities:
        return cities

    target_states = [s.upper() for s in states] if states else list(US_MAJOR_CITIES.keys())

    locations = []
    for state in target_states:
        state_cities = US_MAJOR_CITIES.get(state, [])
        for city in state_cities:
            locations.append(f"{city}, {state}")

    return locations
