import flask

app = flask.Flask(__name__)


@app.route("/")
def index():
    return "Hello from the demos controller preview! 🚀"


if __name__ == "__main__":
    app.run()
