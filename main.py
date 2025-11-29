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
import json

# Configuration file
CONFIG_FILE = Path("config.json")

# API Key
API_KEY = Path("API_keys/avwxkeys.txt").read_text().strip()

# Paths
TEMPLATE = Path("templates/page.html")
HTML_OUT = Path("output/weather.html")
PNG_OUT = Path("output/weather.png")

# Cache for last displayed data
LAST_DATA = None
LAST_CONFIG_MTIME = 0

# Try to import e-paper display
try:
    from waveshare_epd.epd7in3f import EPD
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False
    print("⚠ No e-paper display available")

def load_config():
    """Load configuration from JSON file"""
    if not CONFIG_FILE.exists():
        # Create default config
        default_config = {
            "airport": "KSKA",
            "update_interval": 300,
            "auto_update": True
        }
        CONFIG_FILE.write_text(json.dumps(default_config, indent=2))
        return default_config
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def config_changed():
    """Check if config file has been modified"""
    global LAST_CONFIG_MTIME
    
    if not CONFIG_FILE.exists():
        return False
    
    current_mtime = CONFIG_FILE.stat().st_mtime
    if current_mtime != LAST_CONFIG_MTIME:
        LAST_CONFIG_MTIME = current_mtime
        return True
    
    return False

def fetch_weather(airport):
    """Get weather data from AVWX API"""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # Get METAR
    metar = requests.get(f"https://avwx.rest/api/metar/{airport}?remove=true", 
                         headers=headers, timeout=10).json()
    
    # Get Station
    try:
        station = requests.get(f"https://avwx.rest/api/station/{airport}", 
                              headers=headers, timeout=10).json()
        arpt_name = station["name"]
    except:
        arpt_name = airport
    
    # Get TAF
    try:
        taf = requests.get(f"https://avwx.rest/api/taf/{airport}", 
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

def update(airport, force_refresh=False):
    """Full update cycle"""
    global LAST_DATA
    
    print(f"\n{'='*60}")
    print(f"Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {airport}")
    print(f"{'='*60}")
    
    try:
        print("Fetching weather...")
        data = fetch_weather(airport)
        
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

if __name__ == "__main__":
    # Load initial config
    config = load_config()
    current_airport = config["airport"]
    
    # Check for command line argument (overrides config)
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().upper()
        if arg == "--daemon":
            # Daemon mode: run continuously with config file watching
            print(f"🚀 Starting in daemon mode")
            print(f"✈ Initial airport: {current_airport}")
            print(f"📝 Edit config.json to change settings")
            print(f"   Airport will update automatically!")
            print("-" * 60)
            
            # Initialize config mtime
            LAST_CONFIG_MTIME = CONFIG_FILE.stat().st_mtime
            
            # Run initial update
            update(current_airport, force_refresh=True)
            
            try:
                while True:
                    # Reload config
                    config = load_config()
                    
                    # Check if airport changed
                    if config["airport"] != current_airport:
                        print(f"\n✈ Airport changed: {current_airport} → {config['airport']}")
                        current_airport = config["airport"]
                        LAST_DATA = None  # Force refresh
                        update(current_airport, force_refresh=True)
                    else:
                        # Normal update cycle
                        time.sleep(config.get("update_interval", 300))
                        if config.get("auto_update", True):
                            update(current_airport)
                        
            except KeyboardInterrupt:
                print("\n\n🛑 Stopping daemon...")
                clear_display()
        
        elif len(arg) == 4:
            current_airport = arg
            print(f"✈ Using airport from command line: {current_airport}")
            update(current_airport, force_refresh=True)
    
    else:
        # Interactive mode
        airport_input = input(f"Enter airport code [{current_airport}]: ").strip().upper()
        if airport_input and len(airport_input) == 4:
            current_airport = airport_input
        
        print(f"✈ Using airport: {current_airport}")
        
        try:
            # Run once
            update(current_airport, force_refresh=True)
            
            # Ask about continuous updates
            response = input("\nRun continuous updates? (y/n): ")
            if response.lower() == 'y':
                print(f"\n📝 To change airport, edit config.json")
                print("Press Ctrl+C to stop")
                print("-" * 40)
                
                # Initialize config mtime
                LAST_CONFIG_MTIME = CONFIG_FILE.stat().st_mtime
                
                while True:
                    time.sleep(config.get("update_interval", 300))
                    
                    # Check if config changed
                    if config_changed():
                        config = load_config()
                        if config["airport"] != current_airport:
                            print(f"\n✈ Airport changed: {current_airport} → {config['airport']}")
                            current_airport = config["airport"]
                            LAST_DATA = None  # Force refresh
                    
                    if config.get("auto_update", True):
                        update(current_airport)
                    
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping...")
        finally:
            clear_display()