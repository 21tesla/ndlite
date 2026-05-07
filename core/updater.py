from PyQt6.QtWidgets import QMessageBox
import urllib.request
import json
import webbrowser
import ssl
import certifi

GLOBAL_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

class Updater:
    def __init__(self, main_window):
        self.main_window = main_window
        self.version = "0.2.2" # Hardcoded for now, should ideally be imported

    def silent_update_check(self):
        repo = "21tesla/NMRdraw_lite"
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'NMRdraw_lite-App'})
            with urllib.request.urlopen(req, context=GLOBAL_SSL_CONTEXT, timeout=3) as response:
                data = json.loads(response.read().decode())
                latest_version = data['tag_name'].lstrip('v')
                release_url = data['html_url']

            if self.parse_version(latest_version) > self.parse_version(self.version):
                reply = QMessageBox.question(
                    self.main_window, 
                    "Update Available",
                    f"A new version of NMRdraw_lite ({latest_version}) is available!\n"
                    f"You are currently running version {self.version}.\n\n"
                    f"Would you like to open your browser to download it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    webbrowser.open(release_url)
        except Exception:
            pass 

    def check_for_updates(self):
        repo = "21tesla/NMRdraw_lite"
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'NMRdraw_lite-Updater'})
            with urllib.request.urlopen(req, context=GLOBAL_SSL_CONTEXT) as response:
                data = json.loads(response.read().decode())
                latest_version = data['tag_name'].lstrip('v')
                release_url = data['html_url']

            if self.parse_version(latest_version) > self.parse_version(self.version):
                reply = QMessageBox.question(
                    self.main_window, 
                    "Update Available",
                    f"A new version of NMRdraw_lite ({latest_version}) is available!\n"
                    f"You are currently running version {self.version}.\n\n"
                    f"Would you like to open your browser to download it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    webbrowser.open(release_url)
            else:
                QMessageBox.information(self.main_window, "Up to Date", f"You are running the latest version ({self.version}).")
        except Exception as e:
            QMessageBox.warning(self.main_window, "Update Check Failed", f"Could not check GitHub for updates.\nError: {e}")

    def parse_version(self, v_string):
        return tuple(map(int, (v_string.split("."))))
