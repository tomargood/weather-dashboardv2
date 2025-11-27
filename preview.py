#!/usr/bin/env python3
"""
Weather Dashboard - Local Testing Version
=========================================
Run this on your local machine to preview the e-paper display
before deploying to the Raspberry Pi.

Features:
- Mock data mode (no API key required)
- Live data mode (with API key)
- Browser preview
- Optional screenshot generation
"""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import webbrowser
import argparse
import shutil
import http.server
import socketserver
import threading

# Configuration
DEFAULT_AIRPORT = "KSKA"
TEMPLATE = Path("templates/page.html")
HTML_OUT = Path("output/weather.html")
PNG_OUT = Path("output/weather.png")
PORT = 8080

# ============================================================================
# MOCK DATA - Edit this to test different weather scenarios
# ============================================================================

MOCK_SCENARIOS = {
    "clear": {
        "arpt": "KSKA",
        "ArptName": "Spokane International Airport",
        "rules": "VFR",
        "vis": "10SM",
        "cig": ["SKC"],
        "px": 30.12,
        "temp": 22,
        "dewpt": 10,
        "wind": 8,
        "gust": None,
        "winddir": 270,
        "aarowdir": "90deg",
        "wxcode": [],
        "pa": 2500,
        "da": 3200,
        "obs": "SKY CLEAR",
        "tafraw": [
            "FM121800 27008KT P6SM SKC",
            "FM130000 VRB03KT P6SM SKC",
            "FM131500 28012KT P6SM FEW080"
        ],
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
    },
    "ifr": {
        "arpt": "KSKA",
        "ArptName": "Spokane International Airport",
        "rules": "IFR",
        "vis": "1SM",
        "cig": ["BKN003", "OVC010"],
        "px": 29.85,
        "temp": 8,
        "dewpt": 7,
        "wind": 12,
        "gust": 20,
        "winddir": 180,
        "aarowdir": "0deg",
        "wxcode": ["BR", "FG"],
        "pa": 2600,
        "da": 2800,
        "obs": "FG",
        "tafraw": [
            "FM121800 18012G20KT 1SM BR BKN003 OVC010",
            "FM130600 VRB05KT 3SM BR SCT010 BKN020",
            "FM131400 27008KT P6SM SCT030"
        ],
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
    },
    "mvfr": {
        "arpt": "KSKA",
        "ArptName": "Spokane International Airport",
        "rules": "MVFR",
        "vis": "5SM",
        "cig": ["SCT015", "BKN025"],
        "px": 29.92,
        "temp": 15,
        "dewpt": 12,
        "wind": 15,
        "gust": None,
        "winddir": 320,
        "aarowdir": "140deg",
        "wxcode": ["HZ"],
        "pa": 2550,
        "da": 3000,
        "obs": "CLOUDY",
        "tafraw": [
            "FM121800 32015KT 5SM HZ SCT015 BKN025",
            "FM130300 30010KT P6SM SCT030",
            "FM131200 28008KT P6SM FEW040"
        ],
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
    },
    "stormy": {
        "arpt": "KSKA",
        "ArptName": "Spokane International Airport",
        "rules": "LIFR",
        "vis": "1/2SM",
        "cig": ["BKN005", "OVC012CB"],
        "px": 29.45,
        "temp": 18,
        "dewpt": 17,
        "wind": 25,
        "gust": 40,
        "winddir": 230,
        "aarowdir": "50deg",
        "wxcode": ["+TSRA", "FG"],
        "pa": 2700,
        "da": 3500,
        "obs": "+TSRA",
        "tafraw": [
            "FM121800 23025G40KT 1/2SM +TSRA BKN005 OVC012CB",
            "FM122200 25015G25KT 2SM TSRA BKN010 OVC020",
            "FM130400 27010KT 5SM -RA SCT015 BKN030"
        ],
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
    },
}


