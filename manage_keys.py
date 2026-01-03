#!/usr/bin/env python3
"""
API Key Management Script
Add, remove, or list API keys for rotation
"""

import sys
import json
from pathlib import Path
import argparse
from src.api_key_manager import APIKeyManager, KeyStatus
from config.settings import config

def main():
    parser = argparse.ArgumentParser(description="Manage API keys for Gemini OCR")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # List keys
    list_parser = subparsers.add_parser('list', help='List all API keys')
    
    # Add key
    add_parser = subparsers.add_parser('add', help='Add a new API key')
    add_parser.add_argument('key', help='API key value')
    add_parser.add_argument('--alias', help='Alias for the key', default=None)
    
    # Remove key
    remove_parser = subparsers.add_parser('remove', help='Remove an API key')
    remove_parser.add_argument('alias', help='Alias of the key to remove')
    
    # Stats
    stats_parser = subparsers.add_parser('stats', help='Show key statistics')
    
    # Reset key
    reset_parser = subparsers.add_parser('reset', help='Reset key status')
    reset_parser.add_argument('alias', help='Alias of the key to reset')
    
    # Test keys
    test_parser = subparsers.add_parser('test', help='Test all API keys')
    
    args = parser.parse_args()
    
    key_manager = APIKeyManager(config)
    
    if args.command == 'list':
        print("Available API Keys:")
        print("=" * 60)
        for i, key in enumerate(key_manager.keys):
            stats = key.get_stats()
            print(f"{i+1}. Alias: {stats['alias']}")
            print(f"   Status: {stats['status']}")
            print(f"   Requests: {stats['total_requests']} "
                  f"(Today: {stats['daily_requests']})")
            print(f"   Success Rate: {stats['success_rate']:.1f}%")
            print(f"   Active: {stats['is_active']}")
            print()
    
    elif args.command == 'add':
        success = key_manager.add_key(args.key, args.alias)
        if success:
            print(f"✓ Key added successfully")
        else:
            print("✗ Failed to add key")
    
    elif args.command == 'remove':
        success = key_manager.remove_key(args.alias)
        if success:
            print(f"✓ Key '{args.alias}' removed successfully")
        else:
            print(f"✗ Key '{args.alias}' not found")
    
    elif args.command == 'stats':
        stats = key_manager.monitor_keys()
        print("API Key Statistics:")
        print("=" * 60)
        print(f"Total Keys: {stats['total_keys']}")
        print(f"Active Keys: {stats['active_keys']}")
        print(f"Rate Limited Keys: {stats['rate_limited_keys']}")
        print(f"Total Requests Today: {stats['total_requests_today']}")
        print()
        
        for key_stat in stats['keys']:
            print(f"Key: {key_stat['alias']}")
            print(f"  Status: {key_stat['status']}")
            print(f"  Requests: {key_stat['total_requests']} "
                  f"(Today: {key_stat['daily_requests']})")
            print(f"  Success: {key_stat['success_rate']:.1f}%")
            print(f"  Rate Limits: {key_stat['rate_limit_hits']}")
            print()
    
    elif args.command == 'reset':
        for key in key_manager.keys:
            if key.alias == args.alias:
                key.status = KeyStatus.ACTIVE
                key.cooldown_until = None
                key.error_count = 0
                print(f"✓ Key '{args.alias}' reset to active status")
                break
        else:
            print(f"✗ Key '{args.alias}' not found")
    
    elif args.command == 'test':
        import google.generativeai as genai
        
        print("Testing API Keys:")
        print("=" * 60)
        
        for key in key_manager.keys:
            print(f"\nTesting key: {key.alias}")
            try:
                genai.configure(api_key=key.key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content("Hello")
                
                if response.text:
                    print(f"  ✓ Working")
                    key.status = KeyStatus.ACTIVE
                else:
                    print(f"  ✗ No response")
                    key.status = KeyStatus.ERROR
            except Exception as e:
                print(f"  ✗ Error: {str(e)[:50]}...")
                key.status = KeyStatus.ERROR
        
        print("\nTest completed!")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    sys.exit(main())