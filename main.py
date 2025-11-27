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
import sys
import threading
import select

# Configuration
API_KEY = Path("API_keys/avwxkeys.txt").read_text().strip()
CURRENT_AIRPORT = "KSKA"  # Default airport
TEMPLATE = Path("templates/page.html")
HTML_OUT = Path("output/weather.html")
PNG_OUT = Path("output/weather.png")
UPDATE_INTERVAL = 300  # 5 minutes

# Cache for last displayed data
LAST_DATA = None

# Flag for new airport entered
NEW_AIRPORT = None

# Try to import e-paper display
try:
    from waveshare_epd.epd7in3f import EPD
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False
    print("⚠ No e-paper display available")

def fetch_weather():
    """Get weather data from AVWX API"""
    global CURRENT_AIRPORT
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # Get METAR
    metar = requests.get(f"https://avwx.rest/api/metar/{CURRENT_AIRPORT}?remove=true", 
                         headers=headers, timeout=10).json()
    
    # Get Station
    try:
        station = requests.get(f"https://avwx.rest/api/station/{CURRENT_AIRPORT}", 
                              headers=headers, timeout=10).json()
        arpt_name = station["name"]
    except:
        arpt_name = CURRENT_AIRPORT
    
    # Get TAF
    try:
        taf = requests.get(f"https://avwx.rest/api/taf/{CURRENT_AIRPORT}", 
                          headers=headers, timeout=10).json()
        tafraw = [line["sanitized"] for line in taf["forecast"]]
    except:
        tafraw = ["TAF not available"]
    
    # Extract weather data
    winddir = metar["wind_direction"]["value"]
    aarowdir = str((winddir + 180) % 360) + "deg"
    
    # Format wind direction with leading zeros (e.g., 040)
    winddir_formatted = f"{winddir:03d}"
    
    # Format pressure to always show 4 digits (e.g., 29.10)
    pressure = metar["altimeter"]["value"]
    pressure_formatted = f"{pressure:.2f}"
    
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
        "px": pressure_formatted,
        "temp": metar["temperature"]["value"],
        "dewpt": metar["dewpoint"]["value"],
        "wind": metar["wind_speed"]["value"],
        "gust": metar["wind_gust"],
        "winddir": winddir_formatted,
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
            '--kiosk',
            '--hide-scrollbars',
            '--disable-dev-shm-usage',
            '--disable-software-rasterizer',
            '--force-device-scale-factor=1',
            f'--screenshot={PNG_OUT.absolute()}',
            f'file://{HTML_OUT.absolute()}'
        ], capture_output=True, timeout=60, check=True)
        
        # Verify the screenshot
        if PNG_OUT.exists():
            img = Image.open(PNG_OUT)
            print(f"  Screenshot: {img.size[0]}x{img.size[1]}")
            
            # Resize to exact 800x480 if needed
            if img.size != (800, 480 ):
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

def data_changed(new_data):
    """Check if weather data has changed (ignoring timestamp)"""
    global LAST_DATA
    
    if LAST_DATA is None:
        return True
    
    # Compare all fields except time
    for key in new_data:
        if key == 'time':
            continue
        if new_data[key] != LAST_DATA.get(key):
            return True
    
    return False


def update(force_refresh=False):
    """Full update cycle"""
    global LAST_DATA
    
    print(f"\n{'='*60}")
    print(f"Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {CURRENT_AIRPORT}")
    print(f"{'='*60}")
    
    try:
        print("Fetching weather...")
        data = fetch_weather()
        
        # Check if data has changed
        if not force_refresh and not data_changed(data):
            print("📊 No changes detected - skipping display refresh")
            return
        
        print("Rendering HTML...")
        render_html(data)
        
        print("Taking screenshot...")
        if not screenshot():
            return
        
        print("Displaying on e-paper...")
        display()
        
        # Update the cache
        LAST_DATA = data.copy()
        
        print("✅ Update complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def clear_display():
    """Clear the e-paper display and put it to sleep"""
    if not HAS_DISPLAY:
        print("⚠ No display to clear")
        return
    
    try:
        epd = EPD()
        epd.init()
        epd.Clear()
        epd.sleep()
        print("✅ Display cleared and sleeping")
    except Exception as e:
        print(f"❌ Error clearing display: {e}")


def input_listener():
    """Listen for airport code input in background"""
    global NEW_AIRPORT, CURRENT_AIRPORT, LAST_DATA
    
    while True:
        try:
            user_input = input().strip().upper()
            if user_input:
                if len(user_input) == 4:
                    CURRENT_AIRPORT = user_input
                    LAST_DATA = None  # Force refresh for new airport
                    print(f"\n✈ Switching to: {CURRENT_AIRPORT}")
                    update()
                elif user_input == 'Q' or user_input == 'QUIT':
                    raise KeyboardInterrupt
                else:
                    print(f"⚠ Invalid airport code: {user_input} (should be 4 characters like KGEG)")
        except EOFError:
            break


if __name__ == "__main__":
    # Check for command line argument first
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().upper()
        if len(arg) == 4:
            CURRENT_AIRPORT = arg
    else:
        # Ask for airport
        airport_input = input(f"Enter airport code [{CURRENT_AIRPORT}]: ").strip().upper()
        if airport_input and len(airport_input) == 4:
            CURRENT_AIRPORT = airport_input
    
    print(f"✈ Using airport: {CURRENT_AIRPORT}")
    
    try:
        # Run once
        update()
        
        # Ask about continuous updates
        response = input("\nRun continuous updates every 5 minutes? (y/n): ")
        if response.lower() == 'y':
            print(f"\nRunning continuous updates for {CURRENT_AIRPORT}")
            print("Type a new airport code (e.g., KGEG) to change")
            print("Press Ctrl+C to stop")
            print("-" * 40)
            
            # Start input listener in background
            listener = threading.Thread(target=input_listener, daemon=True)
            listener.start()
            
            while True:
                time.sleep(UPDATE_INTERVAL)
                update()
                
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping...")
    finally:
        clear_display()