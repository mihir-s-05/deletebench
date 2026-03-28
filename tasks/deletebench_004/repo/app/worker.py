from app.notifications import available_channels

def queued_jobs() -> list[str]:
    jobs = []
    if "email" in available_channels():
        jobs.append("email_notifications")
    if "in_app" in available_channels():
        jobs.append("in_app_notifications")
    return jobs
