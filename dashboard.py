import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from config import DB_PATH


def get_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM applications ORDER BY fit_score DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/api/jobs":
            data = get_data()
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            with open("dashboard.html", "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    print("Dashboard running at http://localhost:8765")
    print("Press Ctrl+C to stop.")
    HTTPServer(("", 8765), Handler).serve_forever()
