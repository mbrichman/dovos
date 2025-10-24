#!/usr/bin/env python3
"""
Simple HTTP Server for Sovereign Desktop
Includes basic CORS handling for local development and iManage API proxy
"""

import http.server
import socketserver
import argparse
import os
import sys
import json
import urllib.request
import urllib.parse
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

    def do_GET(self):
        # Handle iManage API proxy
        if self.path.startswith('/api/imanage/'):
            self.handle_imanage_proxy()
        else:
            # Serve static files normally
            super().do_GET()

    def handle_imanage_proxy(self):
        try:
            # Extract the API path (remove /api/imanage/ prefix)
            api_path = self.path[13:]  # Remove '/api/imanage/'
            
            # Construct the full iManage API URL
            imanage_url = f"https://im.cloudimanage.com/api/v2/{api_path}"
            
            print(f"Proxying request to: {imanage_url}")
            
            # Create the request with proper headers
            req = urllib.request.Request(
                imanage_url,
                headers={
                    'X-Auth-Token': 'FC4qmQ9bkcmapxxwAvpws_jrnUplCrubFi_BtGRLNuU',
                    'Content-Type': 'application/json',
                    'User-Agent': 'Sovereign-Desktop/1.0'
                }
            )
            
            # Make the request
            with urllib.request.urlopen(req) as response:
                response_data = response.read()
                
                # Send successful response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(response_data)
                
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code} - {e.reason}")
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = json.dumps({
                "error": f"HTTP {e.code}: {e.reason}"
            }).encode()
            self.wfile.write(error_response)
            
        except Exception as e:
            print(f"Proxy Error: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = json.dumps({
                "error": f"Proxy error: {str(e)}"
            }).encode()
            self.wfile.write(error_response)

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
            print(f"   iManage API proxy: /api/imanage/*")
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