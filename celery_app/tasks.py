from celery_app import celery_app


@celery_app.task
def send_notification(user_id: int, message: str):
    print(f"Notify user {user_id}: {message}")
