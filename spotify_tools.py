#!/usr/bin/env python3
"""
Spotify Tools - Main Menu
Access all Spotify utilities from a single interface.
"""

import sys
import os

# Add current directory to path so we can import the utility modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def show_menu():
    """Display the main menu."""
    print("\n" + "=" * 60)
    print("🎵 Spotify Tools")
    print("=" * 60)
    print("\nAvailable utilities:")
    print()
    print("  1. Follow Artists")
    print("     Follow all artists from your liked/saved tracks")
    print()
    print("  2. Find Concerts")
    print("     Find upcoming concerts for artists you follow")
    print()
    print("  3. Randomize Playlists")
    print("     Randomize the order of tracks in all your playlists")
    print()
    print("  4. Find Instagram Accounts")
    print("     Find Instagram accounts for artists you follow")
    print()
    print("  0. Exit")
    print()


def run_follow_artists():
    """Run the follow artists utility."""
    try:
        from follow_artists import main
        main()
    except ImportError as e:
        print(f"❌ Error importing follow_artists: {e}")
    except Exception as e:
        print(f"❌ Error running follow_artists: {e}")


def run_find_concerts():
    """Run the find concerts utility."""
    try:
        from find_concerts import main
        main()
    except ImportError as e:
        print(f"❌ Error importing find_concerts: {e}")
    except Exception as e:
        print(f"❌ Error running find_concerts: {e}")


def run_randomize_playlists():
    """Run the randomize playlists utility."""
    try:
        from randomize_playlists import main
        main()
    except ImportError as e:
        print(f"❌ Error importing randomize_playlists: {e}")
    except Exception as e:
        print(f"❌ Error running randomize_playlists: {e}")


def run_find_instagram_accounts():
    """Run the find Instagram accounts utility."""
    try:
        from find_instagram_accounts import main
        main()
    except ImportError as e:
        print(f"❌ Error importing find_instagram_accounts: {e}")
    except Exception as e:
        print(f"❌ Error running find_instagram_accounts: {e}")


def main():
    """Main menu loop."""
    while True:
        show_menu()
        choice = input("Select an option (0-4): ").strip()
        
        if choice == "0":
            print("\n👋 Goodbye!")
            break
        elif choice == "1":
            run_follow_artists()
        elif choice == "2":
            run_find_concerts()
        elif choice == "3":
            run_randomize_playlists()
        elif choice == "4":
            run_find_instagram_accounts()
        else:
            print("\n❌ Invalid option. Please select 0-4.")
        
        # Ask if user wants to continue
        if choice != "0":
            print("\n" + "-" * 60)
            continue_choice = input("Return to main menu? (y/n): ").strip().lower()
            if continue_choice != "y":
                print("\n👋 Goodbye!")
                break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
