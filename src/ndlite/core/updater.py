from PyQt6.QtWidgets import QMessageBox
import urllib.request
import json
import webbrowser
import ssl
import certifi

GLOBAL_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

VERSION = "0.6.1"

class Updater:
    def __init__(self, main_window):
        self.main_window = main_window
        self.version = VERSION
        self.repo = "21tesla/ndlite"

    def _get_latest_release(self):
        """Helper to fetch latest release info from GitHub."""
        url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        req = urllib.request.Request(url, headers={'User-Agent': 'ndlite-App'})
        with urllib.request.urlopen(req, context=GLOBAL_SSL_CONTEXT, timeout=3) as response:
            data = json.loads(response.read().decode())
            return {
                'version': data['tag_name'].lstrip('v'),
                'url': data['html_url']
            }

    def _prompt_update(self, latest_version, release_url):
        """Prompts the user to update."""
        reply = QMessageBox.question(
            self.main_window, 
            "Update Available",
            f"A new version of ndlite ({latest_version}) is available!\n"
            f"You are currently running version {self.version}.\n\n"
            f"Would you like to open your browser to download it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open(release_url)

    def silent_update_check(self):
        """Check for updates without bothering the user unless one is found."""
        try:
            release = self._get_latest_release()
            if self.parse_version(release['version']) > self.parse_version(self.version):
                self._prompt_update(release['version'], release['url'])
        except Exception:
            pass 

    def check_for_updates(self):
        """Manual check for updates with feedback."""
        try:
            release = self._get_latest_release()
            if self.parse_version(release['version']) > self.parse_version(self.version):
                self._prompt_update(release['version'], release['url'])
            else:
                QMessageBox.information(
                    self.main_window, 
                    "Up to Date", 
                    f"You are running the latest version ({self.version})."
                )
        except Exception as e:
            QMessageBox.warning(
                self.main_window, 
                "Update Check Failed", 
                f"Could not check GitHub for updates.\nError: {e}"
            )

    def parse_version(self, v_string):
        """Parses version string into a tuple of integers for comparison."""
        try:
            return tuple(map(int, (v_string.split("."))))
        except (ValueError, AttributeError):
            return (0, 0, 0)
