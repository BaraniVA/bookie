import sqlite3
from datetime import datetime

def generate_html():
    with sqlite3.connect("appointments.db") as conn:
        rows = conn.execute("SELECT username, email, datetime FROM appointments ORDER BY datetime").fetchall()

    html = """
    <html><head><title>Appointments</title></head><body>
    <h2>📅 Appointment Dashboard</h2>
    <table border="1" cellpadding="6">
    <tr><th>Username</th><th>Email</th><th>Date & Time</th></tr>
    """

    for username, email, dt in rows:
        html += f"<tr><td>{username}</td><td>{email}</td><td>{datetime.fromisoformat(dt).strftime('%Y-%m-%d %H:%M')}</td></tr>"

    html += "</table></body></html>"

    with open("appointments.html", "w") as f:
        f.write(html)

    print("✅ appointments.html generated")

if __name__ == "__main__":
    generate_html()
