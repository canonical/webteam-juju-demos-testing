import flask

app = flask.Flask(__name__)


@app.route("/")
def index():
    return "Hello from a deployed Juju Demo! 🚀 Production E2E 2026-09-18"


if __name__ == "__main__":
    app.run()
