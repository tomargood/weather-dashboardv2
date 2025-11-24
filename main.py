#!/usr/bin/env python3
"""
Weather Dashboard for E-Paper Display
Fetch weather → Render HTML → Screenshot → Display on e-ink
"""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import requests
from datetime import datetime
import time
import subprocess
from PIL import Image

# Configuration
API_KEY = Path("API_keys/avwxkeys.txt").read_text().strip()
AIRPORT = "KSKA"
TEMPLATE = Path("templates/page.html")
HTML_OUT = Path("output/weather.html")
PNG_OUT = Path("output/weather.png")
UPDATE_INTERVAL = 300  # 5 minutes

# Try to import e-paper display
try:
    from waveshare_epd.epd7in3f import EPD
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False
    print("⚠ No e-paper display available")

def fetch_weather():
    """Get weather data from AVWX API"""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # Get METAR
    metar = requests.get(f"https://avwx.rest/api/metar/{AIRPORT}?remove=true", 
                         headers=headers, timeout=10).json()
    
    # Get Station
    try:
        station = requests.get(f"https://avwx.rest/api/station/{AIRPORT}", 
                              headers=headers, timeout=10).json()
        arpt_name = station["name"]
    except:
        arpt_name = AIRPORT
    
    # Get TAF
    try:
        taf = requests.get(f"https://avwx.rest/api/taf/{AIRPORT}", 
                          headers=headers, timeout=10).json()
        tafraw = [line["sanitized"] for line in taf["forecast"]]
    except:
        tafraw = ["TAF not available"]
    
    # Extract weather data
    winddir = metar["wind_direction"]["value"]
    aarowdir = str((winddir + 180) % 360) + "deg"
    
    wxcodes = metar["wx_codes"]
    maincode = wxcodes[0]["value"] if wxcodes else None
    if not maincode:
        has_low_clouds = any(layer.get("altitude", 999) < 100 for layer in metar["clouds"])
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
    env = Environment(loader=FileSystemLoader(TEMPLATE.parent))
    env.globals['url_for'] = lambda endpoint, filename=None: f'static/{filename}' if filename else '#'
    
    template = env.get_template(TEMPLATE.name)
    html = template.render(**data)
    
    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(html)
    
    # Copy static files
    import shutil
    static_src = Path("static")
    static_dst = Path("output/static")
    if static_src.exists():
        shutil.copytree(static_src, static_dst, dirs_exist_ok=True)

def screenshot():
    """Take screenshot with Chromium"""
    try:
        print(f"  Using chromium-browser...")
        subprocess.run([
            'chromium',
            '--headless',
            '--disable-gpu',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-software-rasterizer',
            '--window-size=812,620',
            '--force-device-scale-factor=1',
            f'--screenshot={PNG_OUT.absolute()}',
            f'file://{HTML_OUT.absolute()}'
        ], capture_output=True, timeout=60, check=True)
        
        # Verify the screenshot
        if PNG_OUT.exists():
            img = Image.open(PNG_OUT)
            print(f"  Screenshot: {img.size[0]}x{img.size[1]}")
            
            # Resize to exact 800x480 if needed
            if img.size != (800, 480):
                img = img.resize((800, 480), Image.Resampling.LANCZOS)
                img.save(PNG_OUT)
                print(f"  Resized to: 800x480")
            
            return True
        else:
            print(f"  ✗ PNG not created")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  ✗ Timeout after 60 seconds")
        print(f"  Chromium is taking too long - may need more memory/CPU")
        return False
    except FileNotFoundError:
        print(f"  ✗ chromium-browser not found")
        print(f"  Install with: sudo apt install chromium-browser")
        return False
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Chromium error: {e}")
        return False

def display():
    """Show on e-paper display"""
    if not HAS_DISPLAY:
        print("⚠ Skipping display (no hardware)")
        return
    
    epd = EPD()
    epd.init()
    img = Image.open(PNG_OUT)
    epd.display(epd.getbuffer(img))
    epd.sleep()

def update():
    """Full update cycle"""
    print(f"\n{'='*60}")
    print(f"Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    try:
        print("Fetching weather...")
        data = fetch_weather()
        
        print("Rendering HTML...")
        render_html(data)
        
        print("Taking screenshot...")
        if not screenshot():
            return
        
        print("Displaying on e-paper...")
        display()
        
        print("✅ Update complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Run once
    update()
    
    # Ask about continuous updates
    response = input("\nRun continuous updates every 5 minutes? (y/n): ")
    if response.lower() == 'y':
        while True:
            time.sleep(UPDATE_INTERVAL)
            update()