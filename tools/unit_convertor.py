from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("UnitConverter")

# Define tools for unit conversion
@mcp.tool()
def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """Convert temperature between Celsius, Fahrenheit, and Kelvin."""
    if from_unit == "Celsius" and to_unit == "Fahrenheit":
        return (value * 9/5) + 32
    elif from_unit == "Celsius" and to_unit == "Kelvin":
        return value + 273.15
    elif from_unit == "Fahrenheit" and to_unit == "Celsius":
        return (value - 32) * 5/9
    elif from_unit == "Fahrenheit" and to_unit == "Kelvin":
        return ((value - 32) * 5/9) + 273.15
    elif from_unit == "Kelvin" and to_unit == "Celsius":
        return value - 273.15
    elif from_unit == "Kelvin" and to_unit == "Fahrenheit":
        return ((value - 273.15) * 9/5) + 32
    else:
        raise ValueError("Invalid temperature units")

@mcp.tool()
def convert_length(value: float, from_unit: str, to_unit: str) -> float:
    """Convert length between meters, kilometers, miles, and feet."""
    conversion_factors = {
        ("meters", "kilometers"): 0.001,
        ("meters", "miles"): 0.000621371,
        ("meters", "feet"): 3.28084,
        ("kilometers", "meters"): 1000,
        ("kilometers", "miles"): 0.621371,
        ("kilometers", "feet"): 3280.84,
        ("miles", "meters"): 1609.34,
        ("miles", "kilometers"): 1.60934,
        ("miles", "feet"): 5280,
        ("feet", "meters"): 0.3048,
        ("feet", "kilometers"): 0.0003048,
        ("feet", "miles"): 0.000189394,
    }
    factor = conversion_factors.get((from_unit.lower(), to_unit.lower()))
    if factor is None:
        raise ValueError("Invalid length units")
    return value * factor

# Start the MCP server
if __name__ == "__main__":
    mcp.run()
