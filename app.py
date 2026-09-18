import flask

app = flask.Flask(__name__)


@app.route("/")
def index():
    return "Hello from a fresh production Juju Demo! 🚀"


if __name__ == "__main__":
    app.run()
