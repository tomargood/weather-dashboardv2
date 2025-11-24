#!/usr/bin/env python3
"""
Simple screenshot test - try multiple methods
"""

from pathlib import Path
import subprocess
import sys

# Paths
HTML_FILE = Path("output/weather.html")
PNG_FILE = Path("output/test_screenshot.png")

# Check HTML exists
if not HTML_FILE.exists():
    print(f"❌ HTML file not found: {HTML_FILE}")
    print("Run preview_weather.py first to generate the HTML")
    exit(1)

print(f"Taking screenshot of: {HTML_FILE}")
print(f"Output will be: {PNG_FILE}\n")

# Method 1: Try Playwright (install with: uv add playwright; playwright install chromium)
print("="*60)
print("Method 1: Playwright")
print("="*60)
try:
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 800, 'height': 480})
        page.goto(f'file://{HTML_FILE.absolute()}')
        page.screenshot(path=str(PNG_FILE))
        browser.close()
    
    print("✅ SUCCESS with Playwright!")
    
    from PIL import Image
    img = Image.open(PNG_FILE)
    print(f"   Image size: {img.size[0]}x{img.size[1]}")
    subprocess.run(['open', str(PNG_FILE)])
    sys.exit(0)
    
except ImportError:
    print("✗ Playwright not installed")
    print("  Install with: uv add playwright && playwright install chromium")
except Exception as e:
    print(f"✗ Error: {e}")

# Method 2: Try Selenium with Chrome
print("\n" + "="*60)
print("Method 2: Selenium")
print("="*60)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    import time
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--force-device-scale-factor=1')
    options.add_argument('--hide-scrollbars')
    
    driver = webdriver.Chrome(options=options)
    
    # Set window size larger to account for chrome/scrollbars
    # Usually need to add ~16-20px for scrollbars
    driver.set_window_size(820, 900)
    
    driver.get(f'file://{HTML_FILE.absolute()}')
    
    # Wait for page to load
    time.sleep(1)
    
    # Get the body element and screenshot just that
    body = driver.find_element(By.TAG_NAME, 'body')
    body.screenshot(str(PNG_FILE))
    
    # Check actual size
    from PIL import Image
    img = Image.open(PNG_FILE)
    actual_size = img.size
    print(f"   Screenshot size: {actual_size[0]}x{actual_size[1]}")
    
    # Crop/resize to exact 800x480
    if actual_size != (800, 480):
        print(f"   Resizing to 800x480...")
        # Crop from center if larger, resize if smaller
        if actual_size[0] > 800 or actual_size[1] > 480:
            # Crop from top-left corner
            img = img.crop((0, 0, min(800, actual_size[0]), min(480, actual_size[1])))
            if img.size != (800, 480):
                # Resize if still not exact
                img = img.resize((800, 480), Image.Resampling.LANCZOS)
        else:
            img = img.resize((800, 480), Image.Resampling.LANCZOS)
        img.save(PNG_FILE)
        print(f"   Final size: {img.size[0]}x{img.size[1]}")
    
    driver.quit()
    
    print("✅ SUCCESS with Selenium!")
    subprocess.run(['open', str(PNG_FILE)])
    sys.exit(0)
    
except ImportError:
    print("✗ Selenium not installed")
    print("  Install with: uv add selenium")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Method 3: Direct Chrome/Chromium
print("\n" + "="*60)
print("Method 3: Chrome/Chromium Direct")
print("="*60)

browsers = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
]

for browser in browsers:
    if not Path(browser).exists():
        print(f"✗ Not found: {browser}")
        continue
    
    try:
        cmd = [
            browser,
            '--headless',
            '--disable-gpu',
            '--no-sandbox',
            '--window-size=800,480',
            '--force-device-scale-factor=1',
            f'--screenshot={PNG_FILE.absolute()}',
            f'file://{HTML_FILE.absolute()}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if PNG_FILE.exists():
            print(f"✅ SUCCESS with {Path(browser).name}!")
            
            from PIL import Image
            img = Image.open(PNG_FILE)
            print(f"   Image size: {img.size[0]}x{img.size[1]}")
            subprocess.run(['open', str(PNG_FILE)])
            sys.exit(0)
    except Exception as e:
        print(f"✗ Error with {browser}: {e}")

print("\n" + "="*60)
print("❌ All methods failed")
print("="*60)
print("\nRecommended installation:")
print("  uv add playwright")
print("  playwright install chromium")
print("\nPlaywright is the most reliable for HTML screenshots")