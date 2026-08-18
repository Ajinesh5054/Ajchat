import os
import uuid
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, join_room, leave_room, emit

# ---------------------------------------------------------------------------
# App / extension setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///chatroom.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Room(db.Model):
    id = db.Column(db.String(36), primary_key=True)  # uuid
    name = db.Column(db.String(100), nullable=False)
    max_members = db.Column(db.Integer, nullable=False, default=10)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship("User")


class RoomMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(36), db.ForeignKey("room.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("room_id", "user_id"),)

    user = db.relationship("User")
    room = db.relationship("Room")


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(36), db.ForeignKey("room.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# In-memory presence tracking: { room_id: { sid: username } }
# ---------------------------------------------------------------------------
online_users = {}


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("create_room"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("create_room"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif User.query.filter_by(username=username).first():
            flash("That username is already taken.", "error")
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("create_room"))

    next_url = request.args.get("next")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = request.form.get("next") or next_url

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(next_url or url_for("create_room"))
        flash("Invalid username or password.", "error")

    return render_template("login.html", next=next_url)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Room creation / joining
# ---------------------------------------------------------------------------
@app.route("/create_room", methods=["GET", "POST"])
@login_required
def create_room():
    if request.method == "POST":
        name = request.form.get("room_name", "").strip()
        max_members_raw = request.form.get("max_members", "").strip()

        if not name:
            flash("Please enter a chatroom name.", "error")
        elif not max_members_raw.isdigit() or int(max_members_raw) < 2:
            flash("Max members must be a number of 2 or more.", "error")
        else:
            room = Room(
                id=str(uuid.uuid4()),
                name=name,
                max_members=int(max_members_raw),
                creator_id=current_user.id,
            )
            db.session.add(room)
            db.session.add(RoomMember(room_id=room.id, user_id=current_user.id))
            db.session.commit()
            return redirect(url_for("room", room_id=room.id, created="1"))

    return render_template("create_room.html")


@app.route("/room/<room_id>")
@login_required
def room(room_id):
    room_obj = Room.query.get(room_id)
    if not room_obj:
        flash("That chatroom does not exist.", "error")
        return redirect(url_for("create_room"))

    member = RoomMember.query.filter_by(room_id=room_id, user_id=current_user.id).first()

    if not member:
        current_count = RoomMember.query.filter_by(room_id=room_id).count()
        if current_count >= room_obj.max_members:
            flash("This chatroom is full.", "error")
            return redirect(url_for("create_room"))
        db.session.add(RoomMember(room_id=room_id, user_id=current_user.id))
        db.session.commit()

    history = (
        Message.query.filter_by(room_id=room_id)
        .order_by(Message.timestamp.asc())
        .limit(200)
        .all()
    )
    member_count = RoomMember.query.filter_by(room_id=room_id).count()
    share_link = request.host_url.rstrip("/") + url_for("room", room_id=room_id)

    return render_template(
        "chatroom.html",
        room=room_obj,
        history=history,
        member_count=member_count,
        share_link=share_link,
        just_created=request.args.get("created") == "1",
    )


# ---------------------------------------------------------------------------
# Socket.IO events
# ---------------------------------------------------------------------------
@socketio.on("join")
def handle_join(data):
    room_id = data["room_id"]
    username = current_user.username if current_user.is_authenticated else "Guest"

    join_room(room_id)
    online_users.setdefault(room_id, {})[request.sid] = username

    emit(
        "system_message",
        {"text": f"{username} joined the chatroom.", "timestamp": _now()},
        room=room_id,
    )
    emit(
        "presence_update",
        {"users": list(online_users.get(room_id, {}).values())},
        room=room_id,
    )


@socketio.on("leave")
def handle_leave(data):
    room_id = data["room_id"]
    username = current_user.username if current_user.is_authenticated else "Guest"

    leave_room(room_id)
    if room_id in online_users:
        online_users[room_id].pop(request.sid, None)

    emit(
        "system_message",
        {"text": f"{username} left the chatroom.", "timestamp": _now()},
        room=room_id,
    )
    emit(
        "presence_update",
        {"users": list(online_users.get(room_id, {}).values())},
        room=room_id,
    )


@socketio.on("disconnect")
def handle_disconnect():
    for room_id, users in list(online_users.items()):
        if request.sid in users:
            username = users.pop(request.sid)
            emit(
                "system_message",
                {"text": f"{username} disconnected.", "timestamp": _now()},
                room=room_id,
            )
            emit(
                "presence_update",
                {"users": list(users.values())},
                room=room_id,
            )


@socketio.on("send_message")
def handle_send_message(data):
    room_id = data["room_id"]
    content = (data.get("content") or "").strip()
    if not content or not current_user.is_authenticated:
        return

    msg = Message(room_id=room_id, user_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()

    emit(
        "new_message",
        {
            "username": current_user.username,
            "content": content,
            "timestamp": _now(),
        },
        room=room_id,
    )


@socketio.on("typing")
def handle_typing(data):
    room_id = data["room_id"]
    username = current_user.username if current_user.is_authenticated else "Guest"
    emit("user_typing", {"username": username}, room=room_id, include_self=False)


def _now():
    return datetime.utcnow().strftime("%H:%M")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
