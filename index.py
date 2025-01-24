from flask import Flask, request, jsonify, Response
import requests
import polyline
import math
import csv
import io

app = Flask(__name__)

# Google API Key
GOOGLE_API_KEY = "AIzaSyAyyAyxzjBMd5FgUCoWRpG335omtxh7woA"

# Helper function: Calculate distance using Haversine formula
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Fetch traffic/incident data from Google Places API
def fetch_accident_data(lat, lng, radius=2000):
    places_url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        f"?location={lat},{lng}&radius={radius}&type=point_of_interest&keyword=traffic&key={GOOGLE_API_KEY}"
    )
    response = requests.get(places_url)
    if response.status_code != 200:
        return []
    places_data = response.json()
    accidents = []
    for result in places_data.get("results", []):
        accidents.append({
            "area": result.get("name", "Unknown Area"),
            "latitude": result["geometry"]["location"]["lat"],
            "longitude": result["geometry"]["location"]["lng"],
            "accident_count": result.get("user_ratings_total", 0),  # Number of ratings as a proxy
        })
    return accidents

# Endpoint to get accident-prone areas along a route and return a CSV
@app.route("/get-accident-prone-areas-csv", methods=["POST"])
def get_accident_prone_areas_csv():
    data = request.json
    source = data.get("source")
    destination = data.get("destination")

    if not source or not destination:
        return jsonify({"error": "Source and destination are required"}), 400

    # Fetch route data from Google Directions API
    directions_url = (
        f"https://maps.googleapis.com/maps/api/directions/json?origin={source}&destination={destination}&key={GOOGLE_API_KEY}"
    )
    response = requests.get(directions_url)

    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch route data"}), 500

    route_data = response.json()
    if route_data["status"] != "OK":
        return jsonify({"error": "No route found"}), 404

    # Decode the polyline from the route
    polyline_data = route_data["routes"][0]["overview_polyline"]["points"]
    route_points = polyline.decode(polyline_data)

    # Fetch accident data for each route point
    accident_prone_areas = []
    for point in route_points:
        lat, lng = point
        accidents = fetch_accident_data(lat, lng)
        accident_prone_areas.extend(accidents)

    # Remove duplicates based on coordinates
    unique_areas = {f"{area['latitude']},{area['longitude']}": area for area in accident_prone_areas}.values()

    # Create a CSV response
    output = io.StringIO()
    csv_writer = csv.DictWriter(output, fieldnames=["area", "latitude", "longitude", "accident_count"])
    csv_writer.writeheader()
    csv_writer.writerows(unique_areas)

    # Make sure the file is ready to be downloaded
    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=accident_prone_areas.csv"},
    )

if __name__ == "__main__":
    app.run(debug=True)

