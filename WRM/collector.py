import psutil
import sys

DISK_PATH = "C:\\" if sys.platform == "win32" else "/"

def collect_data():
    return {
        "cpu":  psutil.cpu_percent(),
        "ram":  psutil.virtual_memory().percent,
        "disk": psutil.disk_usage(DISK_PATH).percent,
    }
