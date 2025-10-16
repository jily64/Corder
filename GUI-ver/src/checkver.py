import os
import requests
import zipfile
from bs4 import BeautifulSoup
import flet as ft
import threading
from requests.exceptions import RequestException
from const import *
import json

class UpdateChecker:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "KayoVPN"
        self.page.theme_mode = self.read_settinng("theme")
        self.page.window_resizable = False
        self.update_available = False
        self.latest_version = None
        self.app_latest_version = None
        self.update_window = None
        self.dialog = None
        self.download_dialog = None

    def read_settinng (self , type) :
        default_settings = {"ping": "Tcping", "theme": "dark"}
        if os.path.exists("./setting.json"):
            with open("./setting.json", "r") as file:
                f = file.read()
                if f.strip():
                    try:
                        data = json.loads(f)
                        ping = data.get("ping", default_settings["ping"])
                        theme = data.get("theme", default_settings["theme"])
                    except json.JSONDecodeError:

                        print("Error decoding JSON, using default settings.")
                        ping = default_settings["ping"]
                        theme = default_settings["theme"]
                else:

                    print("File is empty, using default settings.")
                    ping = default_settings["ping"]
                    theme = default_settings["theme"]
                    with open("./setting.json" , "w") as file :
                        data = json.dumps(default_settings , indent=4)
                        file.write(data)
        else:
            print("File not found, using default settings.")
            ping = default_settings["ping"]
            theme = default_settings["theme"]
            with open("./setting.json" , "w") as file :
                data = json.dumps(default_settings , indent=4)
                file.write(data)
        if type == "ping" :
            return ping
        elif type == "theme" :
            if theme == "dark" :
                return ft.ThemeMode.DARK
            elif theme == "light" :
                return ft.ThemeMode.LIGHT

    def check_ver(self):
        try:
            response = requests.get(REPO_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            version_text = soup.find(string=lambda text: text and "Release" in text)
            self.app_latest_version = version_text.split(" ")[2].split("v")[1]
        except requests.RequestException as e:
            print(f"Error fetch repo : {e}")
        if self.app_latest_version != APP_VERSION :
            self.show_app_update_dialog()
    
        try:
            response = requests.get(URL_CHECK, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            version_text = soup.find(string=lambda text: text and "v=" in text)
            
            if version_text:
                self.latest_version = version_text.split("v=")[1].strip()
                print("Latest Version:", self.latest_version)
            else:
                raise ValueError("Version information not found on the page")

            if not os.path.exists(CORE_PATH) or XRAY_VERSION != self.latest_version:
                self.update_available = True
                self.show_core_update_dialog()
            else:
                print("Core is up to date.")
                return

        except RequestException as e:
            print(f"Network error: {e}")
            self.show_error_dialog("Network Error", "Failed to check for updates. Please check your internet connection and try again.")
        except Exception as e:
            print(f"Error checking for updates: {e}")
            self.show_error_dialog("Update Check Failed", f"An error occurred while checking for updates: {str(e)}")

    def show_error_dialog(self, title, message):
        def close_dialog(e):
            self.dialog.open = False
            self.page.update()
            self.close_update_window()

        self.dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("OK", on_click=close_dialog),
            ],
        )
        self.page.dialog = self.dialog
        self.dialog.open = True
        self.page.update()

    def show_core_update_dialog(self):
        self.dialog = ft.AlertDialog(
            title=ft.Text("Update Available" if os.path.exists(CORE_PATH) else "Core Not Installed"),
            content=ft.Text(f"A new core version ({self.latest_version}) is available. Do you want to update?" if os.path.exists(CORE_PATH) else "Core is not installed. Do you want to install it?"),
            actions=[
                ft.TextButton("No", on_click=self.close_dialog),
                ft.TextButton("Yes", on_click=self.start_update),
            ],
        )
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def show_app_update_dialog(self):
        self.dialog = ft.AlertDialog(
            title=ft.Text("Update Available"),
            content=ft.Text(f"A new App version ({self.app_latest_version}) is available. Do you want to update?"),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog),
                ft.TextButton("Update", on_click=self.open_update_site),
            ],
        )
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def open_update_site(self, e) :
        self.page.launch_url(REPO_URL)
        self.close_dialog(None)

    def close_dialog(self, e):
        if self.dialog:
            self.dialog.open = False
            self.page.dialog = None
            self.page.update()
        if self.download_dialog :
            self.download_dialog.open = False
            self.page.dialog = None
            self.page.update()

        self.page.title = "KayoVPN XC"
        self.page.window_resizable = True
        self.page.update()

    def close_update_window(self):
        if self.update_window:
            self.update_window.close()

    def start_update(self, e): 
        self.page.update()

        progress_bar = ft.ProgressBar(width=300)
        status_text = ft.Text("Loading ...", size=16)

        self.download_dialog = ft.AlertDialog(
            title=ft.Text("installing Core", size=20, weight=ft.FontWeight.BOLD),
            content=ft.Container(
            content=ft.Column([
                status_text,
                progress_bar,
            ], spacing=20, alignment=ft.MainAxisAlignment.CENTER),
            padding=20,
            width=400,
        ),
        modal=True
        )

        self.page.overlay.append(self.download_dialog)
        self.download_dialog.open = True
        self.page.update()

        def update_task():
            try:
                self.download_core(status_text, progress_bar)
                self.extract_core(status_text, progress_bar)
                self.finalize_update(status_text)
            except Exception as e:
                status_text.value = f"Error: {str(e)}"
                self.page.update()
                self.show_error_dialog("Update Failed", f"An error occurred during the update: {str(e)}")

        threading.Thread(target=update_task, daemon=True).start()


    def finalize_update(self, status_text):
        try:
            current_version_file = os.path.join(CORE_PATH, "version.txt")
            with open(current_version_file, "w") as file:
                file.write(self.latest_version)
            
            status_text.value = "Update completed successfully!"
            self.page.update()

            if OS_SYS == "linux"  :
                os.chmod("./core/linux/xray", 0o755)
                os.chmod("./core/linux/sing-box", 0o755)

            self.close_dialog(None)

        except Exception as e:
            raise Exception(f"Failed to finalize update: {str(e)}")

    def download_core(self, status_text, progress_bar):
        try:
            response = requests.get(DOWNLOAD_URL, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            block_size = 16 * 1024
            downloaded = 0

            with open(SAVE_PATH, 'wb') as file:
                for data in response.iter_content(block_size):
                    size = file.write(data)
                    downloaded += size
                    if downloaded % (1024 * 1024) == 0 or downloaded == total_size:
                        percent = int(50 * downloaded / total_size) if total_size > 0 else 0
                        progress_bar.value = percent / 100
                        status_text.value = f"Downloading... {percent * 2}%"
                        self.page.update()
        except RequestException as e:
            raise Exception(f"Download failed: {str(e)}")


    def extract_core(self, status_text, progress_bar):
        status_text.value = "Extracting..."
        self.page.update()
        
        try:
            with zipfile.ZipFile(SAVE_PATH, 'r') as zip_ref:
                zip_ref.extractall(ROOT)
            
            os.remove(SAVE_PATH)
            progress_bar.value = 1
            self.page.update()
        except Exception as e:
            raise Exception(f"Extraction failed: {str(e)}")

def main(page: ft.Page):
    update_checker = UpdateChecker(page)
    update_checker.update_window = page.window
    update_checker.check_ver()

    page.title = "KayoVPN XC"
    page.window_resizable = True
    page.update()

if __name__ == "__main__":
    ft.app(target=main)