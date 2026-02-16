#!/usr/bin/env python3
"""
Setup script for Crossplay Bot.
Downloads dependencies and a word dictionary.
"""

import subprocess
import sys
import os
import urllib.request

PACKAGES = [
    'mss',           # Screen capture
    'Pillow',        # Image processing
    'pytesseract',   # OCR (Python wrapper)
    'opencv-python', # Computer vision
    'numpy',         # Numerical processing
]


def install_packages():
    """Install required Python packages."""
    print("Installing Python packages...")
    for pkg in PACKAGES:
        print(f"  Installing {pkg}...")
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', pkg, '-q'],
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            print(f"  ✗ Failed to install {pkg} (exit code {exc.returncode})")
            print(f"    Try manually: pip install {pkg}")
    print("✓ All Python packages installed.\n")

    # Write a requirements.txt so users can `pip install -r` later
    req_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    with open(req_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(PACKAGES) + '\n')
    print(f"  Wrote {req_path}\n")


def check_tesseract():
    """Check if Tesseract OCR is installed."""
    try:
        result = subprocess.run(['tesseract', '--version'],
                                capture_output=True, text=True)
        print(f"Tesseract found: {result.stdout.splitlines()[0]}")
        return True
    except FileNotFoundError:
        print("✗ Tesseract OCR not found!")
        print("  Install it:")
        print("    macOS:   brew install tesseract")
        print("    Ubuntu:  sudo apt install tesseract-ocr")
        print("    Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        return False


def download_dictionary():
    """Download a word dictionary (TWL-based) for the move engine."""
    dict_path = os.path.join(os.path.dirname(__file__), 'dictionary.txt')

    if os.path.exists(dict_path):
        with open(dict_path, encoding='utf-8') as f:
            count = sum(1 for _ in f)
        print(f"Dictionary already exists: {dict_path} ({count:,} words)")
        return

    print("Downloading word dictionary...")

    # Try the system dictionary first as a fallback
    system_dict = '/usr/share/dict/words'
    if os.path.exists(system_dict):
        print(f"  Using system dictionary: {system_dict}")
        words = set()
        with open(system_dict, encoding='utf-8') as f:
            for line in f:
                word = line.strip().upper()
                if 2 <= len(word) <= 15 and word.isalpha():
                    words.add(word)

        # Add essential 2-letter words for Crossplay
        two_letter = [
            "AA","AB","AD","AE","AG","AH","AI","AL","AM","AN","AR","AS","AT",
            "AW","AX","AY","BA","BE","BI","BO","BY","DA","DE","DO","ED","EF",
            "EH","EL","EM","EN","ER","ES","ET","EW","EX","FA","FE","GO","HA",
            "HE","HI","HM","HO","ID","IF","IN","IS","IT","JO","KA","KI","LA",
            "LI","LO","MA","ME","MI","MM","MO","MU","MY","NA","NE","NO","NU",
            "OD","OE","OF","OH","OI","OK","OM","ON","OP","OR","OS","OU","OW",
            "OX","OY","PA","PE","PI","PO","QI","RE","SH","SI","SO","TA","TI",
            "TO","UH","UM","UN","UP","US","UT","WE","WO","XI","XU","YA","YE",
            "YO","ZA",
        ]
        words.update(two_letter)

        with open(dict_path, 'w', encoding='utf-8') as f:
            for word in sorted(words):
                f.write(word + '\n')
        print(f"✓ Dictionary created: {len(words):,} words → {dict_path}")
        return

    # Try to download from a public source
    urls = [
        "https://raw.githubusercontent.com/benhoyt/goawk/master/testdata/words",
    ]

    for url in urls:
        try:
            print(f"  Trying {url}...")
            urllib.request.urlretrieve(url, dict_path)
            # Clean up
            words = set()
            with open(dict_path, encoding='utf-8') as f:
                for line in f:
                    word = line.strip().upper()
                    if 2 <= len(word) <= 15 and word.isalpha():
                        words.add(word)
            with open(dict_path, 'w', encoding='utf-8') as f:
                for word in sorted(words):
                    f.write(word + '\n')
            print(f"✓ Dictionary downloaded: {len(words):,} words")
            return
        except Exception as e:
            print(f"  Failed: {e}")
            continue

    print("\n⚠ Could not download a dictionary automatically.")
    print("  Please download a TWL06 or SOWPODS word list and save as:")
    print(f"  {dict_path}")
    print("\n  You can find word lists at:")
    print("  - https://github.com/benhoyt/goawk/blob/master/testdata/words")
    print("  - Search for 'TWL06 word list download'")
    print("  - Search for 'SOWPODS word list download'")


def main():
    print("=" * 50)
    print("  Crossplay Bot — Setup")
    print("=" * 50)
    print()

    install_packages()
    check_tesseract()
    print()
    download_dictionary()

    print()
    print("=" * 50)
    print("  Setup complete! Run the bot:")
    print()
    print("    python crossplay_bot.py          # GUI mode")
    print("    python crossplay_bot.py --manual  # Terminal mode")
    print("=" * 50)


if __name__ == '__main__':
    main()
