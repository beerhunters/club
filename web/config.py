import os


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET", "dev")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
    SESSION_TYPE = "filesystem"
    SESSION_FILE_DIR = "/app/flask_session"
