"""Small local GUI for configuring and starting the IMAP lead poller."""

from __future__ import annotations

import imaplib
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"


class ConfigurationWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Lead mailbox setup")
        self.resizable(False, False)
        self.configure(padx=20, pady=18)
        self.fields: dict[str, tk.StringVar] = {}
        self._build_form()
        self._load_existing_config()

    def _build_form(self) -> None:
        ttk.Label(self, text="Connect your lead mailbox", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        ttk.Label(
            self,
            text="This service reads Drafts through IMAP. Use an app password if your provider requires one.",
            wraplength=440,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 16))

        form = [
            ("IMAP server", "IMAP_HOST", "imap.example.com"),
            ("IMAP port", "IMAP_PORT", "993"),
            ("Email address", "IMAP_USER", "you@example.com"),
            ("Password / app password", "IMAP_PASSWORD", ""),
            ("SMTP server", "SMTP_HOST", "smtp.example.com"),
            ("SMTP port", "SMTP_PORT", "465"),
            ("SMTP username", "SMTP_USER", "you@example.com"),
            ("SMTP password / app password", "SMTP_PASSWORD", ""),
            ("Sender name", "SENDER_NAME", "SE Global"),
            ("Drafts folder", "IMAP_DRAFTS_FOLDER", "Drafts"),
            ("Processed folder", "IMAP_PROCESSED_FOLDER", "Processed"),
            ("Poll interval (seconds)", "POLL_INTERVAL_SECONDS", "300"),
            ("CSV filename marker", "CSV_FILENAME_MARKER", "leads_"),
            ("Subject tag", "SUBJECT_TAG", "[NEW LEADS]"),
            ("SQLite database path", "DATABASE_PATH", "leads.db"),
            ("Ollama model", "OLLAMA_MODEL", "llama3.1:8b"),
            ("Dry-run mode (true/false)", "DRY_RUN", "true"),
        ]
        for row, (label, key, default) in enumerate(form, start=2):
            self.fields[key] = tk.StringVar(value=default)
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=4)
            secret = key.endswith("PASSWORD")
            entry = ttk.Entry(self, textvariable=self.fields[key], width=42, show="*" if secret else "")
            entry.grid(row=row, column=1, sticky="ew", pady=4)

        actions = ttk.Frame(self)
        action_row = len(form) + 3
        actions.grid(row=action_row, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        ttk.Button(actions, text="Test connection", command=self._test_connection).pack(side="left")
        ttk.Button(actions, text="Save settings", command=self._save).pack(side="left", padx=8)
        ttk.Button(actions, text="Save and start poller", command=self._save_and_start).pack(side="right")
        self.status = ttk.Label(self, text="Settings are stored locally in .env")
        self.status.grid(row=action_row + 1, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def _load_existing_config(self) -> None:
        if not ENV_FILE.exists():
            return
        values: dict[str, str] = {}
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value
        for key, variable in self.fields.items():
            if key in values:
                variable.set(values[key])

    def _settings(self) -> dict[str, str]:
        return {key: variable.get().strip() for key, variable in self.fields.items()}

    def _validate(self, values: dict[str, str]) -> bool:
        required = ("IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD")
        missing = [key for key in required if not values[key]]
        if missing:
            messagebox.showerror("Missing settings", "Please fill in the server, email address, and password.")
            return False
        try:
            int(values["IMAP_PORT"])
            int(values["SMTP_PORT"])
            int(values["POLL_INTERVAL_SECONDS"])
        except ValueError:
            messagebox.showerror("Invalid settings", "IMAP port and poll interval must be whole numbers.")
            return False
        if values["DRY_RUN"].lower() not in ("true", "false"):
            messagebox.showerror("Invalid settings", "Dry-run mode must be true or false.")
            return False
        return True

    def _test_connection(self) -> None:
        values = self._settings()
        if not self._validate(values):
            return
        self.status.configure(text="Testing IMAP connection...")
        self.update_idletasks()
        try:
            client = imaplib.IMAP4_SSL(values["IMAP_HOST"], int(values["IMAP_PORT"]))
            try:
                client.login(values["IMAP_USER"], values["IMAP_PASSWORD"])
                status, _ = client.select(values["IMAP_DRAFTS_FOLDER"], readonly=True)
                if status != "OK":
                    raise RuntimeError(f"Folder not found: {values['IMAP_DRAFTS_FOLDER']}")
            finally:
                client.logout()
        except Exception as error:
            self.status.configure(text="Connection failed")
            messagebox.showerror("IMAP connection failed", str(error))
            return
        self.status.configure(text="IMAP connection successful")
        messagebox.showinfo("Connection successful", "The mailbox and Drafts folder are reachable.")

    def _save(self) -> bool:
        values = self._settings()
        if not self._validate(values):
            return False
        lines = [f"{key}={value}" for key, value in values.items()]
        lines.append("LOG_LEVEL=INFO")
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.status.configure(text=f"Saved settings to {ENV_FILE.name}")
        return True

    def _save_and_start(self) -> None:
        if not self._save():
            return
        os.environ.update(self._settings())
        creation_flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        subprocess.Popen(
            [sys.executable, str(ROOT / "ingest_service.py")],
            cwd=ROOT,
            creationflags=creation_flags,
        )
        self.status.configure(text="Poller started")
        messagebox.showinfo("Poller started", "The lead ingestion poller is running in its own console window.")


if __name__ == "__main__":
    ConfigurationWindow().mainloop()
