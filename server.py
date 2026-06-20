from flask import Flask, request, jsonify
import hashlib
import os
import json
import time

try:
    import redis
except Exception:
    redis = None


app = Flask(__name__)

SECRET = os.getenv("LICENSE_SECRET", "my_secret_salt_2026")
ADMIN_KEY = os.getenv("CLOUD_DICTIONARY_API_KEY", "")

REDIS_URL = os.getenv("REDIS_URL", "")
LOCAL_DB = "cloud_dictionary.json"

r = None
if redis and REDIS_URL:
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
    except Exception:
        r = None


def generate_key(pc_id):
    raw = SECRET + pc_id
    return hashlib.sha256(raw.encode()).hexdigest()


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "ok": True,
        "service": "MCAddon Translator License + Cloud Dictionary"
    })


@app.route("/verify", methods=["POST"])
def verify():
    data = request.json or {}

    pc_id = data.get("pc_id")
    key = data.get("key")

    if not pc_id or not key:
        return jsonify({"status": "error"}), 400

    valid_key = generate_key(pc_id)

    if key == valid_key:
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "ng"})


def load_local_dict():
    if not os.path.exists(LOCAL_DB):
        return {}

    try:
        with open(LOCAL_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_local_dict(data):
    with open(LOCAL_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def dict_key(source):
    return "dict:" + hashlib.sha256(source.encode("utf-8")).hexdigest()


@app.route("/lookup", methods=["POST"])
def lookup():
    data = request.json or {}
    source = str(data.get("source", "")).strip()

    if not source:
        return jsonify({"found": False, "translated": None})

    if r:
        translated = r.get(dict_key(source))
        if translated:
            return jsonify({"found": True, "translated": translated})

    local = load_local_dict()
    translated = local.get(source)

    if translated:
        return jsonify({"found": True, "translated": translated})

    return jsonify({"found": False, "translated": None})


@app.route("/add", methods=["POST"])
def add_dictionary():
    if ADMIN_KEY:
        key = request.headers.get("X-API-Key", "")
        if key != ADMIN_KEY:
            return jsonify({"ok": False, "reason": "invalid api key"}), 401

    data = request.json or {}

    source = str(data.get("source", "")).strip()
    translated = str(data.get("translated", "")).strip()

    if not source or not translated:
        return jsonify({"ok": False, "reason": "empty value"}), 400

    if len(source) > 5000 or len(translated) > 5000:
        return jsonify({"ok": False, "reason": "too long"}), 400

    if r:
        r.set(dict_key(source), translated)
        r.zincrby("dict:ranking", 1, source)
        r.hset("dict:updated_at", source, str(int(time.time())))
    else:
        local = load_local_dict()
        local[source] = translated
        save_local_dict(local)

    return jsonify({"ok": True})


@app.route("/stats", methods=["GET"])
def stats():
    if r:
        total = len(r.keys("dict:*")) - 2
        top = r.zrevrange("dict:ranking", 0, 19, withscores=True)

        return jsonify({
            "total": max(total, 0),
            "top": [
                {"source": item[0], "count": int(item[1])}
                for item in top
            ]
        })

    local = load_local_dict()

    return jsonify({
        "total": len(local),
        "top": []
    })


@app.route("/export", methods=["GET"])
def export():
    if ADMIN_KEY:
        key = request.headers.get("X-API-Key", "")
        if key != ADMIN_KEY:
            return jsonify({"ok": False, "reason": "invalid api key"}), 401

    if r:
        data = {}
        for key in r.keys("dict:*"):
            if key in ["dict:ranking", "dict:updated_at"]:
                continue
            data[key] = r.get(key)
        return jsonify(data)

    return jsonify(load_local_dict())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
