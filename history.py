from datetime import datetime

history_log = []

def log_action(user_id, action):
    history_log.append({
        "user": user_id,
        "action": action,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

def get_history():
    return history_log
