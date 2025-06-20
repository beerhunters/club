from flask import Blueprint, request, session, redirect, url_for, render_template
from web.config import Config

auth_blueprint = Blueprint("auth", __name__)


@auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (
            request.form["username"] == Config.ADMIN_USERNAME
            and request.form["password"] == Config.ADMIN_PASSWORD
        ):
            session["user"] = request.form["username"]
            return redirect(url_for("main.index"))
        return render_template("login.html", error="Неверные данные")
    return render_template("login.html")


@auth_blueprint.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("auth.login"))
