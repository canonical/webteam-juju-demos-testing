import flask

app = flask.Flask(__name__)


@app.route("/")
def index():
    return "This is another deployed Juju Demo! 🚀"


if __name__ == "__main__":
    app.run()
