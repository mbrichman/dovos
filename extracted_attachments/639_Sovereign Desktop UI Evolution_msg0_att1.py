#!/usr/bin/env python3
"""
Simple HTTP Server for Sovereign Desktop
Includes basic CORS handling for local development
"""

import http.server
import socketserver
import argparse
import os
import sys
from pathlib import Path

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Auth-Token')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def main():
    parser = argparse.ArgumentParser(description='Sovereign Desktop HTTP Server')
    parser.add_argument('--port', '-p', type=int, default=8080, help='Port number (default: 8080)')
    parser.add_argument('--host', default='localhost', help='Host address (default: localhost)')
    args = parser.parse_args()

    # Change to the directory containing this script
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    try:
        with socketserver.TCPServer((args.host, args.port), CORSRequestHandler) as httpd:
            print(f"ðŸš€ Sovereign Desktop server running at:")
            print(f"   http://{args.host}:{args.port}")
            print(f"   Serving from: {script_dir}")
            print(f"   Press Ctrl+C to stop")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nðŸ‘‹ Server stopped by user")
        sys.exit(0)
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"âŒ Port {args.port} is already in use.")
            print(f"   Try a different port: python3 server.py --port 3000")
        else:
            print(f"âŒ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()