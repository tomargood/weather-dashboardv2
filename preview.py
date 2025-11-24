#!/usr/bin/env python3
"""
Preview the weather dashboard on Mac without e-paper display
Generates HTML and PNG, then opens them for viewing
"""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import requests
from datetime import datetime
import subprocess
from PIL import Image, ImageDraw, ImageFont

# Configuration
API_KEY_PATH = Path("API_keys/avwxkeys.txt")
AIRPORT = "KSKA"
HTML_OUTPUT = Path("output/weather.html")
PNG_OUTPUT = Path("output/weather_preview.png")
TEMPLATE_PATH = Path("templates/page.html")

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

def render_html(template_path, weather_data, output_path):
    """Render template to HTML"""
    env = Environment(loader=FileSystemLoader(template_path.parent))
    
    def url_for(endpoint, filename=None, **values):
        if endpoint == 'static' and filename:
            return f'static/{filename}'
        return '#'
    
    env.globals['url_for'] = url_for
    template = env.get_template(template_path.name)
    html_output = template.render(**weather_data)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html_output)
    
    print(f"✓ HTML: {output_path}")

def create_preview_png():
    """Create a PNG screenshot using Chromium - try different window sizes"""
    
    print("\nTaking screenshot with Chromium...")
    
    # Find chromium
    chromium_paths = [
        'chromium',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/opt/homebrew/bin/chromium',
    ]
    
    chromium_cmd = None
    for path in chromium_paths:
        try:
            if path.startswith('/'):
                if Path(path).exists():
                    chromium_cmd = path
                    break
            else:
                result = subprocess.run(['which', path], capture_output=True, text=True)
                if result.returncode == 0:
                    chromium_cmd = path
                    break
        except:
            continue
    
    if not chromium_cmd:
        print("❌ Chromium not found!")
        print("   Install with: brew install chromium")
        return False
    
    print(f"Using: {chromium_cmd}")
    
    # Try different window sizes
    window_sizes = [
        (800, 480, "Exact"),
        (850, 500, "Slightly larger"),
        (900, 600, "Larger"),
        (1000, 700, "Much larger"),
        (1200, 900, "Extra large"),
    ]
    
    for width, height, description in window_sizes:
        print(f"\nTrying {width}x{height} ({description})...")
        
        try:
            result = subprocess.run([
                chromium_cmd,
                '--headless',
                '--disable-gpu',
                '--no-sandbox',
                '--force-device-scale-factor=1',
                '--hide-scrollbars',
                f'--screenshot={PNG_OUTPUT.absolute()}',
                f'file://{HTML_OUTPUT.absolute()}'
            ], capture_output=True, timeout=30)
            
            if PNG_OUTPUT.exists():
                from PIL import Image, ImageDraw, ImageFont
                img = Image.open(PNG_OUTPUT)
                print(f"  Captured: {img.size[0]}x{img.size[1]}")
                
                # Check if close to target
                if img.size[0] >= 750 and img.size[1] >= 450:
                    print(f"  ✓ Good size! Using {width}x{height}")
                    
                    # Resize to exact 800x480
                    if img.size != (DISPLAY_WIDTH, DISPLAY_HEIGHT):
                        img = img.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.Resampling.LANCZOS)
                        print(f"  Resized to: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
                    
                    # Add border
                    draw = ImageDraw.Draw(img)
                    draw.rectangle([0, 0, DISPLAY_WIDTH-1, DISPLAY_HEIGHT-1], outline='red', width=3)
                    
                    try:
                        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
                    except:
                        font = ImageFont.load_default()
                    
                    draw.text((10, 10), f"{DISPLAY_WIDTH}x{DISPLAY_HEIGHT}", fill='red', font=font)
                    draw.text((10, DISPLAY_HEIGHT-25), f"Window: {width}x{height}", fill='red', font=font)
                    
                    img.save(PNG_OUTPUT)
                    print(f"✓ Preview PNG saved: {PNG_OUTPUT}")
                    return True
                else:
                    print(f"  ✗ Too small, trying larger...")
                    
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print("\n❌ Could not capture good screenshot with any window size")
    return False

def main():
    print("Weather Dashboard Preview")
    print("=" * 60)
    
    try:
        token = API_KEY_PATH.read_text().strip()
        
        print(f"\nFetching weather for {AIRPORT}...")
        weather_data = get_weather_data(AIRPORT, token)
        if not weather_data:
            print("❌ Failed to fetch weather data")
            return
        
        print("Rendering HTML...")
        copy_static_files()
        render_html(TEMPLATE_PATH, weather_data, HTML_OUTPUT)
        
        print("Creating preview PNG...")
        png_created = create_preview_png()
        
        print("\n" + "=" * 60)
        print("✅ Preview generated!")
        print(f"HTML: {HTML_OUTPUT}")
        if png_created:
            print(f"PNG:  {PNG_OUTPUT}")
        
        # Open in browser
        print("\nOpening preview in browser...")
        subprocess.run(['open', str(HTML_OUTPUT)])
        
        if png_created:
            print("Opening PNG...")
            subprocess.run(['open', str(PNG_OUTPUT)])
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()