def get_mock_data(scenario="clear"):
    """Get mock weather data for testing"""
    if scenario not in MOCK_SCENARIOS:
        print(f"Unknown scenario '{scenario}'. Available: {list(MOCK_SCENARIOS.keys())}")
        scenario = "clear"
    
    data = MOCK_SCENARIOS[scenario].copy()
    data["time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    return data


def fetch_live_weather(airport, debug=False):
    """Get real weather data from AVWX API (requires API key)"""
    import requests
    import json
    
    api_key_file = Path("API_keys/avwxkeys.txt")
    if not api_key_file.exists():
        raise FileNotFoundError(
            f"API key not found at {api_key_file}\n"
            "Use --mock flag to test with mock data instead."
        )
    
    API_KEY = api_key_file.read_text().strip()
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # Get METAR
    metar = requests.get(
        f"https://avwx.rest/api/metar/{airport}?remove=true",
        headers=headers, timeout=10
    ).json()
    
    # Get Station name
    try:
        station = requests.get(
            f"https://avwx.rest/api/station/{airport}",
            headers=headers, timeout=10
        ).json()
        arpt_name = station["name"]
    except:
        arpt_name = airport
    
    # Get TAF
    taf_raw_json = None
    try:
        taf = requests.get(
            f"https://avwx.rest/api/taf/{airport}",
            headers=headers, timeout=10
        ).json()
        taf_raw_json = taf
        tafraw = [line["sanitized"] for line in taf["forecast"]]
    except:
        tafraw = ["TAF not available"]
    
    # Debug output
    if debug:
        print("\n" + "="*60)
        print("RAW TAF JSON:")
        print("="*60)
        print(json.dumps(taf_raw_json, indent=2))
        print("="*60)
        print("\nPARSED tafraw list:")
        for i, line in enumerate(tafraw):
            print(f"  [{i}] '{line}'")
        print("="*60 + "\n")
    
    # Extract weather data
    winddir = metar["wind_direction"]["value"]
    aarowdir = str((winddir + 180) % 360) + "deg"
    
    wxcodes = metar["wx_codes"]
    maincode = wxcodes[0]["value"] if wxcodes else None
    if not maincode:
        has_low_clouds = any(
            layer.get("altitude", 999) < 100 
            for layer in metar["clouds"]
        )
        maincode = "CLOUDY" if has_low_clouds else "SKY CLEAR"
    
    dt = datetime.fromisoformat(metar["time"]["dt"].replace("Z", "+00:00"))
    
    return {
        "arpt": metar["station"],
        "ArptName": arpt_name,
        "rules": metar["flight_rules"],
        "vis": metar["visibility"]["repr"],
        "cig": [layer["repr"] for layer in metar["clouds"]],
        "px": metar["altimeter"]["value"],
        "temp": metar["temperature"]["value"],
        "dewpt": metar["dewpoint"]["value"],
        "wind": metar["wind_speed"]["value"],
        "gust": metar["wind_gust"],
        "winddir": winddir,
        "aarowdir": aarowdir,
        "wxcode": [code["repr"] for code in wxcodes],
        "pa": metar["pressure_altitude"],
        "da": metar["density_altitude"],
        "obs": maincode,
        "tafraw": tafraw,
        "time": dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


def render_html(data):
    """Render Jinja template to HTML"""
    if not TEMPLATE.exists():
        raise FileNotFoundError(
            f"Template not found at {TEMPLATE}\n"
            "Please create your template or copy it from the Pi."
        )
    
    env = Environment(loader=FileSystemLoader(TEMPLATE.parent))
    env.globals['url_for'] = lambda endpoint, filename=None: f'static/{filename}' if filename else '#'
    
    template = env.get_template(TEMPLATE.name)
    html = template.render(**data)
    
    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(html)
    
    # Copy static files
    static_src = Path("static")
    static_dst = Path("output/static")
    if static_src.exists():
        shutil.copytree(static_src, static_dst, dirs_exist_ok=True)
    
    return HTML_OUT


def take_screenshot():
    """Take a screenshot using available browser"""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 780, "height": 500})
            page.goto(f"file://{HTML_OUT.absolute()}")
            page.screenshot(path=str(PNG_OUT))
            browser.close()
        
        print(f"  ✓ Screenshot saved: {PNG_OUT}")
        return True
        
    except ImportError:
        print("  ℹ Playwright not installed. Trying Selenium...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--window-size=780,500")
        options.add_argument("--hide-scrollbars")
        options.add_argument("--force-device-scale-factor=1")
        
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(780, 500)
        driver.get(f"file://{HTML_OUT.absolute()}")
        driver.save_screenshot(str(PNG_OUT))
        driver.quit()
        
        print(f"  ✓ Screenshot saved: {PNG_OUT}")
        return True
        
    except ImportError:
        print("  ℹ Selenium not installed. Skipping screenshot.")
        print("  ℹ Install with: pip install playwright && playwright install")
        print("  ℹ Or: pip install selenium webdriver-manager")
        return False
    except Exception as e:
        print(f"  ✗ Screenshot failed: {e}")
        return False


