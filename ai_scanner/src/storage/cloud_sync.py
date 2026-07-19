import os
from typing import Optional


class CloudSync:
    def __init__(self):
        self.drive_service = None
        self.dropbox_client = None
        self.onedrive_client = None

    def setup_google_drive(self, credentials_path: str = None) -> bool:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            creds = None
            token_file = "token_google_drive.json"

            if os.path.exists(token_file):
                creds = Credentials.from_authorized_user_file(token_file)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    client_id = os.getenv("GOOGLE_DRIVE_CLIENT_ID")
                    client_secret = os.getenv("GOOGLE_DRIVE_CLIENT_SECRET")
                    if not client_id:
                        return False

                    flow = InstalledAppFlow.from_client_config(
                        {"installed": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "redirect_uris": [os.getenv("GOOGLE_DRIVE_REDIRECT_URI", "http://localhost:8080/")],
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                        }},
                        scopes=["https://www.googleapis.com/auth/drive.file"],
                    )
                    creds = flow.run_local_server(port=8080)

                with open(token_file, "w") as f:
                    f.write(creds.to_json())

            self.drive_service = build("drive", "v3", credentials=creds)
            return True
        except Exception:
            return False

    def upload_to_drive(self, filepath: str, filename: str = None,
                        folder_name: str = "AI_Scanner") -> Optional[str]:
        if not self.drive_service:
            return None

        try:
            from googleapiclient.http import MediaFileUpload
            from googleapiclient.discovery import build

            if filename is None:
                filename = os.path.basename(filepath)

            folder_id = self._get_or_create_drive_folder(folder_name)
            media = MediaFileUpload(filepath, resumable=True)
            file_metadata = {
                "name": filename,
                "parents": [folder_id] if folder_id else [],
            }
            file = self.drive_service.files().create(
                body=file_metadata, media_body=media, fields="id,webViewLink"
            ).execute()
            return file.get("webViewLink")
        except Exception:
            return None

    def _get_or_create_drive_folder(self, folder_name: str) -> Optional[str]:
        try:
            response = self.drive_service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)",
            ).execute()
            folders = response.get("files", [])
            if folders:
                return folders[0]["id"]

            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            folder = self.drive_service.files().create(
                body=file_metadata, fields="id"
            ).execute()
            return folder.get("id")
        except Exception:
            return None

    def setup_dropbox(self) -> bool:
        try:
            import dropbox
            token = os.getenv("DROPBOX_ACCESS_TOKEN")
            if not token:
                return False
            self.dropbox_client = dropbox.Dropbox(token)
            self.dropbox_client.users_get_current_account()
            return True
        except Exception:
            return False

    def upload_to_dropbox(self, filepath: str, filename: str = None) -> Optional[str]:
        if not self.dropbox_client:
            return None
        try:
            import dropbox
            if filename is None:
                filename = os.path.basename(filepath)
            dest_path = f"/AI_Scanner/{filename}"
            with open(filepath, "rb") as f:
                self.dropbox_client.files_upload(f.read(), dest_path,
                                                  mode=dropbox.files.WriteMode("overwrite"))
            shared = self.dropbox_client.sharing_create_shared_link_with_settings(dest_path)
            return shared.url
        except Exception:
            return None

    def upload_to_all(self, filepath: str, filename: str = None) -> dict:
        results = {}
        drive_link = self.upload_to_drive(filepath, filename)
        if drive_link:
            results["google_drive"] = drive_link

        dropbox_link = self.upload_to_dropbox(filepath, filename)
        if dropbox_link:
            results["dropbox"] = dropbox_link

        return results
