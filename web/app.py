from flask import Flask
from web.config import Config
from web.auth import auth_blueprint
from web.views import main_blueprint
from flask_session import Session
import os
from bot.logger import setup_logger

logger = setup_logger("web")

app = Flask(
    __name__, template_folder=os.path.join(os.path.dirname(__file__), "templates")
)
app.config.from_object(Config)
Session(app)

app.register_blueprint(auth_blueprint)
app.register_blueprint(main_blueprint)

logger.info("Flask-приложение запускается")
