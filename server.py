from flask import Flask, request, jsonify
import hashlib

app = Flask(__name__)

SECRET = "my_secret_salt_2026"

# 仮DB（本番はDBにする）
valid_users = {
    # pc_id: key
}

def generate_key(pc_id):
    raw = SECRET + pc_id
    return hashlib.sha256(raw.encode()).hexdigest()


@app.route("/verify", methods=["POST"])
def verify():
    data = request.json

    pc_id = data.get("pc_id")
    key = data.get("key")

    if not pc_id or not key:
        return jsonify({"status": "error"}), 400

    valid_key = generate_key(pc_id)

    if key == valid_key:
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "ng"})


if __name__ == "__main__":
    app.run(port=5000)