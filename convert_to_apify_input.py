#!/usr/bin/env python3
"""
Helper script to convert Instagram URLs file to Apify actor input format.
"""

import json
import sys
import os

def convert_urls_to_apify_input(urls_file, output_file=None):
    """
    Convert a text file with one URL per line to Apify input JSON format.
    """
    if not os.path.exists(urls_file):
        print(f"❌ Error: File not found: {urls_file}")
        return
    
    # Read URLs
    urls = []
    with open(urls_file, 'r') as f:
        for line in f:
            url = line.strip()
            if url and url.startswith('http'):
                urls.append(url)
    
    if not urls:
        print("❌ No valid URLs found in file")
        return
    
    # Create Apify input format
    apify_input = {
        "urls": urls,
        "delay_min": 2,
        "delay_max": 4,
        "max_follows": 40,
        "headless": False
    }
    
    # Save to file
    if not output_file:
        output_file = urls_file.replace('.txt', '_apify_input.json')
    
    with open(output_file, 'w') as f:
        json.dump(apify_input, f, indent=2)
    
    print(f"✅ Converted {len(urls)} URLs to Apify input format")
    print(f"📄 Saved to: {output_file}")
    print(f"\n⚠️  Remember to add your Instagram credentials:")
    print(f"   - instagram_username")
    print(f"   - instagram_password")
    print(f"\nYou can edit the JSON file or add them in Apify Console.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_to_apify_input.py <urls_file.txt> [output.json]")
        print("\nExample:")
        print("  python convert_to_apify_input.py instagram_urls_1767793973.txt")
        sys.exit(1)
    
    urls_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_urls_to_apify_input(urls_file, output_file)
