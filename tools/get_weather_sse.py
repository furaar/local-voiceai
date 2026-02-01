# weather_server.py
from typing import List
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import os
import requests

mcp = FastMCP("Weather",host="localhost", port=9080)
load_dotenv()
@mcp.tool()
async def get_weather(location: str) -> dict:
    """Get weather for location via HTTP call."""
    weather_api_key = os.environ["OPENWEATHER_API_KEY"]
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={weather_api_key}&units=metric"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes
        data = response.json()
        return {
            "temperature": data["main"]["temp"],
            "weather": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
            "url":url,
        }
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

if __name__ == "__main__":
    mcp.run(transport="sse")