def serve_and_open(port=PORT):
    """Start a local server and open browser"""
    
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress logging
    
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True
    
    # Change to output directory
    import os
    original_dir = os.getcwd()
    os.chdir("output")
    
    # Try the requested port, then fall back to alternatives
    for try_port in [port, port + 1, port + 2, 0]:  # 0 = let OS pick
        try:
            httpd = ReusableTCPServer(("", try_port), QuietHandler)
            if try_port == 0:
                try_port = httpd.server_address[1]
            if try_port != port:
                print(f"  ℹ Port {port} in use, using {try_port}")
            break
        except OSError:
            if try_port == 0:
                raise
            continue
    
    try:
        with httpd:
            url = f"http://localhost:{try_port}/weather.html"
            print(f"\n🌐 Preview: {url}")
            print("   Press Ctrl+C to stop\n")
            
            # Open browser in background
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()
            
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Server stopped")
    finally:
        os.chdir(original_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Weather Dashboard - Local Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python weather_local.py --mock              # Preview with VFR conditions
  python weather_local.py --mock ifr          # Preview with IFR conditions  
  python weather_local.py --mock stormy       # Preview with thunderstorm
  python weather_local.py --live              # Use real API data
  python weather_local.py --mock --screenshot # Also generate PNG

Available scenarios: clear, ifr, mvfr, stormy
        """
    )
    
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mock", nargs="?", const="clear", metavar="SCENARIO",
                      help="Use mock data (default: clear)")
    mode.add_argument("--live", action="store_true",
                      help="Use live API data (requires API key)")
    
    parser.add_argument("--screenshot", "-s", action="store_true",
                        help="Generate PNG screenshot")
    parser.add_argument("--no-browser", "-n", action="store_true",
                        help="Don't open browser")
    parser.add_argument("--debug", "-d", action="store_true",
                        help="Show raw API data (JSON)")
    parser.add_argument("--port", "-p", type=int, default=PORT,
                        help=f"Server port (default: {PORT})")
    parser.add_argument("--airport", "-a", default=DEFAULT_AIRPORT,
                        help=f"Airport code for live data (default: {DEFAULT_AIRPORT})")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Weather Dashboard - Local Testing")
    print("=" * 60)
    
    # Get weather data
    if args.mock:
        print(f"\n📊 Using mock data: {args.mock}")
        data = get_mock_data(args.mock)
    else:
        print(f"\n📡 Fetching live data for {args.airport}...")
        try:
            data = fetch_live_weather(args.airport, debug=args.debug)
        except Exception as e:
            print(f"❌ Error: {e}")
            return
    
    # Show summary
    print(f"\n   Station: {data['arpt']} - {data['ArptName']}")
    print(f"   Rules:   {data['rules']}")
    print(f"   Weather: {data['obs']}")
    print(f"   Wind:    {data['winddir']}° @ {data['wind']}kt", end="")
    if data['gust']:
        print(f" G{data['gust']}")
    else:
        print()
    
    # Render HTML
    print("\n🎨 Rendering HTML...")
    try:
        render_html(data)
        print(f"   ✓ Output: {HTML_OUT}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Take screenshot if requested
    if args.screenshot:
        print("\n📸 Taking screenshot...")
        take_screenshot()
    
    # Open browser (skip if --no-browser or if only taking screenshot)
    if not args.no_browser and not args.screenshot:
        serve_and_open(args.port)


if __name__ == "__main__":
    main()