#!/usr/bin/env python3
"""
Quit script - Clear e-paper display and shutdown Pi
"""

import subprocess
import sys

# Try to import e-paper display
try:
    from waveshare_epd.epd7in3f import EPD
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False
    print("⚠ No e-paper display available")

def clear_display():
    """Clear the e-paper display and put it to sleep"""
    if not HAS_DISPLAY:
        print("⚠ No display to clear")
        return
    
    try:
        print("Clearing e-paper display...")
        epd = EPD()
        epd.init()
        epd.Clear()
        epd.sleep()
        print("✅ Display cleared and sleeping")
    except Exception as e:
        print(f"❌ Error clearing display: {e}")

def shutdown():
    """Shutdown the Pi"""
    try:
        print("🔌 Shutting down Pi...")
        subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error shutting down: {e}")
        print("You may need to run this script with sudo or add your user to sudoers")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("Weather Dashboard Quit Script")
    print("=" * 60)
    
    # Clear the display
    clear_display()
    
    # Shutdown the Pi
    shutdown()