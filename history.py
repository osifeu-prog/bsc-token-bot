history_log = []

def log_action(user_id, action):
    history_log.append({
        "user": user_id,
        "action": action,
        "timestamp": str(datetime.utcnow())
    })

def get_history():
    return history_log
