from __future__ import annotations

from typing import Literal

SupportedCountryCode = Literal["US", "CA", "IN", "ANY"]
ResolvedCountryCode = Literal["US", "CA", "IN", "OTHER"]
RecommendationTone = Literal["apply", "review", "skip"]
FreshnessTone = Literal["fresh", "aging", "stale"]

_COUNTRY_FLAGS: dict[str, str] = {
    "US": "🇺🇸",
    "CA": "🇨🇦",
    "IN": "🇮🇳",
    "ANY": "🌍",
    "OTHER": "🌍",
}

_COUNTRY_LABELS: dict[str, str] = {
    "US": "United States",
    "CA": "Canada",
    "IN": "India",
    "ANY": "Any",
    "OTHER": "Other",
}

_US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
    "district of columbia", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee", "texas", "utah",
    "vermont", "virginia", "washington", "west virginia", "wisconsin", "wyoming",
}

_US_STATE_CODES = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "dc", "fl", "ga", "hi", "id", "il", "in", "ia",
    "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj", "nm",
    "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa",
    "wv", "wi", "wy",
}

_CANADA_HINTS = {
    "canada", "toronto", "vancouver", "montreal", "ottawa", "calgary", "edmonton", "waterloo", "victoria",
    "ontario", "british columbia", "quebec", "alberta", "manitoba", "saskatchewan", "nova scotia",
    "new brunswick", "newfoundland and labrador", "prince edward island", "ont", "bc", "qc", "ab", "mb",
    "sk", "ns", "nb", "nl", "pei",
}

_INDIA_HINTS = {
    "india", "bangalore", "bengaluru", "hyderabad", "mumbai", "pune", "gurgaon", "gurugram", "noida",
    "delhi", "new delhi", "chennai", "kolkata", "ahmedabad", "remote - india",
}

_OTHER_COUNTRY_HINTS = {
    "japan", "united kingdom", "uk", "england", "ireland", "germany", "france", "spain", "italy",
    "netherlands", "poland", "sweden", "norway", "denmark", "finland", "switzerland", "austria",
    "portugal", "singapore", "australia", "new zealand", "mexico", "brazil", "argentina", "uae",
    "united arab emirates", "saudi arabia", "israel", "south korea", "korea", "taiwan", "hong kong",
}


def normalize_supported_country(value: str | None) -> SupportedCountryCode:
    normalized = (value or "US").strip().casefold()
    mapping = {
        "us": "US",
        "usa": "US",
        "united states": "US",
        "united_states": "US",
        "ca": "CA",
        "canada": "CA",
        "in": "IN",
        "india": "IN",
        "any": "ANY",
        "global": "ANY",
        "world": "ANY",
    }
    return mapping.get(normalized, "US")  # type: ignore[return-value]


def country_flag(country_code: str | None) -> str:
    return _COUNTRY_FLAGS.get(country_code or "ANY", "🌍")


def country_label(country_code: str | None) -> str:
    return _COUNTRY_LABELS.get(country_code or "ANY", "Any")


def country_display(country_code: str | None) -> str:
    return f"{country_flag(country_code)} {country_label(country_code)}"


def infer_country_code(location: str, description_text: str = "") -> ResolvedCountryCode | None:
    location_text = location.strip()
    if not location_text:
        haystack = description_text.casefold()
        if any(token in haystack for token in ("united states", "remote us", "remote - us", "remote, us", "usa")):
            return "US"
        if any(token in haystack for token in _CANADA_HINTS):
            return "CA"
        if any(token in haystack for token in _INDIA_HINTS):
            return "IN"
        if any(token in haystack for token in _OTHER_COUNTRY_HINTS):
            return "OTHER"
        return None

    haystack = location_text.casefold()
    trailing = location_text.casefold().split(",")[-1].strip()

    if any(token in haystack for token in ("united states", "remote us", "remote - us", "remote, us", "usa")):
        return "US"
    if trailing in _US_STATE_NAMES or trailing in _US_STATE_CODES:
        return "US"
    segments = [segment.strip() for segment in haystack.split(",") if segment.strip()]
    if any(segment in {"us", "usa", "united states"} for segment in segments):
        return "US"
    if any(segment in {"in", "india"} for segment in segments):
        return "IN"

    if any(token in haystack for token in _CANADA_HINTS):
        return "CA"

    if any(token in haystack for token in _INDIA_HINTS):
        return "IN"

    if any(token in haystack for token in _OTHER_COUNTRY_HINTS):
        return "OTHER"

    # If the last comma-delimited segment is an explicit non-empty geography token and not a role marker,
    # treat it as a clearly non-target country when it is not one of the supported regions above.
    if "," in location_text and trailing not in {"remote", "hybrid", "onsite"} and len(trailing) > 2:
        return "OTHER"

    return None


def matches_country_preference(country_code: str | None, selected_country: SupportedCountryCode) -> bool:
    if selected_country == "ANY":
        return True
    if country_code is None:
        return True
    return country_code == selected_country


def freshness_tone_from_minutes(minutes: int, *, alert_freshness_hours: int, dashboard_freshness_hours: int) -> FreshnessTone:
    if minutes <= alert_freshness_hours * 60:
        return "fresh"
    if minutes <= dashboard_freshness_hours * 60:
        return "aging"
    return "stale"


def _compact_age(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remainder = minutes % 60
    if hours < 4 and remainder:
        return f"{hours}h {remainder}m"
    if hours < 24:
        return f"{hours}h"
    if minutes < 48 * 60:
        return "yesterday"
    return f"{minutes // (24 * 60)}d"


def freshness_label(minutes: int, *, alert_freshness_hours: int, dashboard_freshness_hours: int) -> str:
    if minutes < 30:
        return f"🟢 Just posted ({minutes}m ago)"
    tone = freshness_tone_from_minutes(
        minutes,
        alert_freshness_hours=alert_freshness_hours,
        dashboard_freshness_hours=dashboard_freshness_hours,
    )
    if tone == "fresh":
        return f"🟢 Posted {_compact_age(minutes)} ago"
    if tone == "aging":
        return f"🟡 Posted {_compact_age(minutes)} ago"
    if minutes < 48 * 60:
        return "🔴 Posted yesterday"
    return f"🔴 Posted {_compact_age(minutes)} ago"


def recommendation_label(decision: str) -> str:
    if decision == "APPLY_NOW":
        return "Apply Immediately"
    if decision == "REVIEW":
        return "Review Before Applying"
    return "Skip"


def recommendation_tone(decision: str) -> RecommendationTone:
    if decision == "APPLY_NOW":
        return "apply"
    if decision == "REVIEW":
        return "review"
    return "skip"
