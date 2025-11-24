#!/usr/bin/env python3
"""
Complete Weather Dashboard for Waveshare E-Paper Display
Fetches weather, renders HTML, generates PNG, and displays on e-paper
"""

from pathlib import Path
from jinja2 import Template
import requests
from datetime import datetime
import time
import subprocess
from PIL import Image
from rich import print_json
import sys

# Import Waveshare library
try:
    from waveshare_epd.epd7in3f import EPD
    EPAPER_AVAILABLE = True
except ImportError:
    print("⚠ Warning: waveshare_epd library not found. Running in preview mode only.")
    EPAPER_AVAILABLE = False

# Configuration
API_KEY_PATH = Path("API_keys/avwxkeys.txt")
AIRPORT = "KSKA"  # Change to your airport
HTML_OUTPUT = Path("output/weather.html")
PNG_OUTPUT = Path("output/weather.png")
TEMPLATE_PATH = Path("templates/page.html")
UPDATE_INTERVAL = 300  # 5 minutes

# Display dimensions
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

def get_weather_data(airport, token):
    """Fetch weather data"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    url_metar = f"https://avwx.rest/api/metar/{airport}?remove=true"
    url_station = f"https://avwx.rest/api/station/{airport}"
    url_taf = f"https://avwx.rest/api/taf/{airport}"
    
    try:
        response = requests.get(url_metar, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching METAR: {e}")
        return None
    
    try:
        response1 = requests.get(url_station, headers=headers, timeout=10)
        response1.raise_for_status()
        data1 = response1.json()
        arpt_name = data1["name"]
    except:
        arpt_name = airport
    
    try:
        response2 = requests.get(url_taf, headers=headers, timeout=10)
        response2.raise_for_status()
        data2 = response2.json()
        tafraw = [line["sanitized"] for line in data2["forecast"]]
    except:
        tafraw = ["TAF not available"]
    
    # Extract all weather data
    arpt = data["station"]
    flight_rules = data["flight_rules"]
    vis = data["visibility"]["repr"]
    cig = data["clouds"]
    px = data["altimeter"]["value"]
    temp = data["temperature"]["value"]
    dewpt = data["dewpoint"]["value"]
    wind = data["wind_speed"]["value"]
    gust = data["wind_gust"]
    winddir = data["wind_direction"]["value"]
    pa = data["pressure_altitude"]
    da = data["density_altitude"]
    
    cloudlayers = [layer["repr"] for layer in cig]
    
    aarowdir = str((winddir + 180) % 360) + "deg"
    
    wxcodes = data["wx_codes"]
    wxcode = [code["repr"] for code in wxcodes]
    maincode = wxcodes[0]["value"] if wxcodes else None
    
    if not maincode:
        has_low_clouds = any(layer.get("altitude", 999) < 100 for layer in cig)
        maincode = "CLOUDY" if has_low_clouds else "SKY CLEAR"
    
    ts = data["time"]["dt"]
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    updatetime = dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    
    return {
        "tafraw": tafraw, "time": updatetime, "aarowdir": aarowdir,
        "rules": flight_rules, "arpt": arpt, "ArptName": arpt_name,
        "vis": vis, "cig": cloudlayers, "px": px, "temp": temp,
        "dewpt": dewpt, "wind": wind, "gust": gust, "winddir": winddir,
        "wxcode": wxcode, "pa": pa, "da": da, "obs": maincode,
    }

def copy_static_files():
    """Copy static files to output directory"""
    import shutil
    static_src = Path("static")
    static_dst = Path("output/static")
    
    if static_src.exists():
        shutil.copytree(static_src, static_dst, dirs_exist_ok=True)
        print(f"✓ Copied static files")
    else:
        print("⚠ No static folder found")

def render_html(template_path, weather_data, output_path):
    """Render template to HTML"""
    from jinja2 import Environment, FileSystemLoader
    
    # Set up Jinja2 environment with template directory
    env = Environment(loader=FileSystemLoader(template_path.parent))
    
    # Add url_for function that returns static paths
    def url_for(endpoint, filename=None, **values):
        if endpoint == 'static' and filename:
            return f'static/{filename}'
        return '#'
    
    # Add url_for to globals
    env.globals['url_for'] = url_for
    
    # Load and render template
    template = env.get_template(template_path.name)
    html_output = template.render(**weather_data)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html_output)
    
    print(f"✓ HTML: {output_path}")

def html_to_png(html_path, png_path):
    """Convert HTML to PNG"""
    png_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Try different screenshot tools
    commands = [
        ['wkhtmltoimage', '--width', str(DISPLAY_WIDTH), '--height', str(DISPLAY_HEIGHT),
         '--quality', '100', str(html_path), str(png_path)],
        ['chromium-browser', '--headless', '--disable-gpu',
         f'--screenshot={png_path}', f'--window-size={DISPLAY_WIDTH},{DISPLAY_HEIGHT}',
         f'file://{html_path.absolute()}'],
    ]
    
    for cmd in commands:
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✓ PNG: {png_path}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    print("❌ No screenshot tool found (install wkhtmltoimage or chromium-browser)")
    return False

def display_on_epaper(image_path):
    """Display image on e-paper"""
    if not EPAPER_AVAILABLE:
        print("⚠ E-paper display not available - skipping")
        return
    
    try:
        epd = EPD()
        epd.init()
        
        image = Image.open(image_path)
        if image.size != (800, 480):
            image = image.resize((800, 480), Image.Resampling.LANCZOS)
        
        epd.display(epd.getbuffer(image))
        epd.sleep()
        
        print("✓ Displayed on e-paper")
    except Exception as e:
        print(f"❌ E-paper error: {e}")

def update_cycle():
    """Complete update cycle"""
    print(f"\n{'='*60}")
    print(f"Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    try:
        token = API_KEY_PATH.read_text().strip()
        
        print(f"Fetching {AIRPORT}...")
        weather_data = get_weather_data(AIRPORT, token)
        if not weather_data:
            return False
        
        # Copy static files (CSS, JS, images)
        copy_static_files()
        
        render_html(TEMPLATE_PATH, weather_data, HTML_OUTPUT)
        
        if not html_to_png(HTML_OUTPUT, PNG_OUTPUT):
            return False
        
        display_on_epaper(PNG_OUTPUT)
        
        print("✅ Update complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main loop"""
    print(f"Weather Dashboard - {AIRPORT}")
    print(f"Update every {UPDATE_INTERVAL//60} minutes")
    
    while True:
        update_cycle()
        print(f"\nNext update: {(datetime.now().timestamp() + UPDATE_INTERVAL)}")
        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    try:
        update_cycle()
        
        response = input("\nRun continuous updates? (y/n): ")
        if response.lower() == 'y':
            main()
    except KeyboardInterrupt:
        print("\n\nStopped by user")