"""Flask application for searching optimal train routes using Google Routes API."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
import requests
from flask import Flask, render_template, request, flash

GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.legs.steps.transitDetails"
DEFAULT_TIMEZONE = "Asia/Seoul"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")


@dataclass
class TransitStep:
    """Represents a single transit segment within a leg of a route."""

    line_name: Optional[str]
    vehicle_type: Optional[str]
    headsign: Optional[str]
    departure_stop: Optional[str]
    departure_time: Optional[str]
    arrival_stop: Optional[str]
    arrival_time: Optional[str]
    stop_count: Optional[int]


@dataclass
class RouteLeg:
    """Represents a leg of the route made of multiple transit steps."""

    steps: List[TransitStep]


@dataclass
class TransitRoute:
    """Container for a single transit route with one or more legs."""

    legs: List[RouteLeg]


def local_datetime_to_rfc3339(local_datetime: str, timezone_name: str) -> str:
    """Convert an ISO 8601 naive local datetime string to RFC3339 in UTC."""

    if not local_datetime:
        raise ValueError("A departure date and time is required.")

    try:
        naive_dt = datetime.strptime(local_datetime, "%Y-%m-%dT%H:%M")
    except ValueError as exc:
        raise ValueError("Departure time must be provided in YYYY-MM-DDTHH:MM format.") from exc

    try:
        timezone = pytz.timezone(timezone_name)
    except pytz.UnknownTimeZoneError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name}") from exc

    localized_dt = timezone.localize(naive_dt)
    utc_dt = localized_dt.astimezone(pytz.utc)
    return utc_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rfc3339_to_local_time_string(timestamp: Optional[str], timezone_name: str) -> Optional[str]:
    """Convert an RFC3339 timestamp to a formatted string in the target timezone."""

    if not timestamp:
        return None

    try:
        if timestamp.endswith("Z"):
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(timestamp)
    except ValueError:
        return timestamp

    try:
        timezone = pytz.timezone(timezone_name)
    except pytz.UnknownTimeZoneError:
        timezone = pytz.utc

    local_dt = dt.astimezone(timezone)
    return local_dt.strftime("%Y-%m-%d %H:%M (%Z)")


def pick_localized_time(transit_details: Dict[str, Any], key: str) -> Optional[str]:
    """Pick a localized time string from the API response if present."""

    localized = transit_details.get("localizedValues") or {}
    time_info = (localized.get(key) or {}).get("time") or {}
    return time_info.get("text")


def build_request_body(
    origin: str,
    destination: str,
    departure_time_rfc3339: str,
    routing_preference: str,
) -> Dict[str, Any]:
    """Construct the request body for the Directions API."""

    return {
        "origin": {"address": origin},
        "destination": {"address": destination},
        "travelMode": "TRANSIT",
        "departureTime": departure_time_rfc3339,
        "transitPreferences": {
            "routingPreference": routing_preference,
        },
        "computeAlternativeRoutes": True,
    }


def build_headers(api_key: str) -> Dict[str, str]:
    """Build the HTTP headers including API key and field mask."""

    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }


def parse_transit_routes(response: Dict[str, Any], timezone_name: str) -> List[TransitRoute]:
    """Extract transit legs and steps from the API response."""

    routes: List[TransitRoute] = []
    for route in response.get("routes", []):
        legs: List[RouteLeg] = []
        for leg in route.get("legs", []):
            steps: List[TransitStep] = []
            for step in leg.get("steps", []):
                transit_details = step.get("transitDetails")
                if not transit_details:
                    continue

                stop_details = transit_details.get("stopDetails") or {}
                departure_stop = (stop_details.get("departureStop") or {}).get("name")
                arrival_stop = (stop_details.get("arrivalStop") or {}).get("name")

                departure_localized = pick_localized_time(transit_details, "departureTime")
                arrival_localized = pick_localized_time(transit_details, "arrivalTime")

                departure_time = departure_localized or rfc3339_to_local_time_string(
                    stop_details.get("departureTime"), timezone_name
                )
                arrival_time = arrival_localized or rfc3339_to_local_time_string(
                    stop_details.get("arrivalTime"), timezone_name
                )

                line_info = transit_details.get("transitLine") or {}
                line_name = line_info.get("nameShort") or line_info.get("name")
                vehicle_type = (line_info.get("vehicle") or {}).get("type")
                headsign = transit_details.get("headsign") or (line_info.get("headsigns") or [None])[0]

                stop_count = transit_details.get("stopCount")

                steps.append(
                    TransitStep(
                        line_name=line_name,
                        vehicle_type=vehicle_type,
                        headsign=headsign,
                        departure_stop=departure_stop,
                        departure_time=departure_time,
                        arrival_stop=arrival_stop,
                        arrival_time=arrival_time,
                        stop_count=stop_count,
                    )
                )
            if steps:
                legs.append(RouteLeg(steps=steps))
        if legs:
            routes.append(TransitRoute(legs=legs))
    return routes


@app.route("/", methods=["GET", "POST"])
def index():
    routes: List[TransitRoute] = []
    error: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None

    if request.method == "POST":
        origin = (request.form.get("origin") or "").strip()
        destination = (request.form.get("destination") or "").strip()
        departure = request.form.get("departure") or ""
        timezone_name = (request.form.get("timezone") or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
        routing_preference = request.form.get("routing_preference") or "FEWER_TRANSFERS"

        if not origin or not destination:
            error = "Both origin and destination are required."
        else:
            try:
                departure_rfc3339 = local_datetime_to_rfc3339(departure, timezone_name)
            except ValueError as exc:
                error = str(exc)
            else:
                api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
                if not api_key:
                    error = "The GOOGLE_MAPS_API_KEY environment variable is not set."
                else:
                    body = build_request_body(origin, destination, departure_rfc3339, routing_preference)
                    try:
                        response = requests.post(
                            GOOGLE_ROUTES_URL,
                            headers=build_headers(api_key),
                            json=body,
                            timeout=20,
                        )
                        response.raise_for_status()
                        raw_response = response.json()
                        routes = parse_transit_routes(raw_response, timezone_name)
                        if not routes:
                            error = "No transit routes were returned for the specified search."
                    except requests.HTTPError:
                        try:
                            raw_response = response.json()
                            error_message = raw_response.get("error", {}).get("message")
                        except Exception:  # noqa: BLE001
                            error_message = response.text
                        error = f"API request failed: {error_message or response.reason}"
                    except requests.RequestException as exc:
                        error = f"An error occurred while contacting the API: {exc}"

        if error:
            flash(error, "error")
        elif routes:
            flash("Routes loaded successfully.", "success")

    return render_template(
        "index.html",
        routes=routes,
        raw_response=raw_response,
        search_params={
            "origin": request.form.get("origin", ""),
            "destination": request.form.get("destination", ""),
            "departure": request.form.get("departure", ""),
            "timezone": request.form.get("timezone", DEFAULT_TIMEZONE),
            "routing_preference": request.form.get("routing_preference", "FEWER_TRANSFERS"),
        },
    )


if __name__ == "__main__":
    app.run(debug=True)
