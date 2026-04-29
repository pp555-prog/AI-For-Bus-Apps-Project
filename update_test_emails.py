"""Set the first DJ and first venue's emails to a real address for end-to-end testing."""
import sqlite3

EMAIL = "pabloplazaro@gmail.com"

c = sqlite3.connect("nocturne.db")

dj_count = c.execute("SELECT COUNT(*) FROM djs").fetchone()[0]
venue_count = c.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
print(f"Found {dj_count} DJs and {venue_count} venues in the database.")

if dj_count == 0 or venue_count == 0:
    print("DB is empty. Stop the backend, delete nocturne.db, and start the backend again to re-seed.")
    c.close()
    raise SystemExit(1)

dj_id = c.execute("SELECT id FROM djs ORDER BY id LIMIT 1").fetchone()[0]
venue_id = c.execute("SELECT id FROM venues ORDER BY id LIMIT 1").fetchone()[0]

c.execute("UPDATE djs SET email = ? WHERE id = ?", (EMAIL, dj_id))
c.execute("UPDATE venues SET email = ? WHERE id = ?", (EMAIL, venue_id))
c.commit()

dj = c.execute("SELECT id, name, email FROM djs WHERE id = ?", (dj_id,)).fetchone()
venue = c.execute("SELECT id, name, email FROM venues WHERE id = ?", (venue_id,)).fetchone()
c.close()

print(f"DJ:    {dj}")
print(f"Venue: {venue}")
print(f"\nUse these IDs in your booking POST: dj_id={dj_id}, venue_id={venue_id}")
