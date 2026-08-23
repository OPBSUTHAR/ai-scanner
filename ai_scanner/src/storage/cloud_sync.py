import os
import json
import re
import time
import threading
from typing import Optional


class CloudSync:
    """Cloud provider sync with per-user sessions.

    Each web user (identified by the session cookie) gets their own isolated
    set of cloud clients and stored tokens. A thread-local holds the active
    user for the current request; the web layer calls activate_user() first.
    When the app is hosted, this means every user connects THEIR OWN Google
    Drive / Dropbox / OneDrive account instead of sharing one global one.
    """

    def __init__(self):
        self._local = threading.local()
        self._client_map = {}
        self._drive_flows = {}
        self._dropbox_flows = {}
        self._onedrive_apps = {}
        self._onedrive_redirect_uris = {}
        self._usage_cache = {}
        self.restore_session()

    # ---- user session plumbing ----

    def activate_user(self, user: str = "default"):
        self._local.user = self._key(user)

    def _key(self, user) -> str:
        return re.sub(r"[^A-Za-z0-9._-]", "_", str(user or "default")).strip() or "default"

    def _user_key(self) -> str:
        return getattr(self._local, "user", "default")

    def _clients(self, user: str = None) -> dict:
        user = self._key(user) if user is not None else self._user_key()
        if user not in self._client_map:
            c = {"drive_service": None, "dropbox_client": None,
                 "onedrive_client": None, "onedrive_token": None}
            self._client_map[user] = c
            self._restore_user(user, c)
        return self._client_map[user]

    def disconnect(self, provider: str, user: str = None):
        c = self._clients(user)
        if provider == "google_drive":
            c["drive_service"] = None
        elif provider == "dropbox":
            c["dropbox_client"] = None
        elif provider == "onedrive":
            c["onedrive_client"] = None
            c["onedrive_token"] = None
        try:
            u = self._key(user) if user is not None else self._user_key()
            path = self._token_path(u, provider)
            if os.path.exists(path):
                os.remove(path)
            if u == "default":
                legacy = os.path.join(os.path.dirname(__file__), "..", "..",
                                      "tokens", f"{provider}.json")
                if os.path.exists(legacy):
                    os.remove(legacy)
        except Exception:
            pass

    # ---- Google credentials ----

    def _google_oauth_config(self) -> dict:
        cfg = {"client_id": None, "client_secret": None, "redirect_uris": []}
        creds_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE", "")
        if not creds_path:
            creds_path = self._find_credentials_file()
        if creds_path and os.path.exists(creds_path):
            try:
                with open(creds_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                web = data.get("web", data.get("installed", data))
                cfg["client_id"] = web.get("client_id")
                cfg["client_secret"] = web.get("client_secret")
                cfg["redirect_uris"] = [u for u in web.get("redirect_uris", []) if u]
            except Exception:
                cfg = {"client_id": None, "client_secret": None, "redirect_uris": []}
        if not cfg["client_id"]:
            cfg["client_id"] = os.getenv("GOOGLE_DRIVE_CLIENT_ID")
            cfg["client_secret"] = os.getenv("GOOGLE_DRIVE_CLIENT_SECRET")
            uri = os.getenv("GOOGLE_DRIVE_REDIRECT_URI", "http://localhost:8080/")
            cfg["redirect_uris"] = [uri] if uri else []
        return cfg

    def _find_credentials_file(self) -> Optional[str]:
        root = os.path.join(os.path.dirname(__file__), "..", "..")
        found = []
        for name in os.listdir(root):
            if not name.endswith(".json"):
                continue
            lower = name.lower()
            if "credential" in lower or name.startswith("client_secret_"):
                if "example" in lower:
                    continue
                found.append(os.path.join(root, name))
        if not found:
            return None
        found.sort(key=os.path.getmtime, reverse=True)
        if len(found) > 1:
            print(f"[CloudSync] Multiple Google credentials files found, using newest: {found[0]}")
        return found[0]

    def _resolve_drive_redirect_uri(self, redirect_uri: str = None) -> Optional[str]:
        # Explicit URI (e.g. derived from the hosted request) wins outright;
        # only fall back to configured/localhost defaults when nothing given.
        if redirect_uri:
            return redirect_uri
        registered = self._google_oauth_config().get("redirect_uris", [])
        if registered:
            return registered[0]
        return os.getenv("GOOGLE_DRIVE_REDIRECT_URI", "http://localhost:8080/")

    def status(self, user: str = None) -> dict:
        c = self._clients(user)
        cfg = self._google_oauth_config()
        return {
            "google_drive": {
                "configured": bool(cfg["client_id"]),
                "connected": c["drive_service"] is not None,
                "redirect_uri": (cfg["redirect_uris"] or [None])[0],
            },
            "dropbox": {
                "configured": bool(os.getenv("DROPBOX_APP_KEY") or os.getenv("DROPBOX_ACCESS_TOKEN")),
                "connected": c["dropbox_client"] is not None,
                "redirect_uri": self._dropbox_redirect_uri(),
            },
            "onedrive": {
                "configured": bool(os.getenv("ONEDRIVE_CLIENT_ID") and os.getenv("ONEDRIVE_CLIENT_SECRET")),
                "connected": c["onedrive_client"] is not None,
                "redirect_uri": self._onedrive_redirect_uri(),
            },
        }

    # ---- Google Drive ----

    def get_google_drive_auth_url(self, redirect_uri: str = None, user: str = None) -> Optional[str]:
        try:
            from google_auth_oauthlib.flow import Flow
            cfg = self._google_oauth_config()
            if not cfg["client_id"]:
                return None
            redirect_uri = self._resolve_drive_redirect_uri(redirect_uri)
            flow = Flow.from_client_config(
                {"web": {
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "redirect_uris": cfg["redirect_uris"] or [redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }},
                scopes=["https://www.googleapis.com/auth/drive.file"],
                redirect_uri=redirect_uri,
            )
            auth_url, _ = flow.authorization_url(prompt="consent")
            self._drive_flows[self._user_key()] = flow
            print(f"[CloudSync] Google Drive auth URL generated (redirect sent to Google):")
            print(f"[CloudSync]   {auth_url}")
            return auth_url
        except Exception:
            return None

    def handle_google_drive_callback(self, code: str, redirect_uri: str = None,
                                     user: str = None) -> bool:
        try:
            from googleapiclient.discovery import build
            u = self._key(user) if user is not None else self._user_key()
            flow = self._drive_flows.get(u)
            if flow is None:
                from google_auth_oauthlib.flow import Flow
                cfg = self._google_oauth_config()
                if not cfg["client_id"]:
                    return False
                redirect_uri = self._resolve_drive_redirect_uri(redirect_uri)
                flow = Flow.from_client_config(
                    {"web": {
                        "client_id": cfg["client_id"],
                        "client_secret": cfg["client_secret"],
                        "redirect_uris": cfg["redirect_uris"] or [redirect_uri],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }},
                    scopes=["https://www.googleapis.com/auth/drive.file"],
                    redirect_uri=redirect_uri,
                )
            flow.fetch_token(code=code)
            self._clients(user)["drive_service"] = build("drive", "v3", credentials=flow.credentials)
            self._save_token(user, "google_drive", flow.credentials.to_json())
            self._drive_flows.pop(u, None)
            return True
        except Exception:
            return False

    def upload_to_drive(self, filepath: str, filename: str = None,
                        folder_name: str = "AI_Scanner", user: str = None) -> Optional[str]:
        c = self._clients(user)
        if not c["drive_service"]:
            return None
        try:
            from googleapiclient.http import MediaFileUpload
            if filename is None:
                filename = os.path.basename(filepath)
            folder_id = self._get_or_create_drive_folder(folder_name, user)
            media = MediaFileUpload(filepath, resumable=True)
            file_metadata = {
                "name": filename,
                "parents": [folder_id] if folder_id else [],
            }
            file = c["drive_service"].files().create(
                body=file_metadata, media_body=media, fields="id,webViewLink"
            ).execute()
            return file.get("webViewLink")
        except Exception:
            return None

    def _get_or_create_drive_folder(self, folder_name: str, user: str = None) -> Optional[str]:
        c = self._clients(user)
        try:
            response = c["drive_service"].files().list(
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
            folder = c["drive_service"].files().create(
                body=file_metadata, fields="id"
            ).execute()
            return folder.get("id")
        except Exception:
            return None

    # ---- Dropbox ----

    DROPBOX_DEFAULT_REDIRECT = "http://localhost:5000/cloud/callback/dropbox"

    def _dropbox_redirect_uri(self, redirect_uri: str = None) -> str:
        return redirect_uri or os.getenv(
            "DROPBOX_REDIRECT_URI", self.DROPBOX_DEFAULT_REDIRECT)

    def setup_dropbox(self, user: str = None) -> bool:
        try:
            import dropbox
            token = os.getenv("DROPBOX_ACCESS_TOKEN")
            if not token:
                return False
            client = dropbox.Dropbox(token)
            self._clients(user)["dropbox_client"] = client
            self._save_token(user, "dropbox", json.dumps({"access_token": token}))
            return True
        except Exception as e:
            self._dropbox_last_error = repr(e)
            print(f"[CloudSync] Dropbox token validation failed: {e!r}")
            return False

    def get_dropbox_auth_url(self, redirect_uri: str = None, user: str = None) -> Optional[str]:
        try:
            import dropbox
            app_key = os.getenv("DROPBOX_APP_KEY")
            if not app_key:
                return None
            u = self._key(user) if user is not None else self._user_key()
            app_secret = os.getenv("DROPBOX_APP_SECRET")
            flow = dropbox.DropboxOAuth2FlowNoRedirect(
                app_key,
                consumer_secret=app_secret or None,
                token_access_type="offline",
                use_pkce=not bool(app_secret),
            )
            auth_url = flow.start()
            self._dropbox_flows[u] = flow
            print(f"[CloudSync] Dropbox auth-CODE URL generated (no redirect needed)")
            return auth_url
        except Exception as e:
            print(f"[CloudSync] Dropbox auth URL error: {e!r}")
            return None

    def handle_dropbox_callback(self, query_params: dict, user: str = None) -> bool:
        try:
            import dropbox
            code = (query_params or {}).get("code", "")
            if not code:
                self._dropbox_last_error = "Missing auth code"
                return False
            u = self._key(user) if user is not None else self._user_key()
            flow = self._dropbox_flows.get(u)
            if flow is None:
                app_key = os.getenv("DROPBOX_APP_KEY")
                if not app_key:
                    return False
                flow = dropbox.DropboxOAuth2FlowNoRedirect(
                    app_key,
                    consumer_secret=os.getenv("DROPBOX_APP_SECRET") or None,
                    token_access_type="offline",
                    use_pkce=not bool(os.getenv("DROPBOX_APP_SECRET")),
                )
            result = flow.finish(code)
            self._clients(user)["dropbox_client"] = dropbox.Dropbox(
                oauth2_access_token=result.access_token,
                oauth2_refresh_token=getattr(result, "refresh_token", None),
                app_key=os.getenv("DROPBOX_APP_KEY"),
            )
            self._save_token(user, "dropbox", json.dumps({
                "access_token": result.access_token,
                "refresh_token": getattr(result, "refresh_token", None),
            }))
            self._dropbox_flows.pop(u, None)
            return True
        except Exception as e:
            self._dropbox_last_error = repr(e)
            print(f"[CloudSync] Dropbox callback error: {e!r}")
            return False

    def upload_to_dropbox(self, filepath: str, filename: str = None, user: str = None) -> Optional[str]:
        c = self._clients(user)
        if not c["dropbox_client"]:
            return None
        try:
            import dropbox
            if filename is None:
                filename = os.path.basename(filepath)
            dest_path = f"/AI_Scanner/{filename}"
            with open(filepath, "rb") as f:
                c["dropbox_client"].files_upload(f.read(), dest_path,
                                                 mode=dropbox.files.WriteMode("overwrite"))
            shared = c["dropbox_client"].sharing_create_shared_link_with_settings(dest_path)
            return shared.url
        except Exception:
            return None

    # ---- OneDrive ----

    ONEDRIVE_SCOPES = ["Files.ReadWrite.All"]
    ONEDRIVE_DEFAULT_REDIRECT = "http://localhost:5000/cloud/callback/onedrive"

    def _onedrive_redirect_uri(self, redirect_uri: str = None) -> str:
        return redirect_uri or os.getenv(
            "ONEDRIVE_REDIRECT_URI", self.ONEDRIVE_DEFAULT_REDIRECT)

    def _onedrive_msal_app(self, user: str = None):
        """Build a ConfidentialClientApplication with a persisted token cache.

        Returns (app, cache, token_path) or (None, None, None) when the app
        registration is not configured. The cache is loaded from disk so the
        refresh token survives restarts and can be used silently.
        """
        import msal
        client_id = os.getenv("ONEDRIVE_CLIENT_ID")
        if not client_id:
            return None, None, None
        u = self._key(user) if user is not None else self._user_key()
        tenant_id = os.getenv("ONEDRIVE_TENANT_ID", "common")
        token_path = self._token_path(u, "onedrive")
        cache = msal.SerializableTokenCache()
        if os.path.exists(token_path):
            try:
                cache.deserialize(open(token_path, "r", encoding="utf-8").read())
            except Exception:
                cache = msal.SerializableTokenCache()
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=os.getenv("ONEDRIVE_CLIENT_SECRET"),
            token_cache=cache,
        )
        return app, cache, token_path

    def _persist_onedrive_cache(self, cache, token_path: str):
        try:
            if cache.has_state_changed:
                os.makedirs(os.path.dirname(token_path), exist_ok=True)
                with open(token_path, "w", encoding="utf-8") as f:
                    f.write(cache.serialize())
        except Exception:
            pass

    def _ensure_onedrive_token(self, user: str = None) -> bool:
        """Refresh the OneDrive access token silently when needed."""
        c = self._clients(user)
        app = c.get("onedrive_client")
        if app is None:
            return bool(c.get("onedrive_token"))
        try:
            accounts = app.get_accounts()
            if accounts:
                result = app.acquire_token_silent(self.ONEDRIVE_SCOPES, account=accounts[0])
                if result and "access_token" in result:
                    c["onedrive_token"] = result["access_token"]
                    cache = c.get("onedrive_cache")
                    if cache is not None:
                        token_path = c.get("onedrive_token_path")
                        if token_path:
                            self._persist_onedrive_cache(cache, token_path)
                    return True
        except Exception:
            pass
        return bool(c.get("onedrive_token"))

    def get_onedrive_auth_url(self, redirect_uri: str = None, user: str = None) -> Optional[str]:
        try:
            u = self._key(user) if user is not None else self._user_key()
            app, cache, token_path = self._onedrive_msal_app(u)
            if app is None:
                return None
            redirect_uri = self._onedrive_redirect_uri(redirect_uri)
            auth_url = app.get_authorization_request_url(
                self.ONEDRIVE_SCOPES, redirect_uri=redirect_uri)
            self._onedrive_apps[u] = (app, cache, token_path)
            self._onedrive_redirect_uris[u] = redirect_uri
            return auth_url
        except Exception:
            return None

    def handle_onedrive_callback(self, code: str, user: str = None) -> bool:
        try:
            u = self._key(user) if user is not None else self._user_key()
            entry = self._onedrive_apps.get(u)
            if entry:
                app, cache, token_path = entry
            else:
                app, cache, token_path = self._onedrive_msal_app(u)
                if app is None:
                    return False
            redirect_uri = self._onedrive_redirect_uris.get(
                u, self._onedrive_redirect_uri())
            result = app.acquire_token_by_authorization_code(
                code, scopes=self.ONEDRIVE_SCOPES,
                redirect_uri=redirect_uri,
            )
            if "access_token" in result:
                c = self._clients(user)
                c["onedrive_client"] = app
                c["onedrive_cache"] = cache
                c["onedrive_token_path"] = token_path
                c["onedrive_token"] = result["access_token"]
                self._persist_onedrive_cache(cache, token_path)
                self._onedrive_apps.pop(u, None)
                return True
            return False
        except Exception:
            return False

    def upload_to_onedrive(self, filepath: str, filename: str = None, user: str = None) -> Optional[str]:
        c = self._clients(user)
        if not self._ensure_onedrive_token(user) or not c.get("onedrive_token"):
            return None
        try:
            import requests
            if filename is None:
                filename = os.path.basename(filepath)
            folder_id = self._get_or_create_onedrive_folder("AI_Scanner", user)
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{filename}:/content"
            headers = {
                "Authorization": f"Bearer {c['onedrive_token']}",
                "Content-Type": "application/octet-stream",
            }
            with open(filepath, "rb") as f:
                resp = requests.put(url, headers=headers, data=f)
            if resp.status_code in (200, 201):
                item = resp.json()
                return item.get("webUrl")
            return None
        except Exception:
            return None

    def _get_or_create_onedrive_folder(self, folder_name: str, user: str = None) -> Optional[str]:
        c = self._clients(user)
        if not self._ensure_onedrive_token(user) or not c.get("onedrive_token"):
            return None
        try:
            import requests
            headers = {"Authorization": f"Bearer {c['onedrive_token']}"}
            resp = requests.get(
                "https://graph.microsoft.com/v1.0/me/drive/root/children",
                headers=headers,
            )
            if resp.status_code == 200:
                for item in resp.json().get("value", []):
                    if item.get("name") == folder_name and item.get("folder"):
                        return item["id"]
            create_url = "https://graph.microsoft.com/v1.0/me/drive/root/children"
            body = {
                "name": folder_name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "rename",
            }
            resp = requests.post(create_url, headers=headers, json=body)
            if resp.status_code in (200, 201):
                return resp.json()["id"]
            return None
        except Exception:
            return None

    # ---- Multi ----

    def get_folder_url(self, provider: str, user: str = None) -> Optional[str]:
        """Browser URL to open the app's AI_Scanner folder on a connected provider."""
        if provider == "google_drive":
            c = self._clients(user)
            if not c["drive_service"]:
                return None
            try:
                folder_id = self._get_or_create_drive_folder("AI_Scanner", user)
                if folder_id:
                    return f"https://drive.google.com/drive/folders/{folder_id}"
            except Exception:
                return None
        elif provider == "dropbox":
            if not self._clients(user).get("dropbox_client"):
                return None
            return "https://www.dropbox.com/home/AI_Scanner"
        elif provider == "onedrive":
            c = self._clients(user)
            if not c.get("onedrive_client") and not c.get("onedrive_token"):
                return None
            try:
                import requests
                if not self._ensure_onedrive_token(user):
                    return None
                folder_id = self._get_or_create_onedrive_folder("AI_Scanner", user)
                if not folder_id:
                    return None
                headers = {"Authorization": f"Bearer {c['onedrive_token']}"}
                resp = requests.get(
                    f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}",
                    params={"select": "webUrl"},
                    headers=headers,
                )
                if resp.status_code == 200:
                    return resp.json().get("webUrl")
            except Exception:
                return None
        return None

    def get_usage_stats(self, user: str = None) -> dict:
        key = self._key(user) if user is not None else self._user_key()
        cache_key = f"usage:{key}"
        now = time.time()
        cached = self._usage_cache.get(cache_key)
        if cached and now - cached[0] < 30:
            return cached[1]
        usage = {
            "google_drive": self._get_drive_usage(user),
            "dropbox": self._get_dropbox_usage(user),
            "onedrive": self._get_onedrive_usage(user),
        }
        self._usage_cache[cache_key] = (now, usage)
        return usage

    def _get_drive_usage(self, user: str = None) -> Optional[str]:
        c = self._clients(user)
        if not c["drive_service"]:
            return None
        try:
            total = 0
            page_token = None
            while True:
                resp = c["drive_service"].files().list(
                    q="name='AI_Scanner' and mimeType='application/vnd.google-apps.folder'",
                    fields="files(id)", pageToken=page_token
                ).execute()
                folders = resp.get("files", [])
                for folder in folders:
                    child_resp = c["drive_service"].files().list(
                        q=f"'{folder['id']}' in parents",
                        fields="files(size,name)", pageToken=page_token
                    ).execute()
                    for f in child_resp.get("files", []):
                        total += int(f.get("size", 0))
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            if total > 1048576:
                return f"{total/1048576:.1f} MB"
            return f"{total/1024:.1f} KB"
        except Exception:
            return None

    def _get_dropbox_usage(self, user: str = None) -> Optional[str]:
        c = self._clients(user)
        if not c["dropbox_client"]:
            return None
        try:
            total = 0
            resp = c["dropbox_client"].files_list_folder("/AI_Scanner")
            for entry in resp.entries:
                total += entry.size if hasattr(entry, "size") else 0
            while resp.has_more:
                resp = c["dropbox_client"].files_list_folder_continue(resp.cursor)
                for entry in resp.entries:
                    total += entry.size if hasattr(entry, "size") else 0
            if total > 1048576:
                return f"{total/1048576:.1f} MB"
            return f"{total/1024:.1f} KB"
        except Exception:
            return None

    def _get_onedrive_usage(self, user: str = None) -> Optional[str]:
        c = self._clients(user)
        if not c["onedrive_token"]:
            return None
        try:
            import requests
            headers = {"Authorization": f"Bearer {c['onedrive_token']}"}
            resp = requests.get(
                "https://graph.microsoft.com/v1.0/me/drive/root:/AI_Scanner:/children",
                headers=headers,
            )
            if resp.status_code != 200:
                return None
            total = sum(item.get("size", 0) for item in resp.json().get("value", []))
            if total > 1048576:
                return f"{total/1048576:.1f} MB"
            return f"{total/1024:.1f} KB"
        except Exception:
            return None

    def upload_to_all(self, filepath: str, filename: str = None, user: str = None) -> dict:
        results = {}
        link = self.upload_to_drive(filepath, filename, user=user)
        if link:
            results["google_drive"] = link
        link = self.upload_to_dropbox(filepath, filename, user=user)
        if link:
            results["dropbox"] = link
        link = self.upload_to_onedrive(filepath, filename, user=user)
        if link:
            results["onedrive"] = link
        return results

    def upload_to_providers(self, filepath: str, providers: list,
                            filename: str = None, user: str = None) -> dict:
        results = {}
        if "google_drive" in providers:
            link = self.upload_to_drive(filepath, filename, user=user)
            if link:
                results["google_drive"] = link
        if "dropbox" in providers:
            link = self.upload_to_dropbox(filepath, filename, user=user)
            if link:
                results["dropbox"] = link
        if "onedrive" in providers:
            link = self.upload_to_onedrive(filepath, filename, user=user)
            if link:
                results["onedrive"] = link
        return results

    # ---- token storage (per user) ----

    def _token_path(self, user: str, provider: str) -> str:
        token_dir = os.path.join(os.path.dirname(__file__), "..", "..", "tokens")
        return os.path.join(token_dir, f"{self._key(user)}.{provider}.json")

    def _save_token(self, user: str | None, provider: str, token_data: str):
        token_dir = os.path.join(os.path.dirname(__file__), "..", "..", "tokens")
        os.makedirs(token_dir, exist_ok=True)
        path = self._token_path(user, provider)
        with open(path, "w") as f:
            f.write(token_data)

    def _load_token(self, user: str | None, provider: str) -> Optional[str]:
        token_dir = os.path.join(os.path.dirname(__file__), "..", "..", "tokens")
        path = self._token_path(user, provider)
        if not os.path.exists(path):
            legacy = os.path.join(token_dir, f"{provider}.json")
            if os.path.exists(legacy):
                path = legacy
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return f.read()
            except Exception:
                return None
        return None

    def _restore_user(self, user: str, c: dict):
        token_data = self._load_token(user, "google_drive")
        if token_data:
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build
                creds = Credentials.from_authorized_user_info(json.loads(token_data))
                c["drive_service"] = build("drive", "v3", credentials=creds)
            except Exception:
                c["drive_service"] = None

        token = self._load_token(user, "dropbox")
        if token:
            try:
                import dropbox
                try:
                    data = json.loads(token)
                    access = data.get("access_token")
                    refresh = data.get("refresh_token")
                except Exception:
                    access, refresh = token, None
                if refresh:
                    c["dropbox_client"] = dropbox.Dropbox(
                        oauth2_access_token=access,
                        oauth2_refresh_token=refresh,
                        app_key=os.getenv("DROPBOX_APP_KEY"),
                    )
                else:
                    c["dropbox_client"] = dropbox.Dropbox(access)
            except Exception:
                c["dropbox_client"] = None

        token = self._load_token(user, "onedrive")
        if token:
            try:
                app, cache, token_path = self._onedrive_msal_app(user)
                if app is None:
                    raise ValueError("OneDrive app not configured")
                c["onedrive_client"] = app
                c["onedrive_cache"] = cache
                c["onedrive_token_path"] = token_path
                c["onedrive_token"] = token.strip()
            except Exception:
                c["onedrive_client"] = None
                c["onedrive_token"] = token.strip()

    def restore_session(self):
        """Legacy alias — the 'default' user session is restored on demand."""
        self._clients("default")