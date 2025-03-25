import http.server
import socketserver
import os

# Set the port
PORT = 8000

# Create a simple handler for serving files
handler = http.server.SimpleHTTPRequestHandler

# Create the server
with socketserver.TCPServer(("", PORT), handler) as httpd:
    print(f"Server started at http://localhost:{PORT}")
    print("To access the website, open this URL in your browser")
    print("Press Ctrl+C to stop the server")
    
    # Serve files from the current directory
    httpd.serve_forever()