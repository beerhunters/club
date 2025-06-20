from flask import Blueprint, session, render_template, redirect, url_for

main_blueprint = Blueprint("main", __name__)


@main_blueprint.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("auth.login"))
    return render_template("index.html", user=session["user"])
