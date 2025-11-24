#!/usr/bin/env python3
"""
Test script to verify e-paper display is working correctly
Creates a test pattern image with dimensions and border
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

try:
    from waveshare_epd.epd7in3f import EPD
    EPAPER_AVAILABLE = True
except:
    EPAPER_AVAILABLE = False
    print("⚠ E-paper not available, will just create test image")

# Create test image
img = Image.new('RGB', (800, 480), 'white')
draw = ImageDraw.Draw(img)

# Draw border around entire image
draw.rectangle([0, 0, 799, 479], outline='black', width=5)

# Draw grid lines every 100 pixels
for x in range(0, 800, 100):
    draw.line([(x, 0), (x, 480)], fill='lightgray', width=1)
for y in range(0, 480, 100):
    draw.line([(0, y), (800, y)], fill='lightgray', width=1)

# Draw corner markers
corners = [
    (10, 10, "TOP LEFT"),
    (790, 10, "TOP RIGHT"),
    (10, 470, "BOTTOM LEFT"),
    (790, 470, "BOTTOM RIGHT")
]

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
except:
    font = ImageFont.load_default()

for x, y, text in corners:
    draw.text((x, y), text, fill='black', font=font, anchor='mm')

# Draw center crosshair
draw.line([(400, 0), (400, 480)], fill='red', width=2)
draw.line([(0, 240), (800, 240)], fill='red', width=2)
draw.text((400, 240), "CENTER\n800x480", fill='red', font=font, anchor='mm', align='center')

# Save test image
output_dir = Path("output")
output_dir.mkdir(exist_ok=True)
test_path = output_dir / "test_pattern.png"
img.save(test_path)
print(f"✓ Test pattern saved: {test_path}")

# Display on e-paper if available
if EPAPER_AVAILABLE:
    try:
        print("Displaying test pattern on e-paper...")
        epd = EPD()
        epd.init()
        epd.display(epd.getbuffer(img))
        epd.sleep()
        print("✓ Test pattern displayed!")
    except Exception as e:
        print(f"❌ E-paper error: {e}")
else:
    print("Open output/test_pattern.png to verify dimensions")