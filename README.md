# Real-Time Chatroom (Flask + WebSockets)

## What it does
1. Open the site → redirected to **Login**.
2. No account? Click **Sign up** → enter username, password, confirm password (show/hide toggle available).
3. Log in with username/password.
4. You land on **Create Chatroom** → enter a room name and max number of members → click **Create**.
5. You're taken into the chatroom, with a **share link** to invite others (up to the member limit).
6. Anyone opening that link is sent to login/signup first, then dropped straight into the room.
7. Messages appear instantly for everyone in the room via WebSockets, with join/leave notifications, online-user list, and a typing indicator.

## Run locally
```bash
python3 -m venv venv
source venv/bin/activate          # on Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Visit http://localhost:5000

## Deploy on Render
1. Push this folder to a GitHub repo.
2. On Render: **New → Web Service**, connect the repo.
3. Render will detect `render.yaml` automatically (or set manually):
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn --worker-class eventlet -w 1 app:app`
4. Add an environment variable `SECRET_KEY` (Render's blueprint auto-generates one).
5. Deploy. Render gives you a URL like `https://your-app.onrender.com` — that's the link people open to log in, sign up, create rooms, and join via share links.

## Notes / where to extend
- Passwords are hashed with Werkzeug's `generate_password_hash` (PBKDF2). Swap in `flask-bcrypt` if you specifically need bcrypt.
- Storage is SQLite by default (`chatroom.db`), auto-created on first run. Set `DATABASE_URL` to point at Postgres in production (Render Postgres works out of the box with `postgresql://...`).
- Presence (online users) is tracked in memory, so it resets if the app restarts and won't sync across multiple server instances — fine for one Render instance (`-w 1`), but for true horizontal scaling you'd move presence into Redis and use `flask_socketio`'s `message_queue` option.
- Direct/private messaging, admin moderation, and file uploads from the original spec aren't built yet — the current app covers auth, room creation with share links, member limits, real-time group chat, message history, and presence. Happy to add any of those next.
