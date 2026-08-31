import base64
import ctypes
from ctypes import wintypes
import http.client
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "LensTranslate"
API_HOST = "api.mymemory.translated.net"
API_PATH = "/get"
GEMINI_API_HOST = "generativelanguage.googleapis.com"
GEMINI_MODEL = "gemini-3.7-flash"
APP_CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_TITLE
SETTINGS_FILE = APP_CONFIG_DIR / "settings.json"
LEGACY_SETTINGS_FILE = Path(__file__).with_name("settings.json")

LANGUAGES = {
    "Phát hiện ngôn ngữ": "auto",
    "Tiếng Việt": "vi",
    "English": "en",
    "中文 (简体)": "zh-CN",
    "中文 (繁體)": "zh-TW",
    "日本語": "ja",
    "한국어": "ko",
    "Français": "fr",
    "Deutsch": "de",
    "Español": "es",
    "Português": "pt",
    "Italiano": "it",
    "Русский": "ru",
    "ไทย": "th",
    "Bahasa Indonesia": "id",
}

HOTKEY_ID_SELECTION = 1
HOTKEY_ID_OCR = 2
HOTKEY_ID_SHOW = 3
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
VK_OEM_3 = 0xC0
VK_CONTROL = 0x11
VK_C = 0x43
KEYEVENTF_KEYUP = 0x0002
SINGLE_KEY_VK = {
    "MINUS": 0xBD, "EQUAL": 0xBB, "BRACKETLEFT": 0xDB, "BRACKETRIGHT": 0xDD,
    "BACKSLASH": 0xDC, "SEMICOLON": 0xBA, "APOSTROPHE": 0xDE, "COMMA": 0xBC,
    "PERIOD": 0xBE, "SLASH": 0xBF, "PLUS": 0xBB, "GRAVE": VK_OEM_3,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "HOME": 0x24, "END": 0x23, "INSERT": 0x2D, "DELETE": 0x2E,
    "PAGEUP": 0x21, "PAGEDOWN": 0x22, "RETURN": 0x0D, "ENTER": 0x0D,
    "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC, ";": 0xBA, "'": 0xDE,
    ",": 0xBC, ".": 0xBE, "/": 0xBF,
}

DEFAULT_HOTKEYS = {
    "translate_selection": "`",
    "ocr_screen": "Ctrl+Shift+O",
    "show_window": "Ctrl+Q",
}
HOTKEY_LABELS = {
    "translate_selection": "Dịch văn bản đã chọn",
    "ocr_screen": "OCR vùng màn hình",
    "show_window": "Hiện cửa sổ chính",
}


def load_settings() -> dict:
    defaults = {
        "source": "Phát hiện ngôn ngữ",
        "target": "Tiếng Việt",
        "auto_translate": False,
        "always_on_top": False,
        "hotkeys_enabled": True,
        "hotkeys": DEFAULT_HOTKEYS.copy(),
        "ocr_provider": "Tesseract (cục bộ)",
        "translation_provider": "MyMemory Translation API",
        "ocr_api_key": "",
        "gemini_api_key": "",
        "ocr_engine": "2",
        "start_with_windows": False,
        "dark_mode": False,
        "text_font_size": 13,
    }
    try:
        settings_path = SETTINGS_FILE if SETTINGS_FILE.exists() else LEGACY_SETTINGS_FILE
        loaded = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return defaults
        hotkeys = loaded.get("hotkeys", {})
        if not isinstance(hotkeys, dict):
            hotkeys = {}
        defaults.update(
            {
                "source": loaded.get("source", defaults["source"]),
                "target": loaded.get("target", defaults["target"]),
                "auto_translate": bool(loaded.get("auto_translate", False)),
                "always_on_top": bool(loaded.get("always_on_top", False)),
                "hotkeys_enabled": bool(loaded.get("hotkeys_enabled", True)),
                "hotkeys": {**DEFAULT_HOTKEYS, **hotkeys},
                "ocr_provider": loaded.get("ocr_provider", "Tesseract (cục bộ)"),
                "translation_provider": loaded.get("translation_provider", "MyMemory Translation API"),
                "ocr_api_key": loaded.get("ocr_api_key", ""),
                "gemini_api_key": loaded.get("gemini_api_key", ""),
                "ocr_engine": str(loaded.get("ocr_engine", "2")),
                "start_with_windows": bool(loaded.get("start_with_windows", False)),
                "dark_mode": bool(loaded.get("dark_mode", False)),
                "text_font_size": max(9, min(30, int(loaded.get("text_font_size", 13)))),
            }
        )
        return defaults
    except (OSError, ValueError, TypeError):
        return defaults


def save_settings(settings: dict) -> None:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def enable_windows_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


def get_virtual_screen_bbox() -> tuple[int, int, int, int]:
    """Return (left, top, width, height) spanning every connected monitor.

    On Windows this covers all monitors combined (the "virtual screen"),
    so multi-monitor setups are fully capturable instead of only the
    primary display.
    """
    if os.name == "nt":
        try:
            user32 = ctypes.windll.user32
            left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            if width > 0 and height > 0:
                return left, top, width, height
        except (AttributeError, OSError):
            pass
    return 0, 0, 0, 0


class LensTranslateApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.launched_hidden = os.environ.pop("LENS_TRANSLATE_START_HIDDEN", "") == "1"
        self.geometry("520x420")
        self.minsize(320, 220)
        self.resizable(True, True)
        self.configure(bg="#ffffff")

        self.settings = load_settings()
        self.source_var = tk.StringVar(value=self._valid_source(self.settings.get("source")))
        self.target_var = tk.StringVar(value=self._valid_target(self.settings.get("target")))
        self.auto_translate_var = tk.BooleanVar(value=bool(self.settings.get("auto_translate", False)))
        self.always_on_top_var = tk.BooleanVar(value=bool(self.settings.get("always_on_top", False)))
        self.hotkeys_enabled_var = tk.BooleanVar(value=bool(self.settings.get("hotkeys_enabled", True)))
        self.ocr_provider_var = tk.StringVar(value=self.settings.get("ocr_provider", "Tesseract (cục bộ)"))
        self.translation_provider_var = tk.StringVar(value=self.settings.get("translation_provider", "MyMemory Translation API"))
        self.ocr_engine_var = tk.StringVar(value=str(self.settings.get("ocr_engine", "2")))
        self.ocr_api_key = str(self.settings.get("ocr_api_key", ""))
        self.gemini_api_key = str(self.settings.get("gemini_api_key", ""))
        self.start_with_windows_var = tk.BooleanVar(value=bool(self.settings.get("start_with_windows", False)))
        self.dark_mode_var = tk.BooleanVar(value=bool(self.settings.get("dark_mode", False)))
        self.text_font_size = self._valid_text_font_size(self.settings.get("text_font_size", 13))
        self.text_font_size_var = tk.IntVar(value=self.text_font_size)
        self.ocr_provider = self.ocr_provider_var.get()
        self.translation_provider = self.translation_provider_var.get()
        self.status_var = tk.StringVar(value="Sẵn sàng")
        self.char_var = tk.StringVar(value="0 ký tự")
        self.detected_var = tk.StringVar(value="")
        self.active_mode = "Văn bản"

        self.translate_after: str | None = None
        self.translation_running = False
        self.tts_process: subprocess.Popen | None = None
        self.history: list[tuple[str, str]] = []
        self.hotkey_config = {**DEFAULT_HOTKEYS, **self.settings.get("hotkeys", {})}
        self.hotkey_thread: threading.Thread | None = None
        self.hotkey_thread_id = 0
        self.hotkey_registered_ids: set[int] = set()
        self.hotkey_registered = False
        self.hotkey_capture_running = False
        self.hotkey_modifier_down: set[str] = set()
        self.clipboard_before_hotkey = ""
        self.clipboard_sequence_before = 0

        self.ocr_selection_running = False
        self.ocr_overlay = None
        self.ocr_screenshot = None
        self.ocr_start_x = 0
        self.ocr_start_y = 0
        self.ocr_rectangle = None
        self.preview_photo = None
        self.tray_icon = None
        self.tray_thread: threading.Thread | None = None
        self.closing = False

        self._build_style()
        self._build_ui()
        self._apply_text_font_size()
        self._apply_theme()
        self._bind_shortcuts()
        self.attributes("-topmost", self.always_on_top_var.get())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_tray()
        if self.start_with_windows_var.get():
            self._apply_start_with_windows(True)
        self._start_global_hotkey()
        self._update_char_count()
        if self.launched_hidden:
            self.after(150, self.withdraw)

    @staticmethod
    def _valid_source(value: str | None) -> str:
        return value if value in LANGUAGES else "Phát hiện ngôn ngữ"

    @staticmethod
    def _valid_target(value: str | None) -> str:
        return value if value in LANGUAGES and value != "Phát hiện ngôn ngữ" else "Tiếng Việt"

    @staticmethod
    def _valid_text_font_size(value) -> int:
        try:
            return max(9, min(30, int(value)))
        except (TypeError, ValueError):
            return 13

    def _theme_palette(self) -> dict[str, str]:
        if self.dark_mode_var.get():
            return {
                "bg": "#202124", "surface": "#292a2d", "surface_alt": "#303134",
                "text": "#e8eaed", "muted": "#9aa0a6", "border": "#5f6368",
                "input": "#202124", "accent": "#8ab4f8", "accent_bg": "#3c4043",
                "status": "#171717", "select": "#3c5279",
            }
        return {
            "bg": "#ffffff", "surface": "#ffffff", "surface_alt": "#f8f9fa",
            "text": "#202124", "muted": "#5f6368", "border": "#dadce0",
            "input": "#ffffff", "accent": "#1a73e8", "accent_bg": "#e8f0fe",
            "status": "#f8f9fa", "select": "#c5dafe",
        }

    def _build_style(self) -> None:
        self.colors = self._theme_palette()
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            style.theme_use("clam")
        self._configure_ttk_style(style)

    def _configure_ttk_style(self, style: ttk.Style | None = None) -> None:
        style = style or ttk.Style(self)
        c = self.colors
        style.configure("Root.TFrame", background=c["bg"])
        style.configure("Header.TFrame", background=c["bg"])
        style.configure("Tab.TButton", background=c["surface"], foreground=c["muted"], padding=(16, 8), font=("Segoe UI", 10))
        style.map("Tab.TButton", background=[("active", c["accent_bg"])], foreground=[("active", c["accent"])])
        style.configure("ActiveTab.TButton", background=c["accent_bg"], foreground=c["accent"], padding=(16, 8), font=("Segoe UI", 10, "bold"))
        style.configure("Small.TButton", background=c["surface"], foreground=c["text"], padding=(7, 4), font=("Segoe UI", 9))
        style.configure("Primary.TButton", background=c["accent_bg"], foreground=c["accent"], padding=(22, 9), font=("Segoe UI", 10, "bold"))
        style.configure("Status.TFrame", background=c["status"])
        style.configure("Status.TLabel", background=c["status"], foreground=c["muted"], font=("Segoe UI", 9))
        style.configure("Language.TCombobox", fieldbackground=c["input"], background=c["surface"], foreground=c["text"], arrowcolor=c["muted"], padding=(7, 5), font=("Segoe UI", 10))
        style.map("Language.TCombobox", fieldbackground=[("readonly", c["input"])], foreground=[("readonly", c["text"])])

    def _theme_widget_tree(self, widget) -> None:
        c = self.colors
        try:
            widget_class = widget.winfo_class()
            if widget_class in {"Frame", "Label", "Button", "Checkbutton", "Radiobutton", "Toplevel"}:
                widget.configure(bg=c["surface" if widget is not self else "bg"])
            if widget_class == "Label":
                widget.configure(fg=c["text"])
            elif widget_class == "Button":
                widget.configure(fg=c["accent"] if widget.cget("text") in {"OCR vùng", "Mở ảnh", "Chọn ảnh", "Chụp vùng màn hình", "Translate"} else c["muted"], activebackground=c["accent_bg"])
            elif widget_class in {"Text", "Entry"}:
                widget.configure(bg=c["input"], fg=c["text"], insertbackground=c["accent"], selectbackground=c["select"], selectforeground=c["text"])
            elif widget_class == "Listbox":
                widget.configure(bg=c["input"], fg=c["text"], selectbackground=c["accent"], selectforeground="#ffffff")
        except (tk.TclError, TypeError):
            pass
        try:
            for child in widget.winfo_children():
                self._theme_widget_tree(child)
        except tk.TclError:
            pass

    def _apply_theme(self) -> None:
        self.colors = self._theme_palette()
        self.configure(bg=self.colors["bg"])
        self._configure_ttk_style()
        self._theme_widget_tree(self)

    def _toggle_dark_mode(self) -> None:
        self._apply_theme()
        self._settings_changed()
        self.status_var.set("Đã chuyển sang " + ("dark mode" if self.dark_mode_var.get() else "light mode"))

    def _build_ui(self) -> None:
        self.root_frame = ttk.Frame(self, style="Root.TFrame", padding=(6, 4, 6, 4))
        self.root_frame.pack(fill="both", expand=True)
        self.root_frame.columnconfigure(0, weight=1)
        self.root_frame.rowconfigure(1, weight=1)
        self._build_header()
        self._build_text_workspace()
        self._build_status_bar()
        self._show_mode("Văn bản")

    def _build_header(self) -> None:
        header = ttk.Frame(self.root_frame, style="Header.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        header.columnconfigure(1, weight=1)
        logo = tk.Frame(header, bg=self.colors["bg"])
        logo.grid(row=0, column=0, sticky="w", padx=(4, 0))
        tk.Label(logo, text="Lens", bg=self.colors["bg"], fg="#4285f4", font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(logo, text="Translate", bg=self.colors["bg"], fg=self.colors["muted"], font=("Segoe UI", 14)).pack(side="left")
        tk.Button(header, text="⋮", command=self._show_menu, relief="flat", bd=0, bg=self.colors["bg"], fg=self.colors["muted"], activebackground=self.colors["accent_bg"], font=("Segoe UI", 15), cursor="hand2", width=2).grid(row=0, column=1, sticky="e", padx=(0, 2))

    def _build_text_workspace(self) -> None:
        self.text_workspace = ttk.Frame(self.root_frame, style="Root.TFrame")
        self.text_workspace.grid(row=1, column=0, sticky="nsew")
        self.text_workspace.columnconfigure(0, weight=1)
        self.text_workspace.rowconfigure(0, weight=1)
        self.text_workspace.rowconfigure(2, weight=1)

        self.source_card, self.source_text = self._make_text_card(self.text_workspace, "", False)
        self.source_card.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        controls = ttk.Frame(self.text_workspace, style="Root.TFrame")
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(2, weight=1)
        self.source_combo = ttk.Combobox(controls, textvariable=self.source_var, values=list(LANGUAGES), state="readonly", style="Language.TCombobox", width=17)
        self.source_combo.grid(row=0, column=0, sticky="ew")
        self.source_combo.bind("<<ComboboxSelected>>", self._language_changed)
        ttk.Button(controls, text="⇄", width=3, style="Small.TButton", command=self._swap_languages).grid(row=0, column=1, padx=5)
        self.target_combo = ttk.Combobox(controls, textvariable=self.target_var, values=[name for name in LANGUAGES if name != "Phát hiện ngôn ngữ"], state="readonly", style="Language.TCombobox", width=17)
        self.target_combo.grid(row=0, column=2, sticky="ew")
        self.target_combo.bind("<<ComboboxSelected>>", self._language_changed)
        ttk.Button(controls, text="Dịch", style="Primary.TButton", command=self._start_translation).grid(row=0, column=3, padx=(6, 0))

        self.result_card, self.result_text = self._make_text_card(self.text_workspace, "", True)
        self.result_card.grid(row=2, column=0, sticky="nsew")

    def _make_text_card(self, parent: ttk.Frame, title: str, result: bool):
        card = tk.Frame(parent, bg="#ffffff", highlightbackground="#dadce0", highlightthickness=1)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)
        head = tk.Frame(card, bg="#ffffff", height=25 if title else 16)
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=(2, 0))
        head.columnconfigure(0, weight=1)
        if title:
            tk.Label(head, text=title, bg="#ffffff", fg="#3c4043", font=("Segoe UI", 10, "bold"), anchor="w").grid(row=0, column=0, sticky="w")
        if result:
            tk.Label(head, textvariable=self.detected_var, bg="#ffffff", fg="#80868b", font=("Segoe UI", 8), anchor="e").grid(row=0, column=1, sticky="e")
        else:
            tk.Label(head, textvariable=self.char_var, bg="#ffffff", fg="#9aa0a6", font=("Segoe UI", 8), anchor="e").grid(row=0, column=1, sticky="e")
        text = tk.Text(card, wrap="word", undo=not result, state="disabled" if result else "normal", font=("Segoe UI", self.text_font_size), bg="#ffffff", fg="#202124", insertbackground="#1a73e8", selectbackground="#c5dafe", relief="flat", borderwidth=0, padx=16, pady=12)
        text.grid(row=1, column=0, sticky="nsew", padx=(0, 4))
        scrollbar = ttk.Scrollbar(card, orient="vertical", command=text.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 8), pady=4)
        text.configure(yscrollcommand=scrollbar.set)
        foot = tk.Frame(card, bg="#ffffff", height=42)
        foot.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(2, 8))
        foot.columnconfigure(0, weight=1)
        if not result:
            self._flat_button(foot, "⌫", self._clear_source, 1)
            self._flat_button(foot, "▣", self._copy_source, 2)
            self._flat_button(foot, "◖", self._speak_source, 3)
            self._flat_button(foot, "OCR vùng", self._start_ocr_capture, 4, accent=True)
            self._flat_button(foot, "Mở ảnh", self._open_image_for_ocr, 5, accent=True)
        else:
            self._flat_button(foot, "▣", self._copy_result, 1)
            self._flat_button(foot, "◖", self._speak_result, 2)
            self._flat_button(foot, "■", self._stop_speaking, 3)
        return card, text

    @staticmethod
    def _flat_button(parent, label, command, column, accent=False):
        tk.Button(parent, text=label, command=command, relief="flat", bd=0, bg="#ffffff", fg="#1a73e8" if accent else "#5f6368", activebackground="#f1f3f4", font=("Segoe UI", 9, "bold" if accent else "normal"), cursor="hand2").grid(row=0, column=column, padx=4)

    def _build_image_workspace(self) -> None:
        self.image_workspace = ttk.Frame(self.root_frame, style="Root.TFrame")
        self.image_workspace.grid(row=3, column=0, sticky="nsew")
        self.image_workspace.columnconfigure(0, weight=1)
        self.image_workspace.columnconfigure(1, weight=1)
        self.image_workspace.rowconfigure(1, weight=1)
        image_controls = ttk.Frame(self.image_workspace, style="Root.TFrame")
        image_controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        image_controls.columnconfigure(0, weight=1)
        ttk.Label(image_controls, text="Dùng Google Lens-style OCR trên ảnh hoặc vùng màn hình", foreground="#5f6368", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        ttk.Button(image_controls, text="Chọn ảnh", style="Primary.TButton", command=self._open_image_for_ocr).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(image_controls, text="Chụp vùng màn hình", style="Small.TButton", command=self._start_ocr_capture).grid(row=0, column=2, padx=(8, 0))

        left = tk.Frame(self.image_workspace, bg="#ffffff", highlightbackground="#dadce0", highlightthickness=1)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        tk.Label(left, text="Ảnh đầu vào", bg="#ffffff", fg="#3c4043", font=("Segoe UI", 10, "bold"), anchor="w").grid(row=0, column=0, sticky="w", padx=16, pady=12)
        self.image_preview = tk.Label(left, text="Chọn ảnh hoặc chụp một vùng màn hình\nđể bắt đầu nhận dạng chữ", bg="#f8f9fa", fg="#80868b", font=("Segoe UI", 11), justify="center")
        self.image_preview.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        right = tk.Frame(self.image_workspace, bg="#ffffff", highlightbackground="#dadce0", highlightthickness=1)
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        tk.Label(right, text="Văn bản nhận dạng", bg="#ffffff", fg="#3c4043", font=("Segoe UI", 10, "bold"), anchor="w").grid(row=0, column=0, sticky="w", padx=16, pady=12)
        self.ocr_text = tk.Text(right, wrap="word", state="disabled", font=("Segoe UI", 12), bg="#ffffff", fg="#202124", relief="flat", padx=16, pady=12)
        self.ocr_text.grid(row=1, column=0, sticky="nsew", padx=(0, 4))
        ocr_actions = tk.Frame(right, bg="#ffffff", height=42)
        ocr_actions.grid(row=2, column=0, sticky="e", padx=12, pady=(2, 8))
        self._flat_button(ocr_actions, "▣ Sao chép", self._copy_ocr_text, 0)

    def _build_status_bar(self) -> None:
        status = ttk.Frame(self.root_frame, style="Status.TFrame", padding=(10, 7))
        status.grid(row=2, column=0, sticky="ew", pady=(3, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(status, text="Tự động dịch", variable=self.auto_translate_var, command=self._settings_changed).grid(row=0, column=1, padx=(12, 0))

    def _show_mode(self, mode: str) -> None:
        # The compact QTranslate layout has one continuous text workspace.
        # Image/OCR actions feed their text into this same workspace.
        self.active_mode = "Văn bản"

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-Return>", lambda _event: self._start_translation())
        self.bind("<Control-l>", lambda _event: self._clear_source())
        self.bind("<Control-L>", lambda _event: self._clear_source())
        self.bind("<Control-Shift-c>", lambda _event: self._copy_result())
        self.bind("<Control-Shift-C>", lambda _event: self._copy_result())
        self.bind("<Escape>", lambda _event: self._cancel_ocr_capture())
        self.source_text.bind("<KeyRelease>", self._source_changed)
        self.source_text.bind("<Double-Button-1>", self._select_word_naturally)

    def _select_word_naturally(self, event):
        """Select only the word under a double-click, like a normal editor."""
        index = self.source_text.index(f"@{event.x},{event.y}")
        start = self.source_text.index(f"{index} wordstart")
        end = self.source_text.index(f"{index} wordend")
        selected = self.source_text.get(start, end)
        if selected.strip():
            self.source_text.tag_remove("sel", "1.0", "end")
            self.source_text.tag_add("sel", start, end)
            self.source_text.mark_set("insert", end)
        else:
            self.source_text.tag_remove("sel", "1.0", "end")
            self.source_text.mark_set("insert", index)
        self.source_text.focus_set()
        return "break"

    def _source_changed(self, _event=None) -> None:
        self._update_char_count()
        if self.auto_translate_var.get():
            if self.translate_after:
                self.after_cancel(self.translate_after)
            self.translate_after = self.after(750, self._start_translation)

    def _update_char_count(self) -> None:
        count = len(self.source_text.get("1.0", "end-1c"))
        self.char_var.set(f"{count:,} ký tự")

    def _language_changed(self, _event=None) -> None:
        self._settings_changed()
        if self.auto_translate_var.get() and self.source_text.get("1.0", "end-1c").strip():
            self._start_translation()

    def _settings_changed(self) -> None:
        self.settings.update({
            "source": self.source_var.get(),
            "target": self.target_var.get(),
            "auto_translate": self.auto_translate_var.get(),
            "always_on_top": self.always_on_top_var.get(),
            "hotkeys_enabled": self.hotkeys_enabled_var.get(),
            "hotkeys": self.hotkey_config,
            "ocr_provider": self.ocr_provider_var.get(),
            "translation_provider": self.translation_provider_var.get(),
            "ocr_api_key": self.ocr_api_key,
            "gemini_api_key": self.gemini_api_key,
            "ocr_engine": self.ocr_engine_var.get(),
            "start_with_windows": self.start_with_windows_var.get(),
            "dark_mode": self.dark_mode_var.get(),
            "text_font_size": self.text_font_size,
        })
        save_settings(self.settings)

    def _swap_languages(self) -> None:
        """Swap the language direction and retranslate the visible source."""
        source_name = self.source_var.get()
        target_name = self.target_var.get()
        source_text = self.source_text.get("1.0", "end-1c")
        result_text = self._get_result()
        valid_result = result_text.strip() and not result_text.startswith("Không thể dịch")

        # A detected source has no fixed language to swap back to. Keep the
        # previous compact-UI behavior by using English as its concrete side.
        concrete_source = "English" if source_name == "Phát hiện ngôn ngữ" else source_name
        self.source_var.set(target_name)
        self.target_var.set(concrete_source)

        # If a translation already exists, make it the new source. This means
        # English -> Vietnamese becomes Vietnamese -> English naturally.
        if valid_result:
            self._set_source(result_text)
        elif source_text.strip():
            self._set_source(source_text)
        else:
            self._set_source("")
        self._set_result("")
        self._settings_changed()

        # Translate immediately in the new direction, including the common
        # Vietnamese-on-top -> English-below use case.
        if self.source_var.get() != self.target_var.get() and self.source_text.get("1.0", "end-1c").strip():
            self._start_translation()

    def _start_translation(self) -> None:
        if self.translation_running:
            return
        text = self.source_text.get("1.0", "end-1c").strip()
        if not text:
            self.status_var.set("Hãy nhập văn bản cần dịch")
            self.source_text.focus_set()
            return
        if len(text) > 5000:
            messagebox.showwarning("Văn bản quá dài", "Giới hạn 5.000 ký tự cho mỗi lần dịch.", parent=self)
            return
        source_name = self.source_var.get()
        target_name = self.target_var.get()
        translation_provider = self.translation_provider_var.get()
        source = LANGUAGES.get(source_name, "auto")
        if source == "auto":
            source = self._guess_source_language(text)
        target = LANGUAGES.get(target_name, "vi")
        self.translation_running = True
        self.status_var.set("Đang dịch...")
        threading.Thread(target=self._translate_worker, args=(text, source, target, source_name, target_name, translation_provider), daemon=True).start()

    @staticmethod
    def _guess_source_language(text: str) -> str:
        if any("\u4e00" <= char <= "\u9fff" for char in text):
            return "zh-CN"
        if any("\u3040" <= char <= "\u30ff" for char in text):
            return "ja"
        if any("\uac00" <= char <= "\ud7af" for char in text):
            return "ko"
        if any("\u0400" <= char <= "\u04ff" for char in text):
            return "ru"
        vietnamese = "ăâđêôơưĂÂĐÊÔƠƯàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
        if any(char in vietnamese for char in text):
            return "vi"
        return "en"

    def _gemini_translate_text(self, text: str, source_name: str, target_name: str, api_key: str) -> str:
        source_instruction = "tự động phát hiện ngôn ngữ" if source_name == "Phát hiện ngôn ngữ" else source_name
        prompt = (
            "Bạn là dịch giả chuyên nghiệp. Hãy dịch nguyên văn nội dung dưới đây "
            f"từ {source_instruction} sang {target_name}. Giữ nguyên ý nghĩa, số dòng, "
            "kí hiệu và định dạng cơ bản. Chỉ trả về bản dịch, không giải thích, không thêm dấu ngoặc kép.\n\n"
            f"NỘI DUNG CẦN DỊCH:\n{text}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        connection = http.client.HTTPSConnection(GEMINI_API_HOST, timeout=60)
        try:
            connection.request(
                "POST", f"/v1beta/models/{GEMINI_MODEL}:generateContent", body=body,
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                    "User-Agent": "LensTranslate/1.0",
                },
            )
            response = connection.getresponse()
            raw = response.read().decode("utf-8", errors="replace")
            try:
                response_payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Gemini trả về dữ liệu không hợp lệ.") from exc
            if response.status in {401, 403}:
                raise RuntimeError("Gemini API key không hợp lệ hoặc chưa được cấp quyền Gemini API.")
            if response.status != 200:
                detail = response_payload.get("error", {}).get("message", f"HTTP {response.status}")
                raise RuntimeError(f"Gemini: {detail}")
            candidates = response_payload.get("candidates") or []
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            translated = "".join(
                str(part.get("text", "")) for part in parts if isinstance(part, dict)
            ).strip()
            if not translated:
                raise RuntimeError("Gemini không trả về bản dịch.")
            if translated.startswith("```"):
                translated = translated.strip("`").strip()
                if translated.lower().startswith("text"):
                    translated = translated[4:].strip()
            return translated
        finally:
            connection.close()

    def _translate_worker(self, text: str, source: str, target: str, source_name: str, target_name: str, translation_provider: str) -> None:
        if translation_provider == "Gemini API":
            api_key = self.gemini_api_key.strip()
            if not api_key:
                self._post_to_ui(self._translation_failed, "Chưa nhập Gemini API key. Mở ⋮ > Cài đặt API để nhập key.")
                return
            try:
                translated = self._gemini_translate_text(text, source_name, target_name, api_key)
                self._post_to_ui(self._translation_succeeded, translated, "", text)
            except (OSError, TimeoutError, RuntimeError) as exc:
                self._post_to_ui(self._translation_failed, str(exc))
            return

        params = urllib.parse.urlencode({"q": text, "langpair": f"{source}|{target}"})
        connection = http.client.HTTPSConnection(API_HOST, timeout=20)
        try:
            connection.request("GET", f"{API_PATH}?{params}", headers={"User-Agent": "LensTranslate/1.0"})
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            translated = payload.get("responseData", {}).get("translatedText", "").strip()
            if not translated:
                raise RuntimeError("Dịch vụ không trả về bản dịch.")
            detected = payload.get("responseData", {}).get("detectedLanguage", "")
            self._post_to_ui(self._translation_succeeded, translated, detected, text)
        except (OSError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            self._post_to_ui(self._translation_failed, str(exc))
        finally:
            connection.close()

    def _translation_succeeded(self, translated: str, detected: str, original: str) -> None:
        self._set_result(translated)
        self.detected_var.set(f"Phát hiện: {detected}" if detected else "")
        self.status_var.set("Dịch xong")
        self.history.append((original, translated))
        self.translation_running = False

    def _translation_failed(self, error: str) -> None:
        self._set_result(f"Không thể dịch lúc này.\n\nChi tiết: {error}")
        self.detected_var.set("")
        self.status_var.set("Dịch thất bại — kiểm tra kết nối mạng")
        self.translation_running = False

    def _set_source(self, text: str) -> None:
        self.source_text.delete("1.0", "end")
        self.source_text.insert("1.0", text)
        self._update_char_count()

    def _set_result(self, text: str) -> None:
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.result_text.configure(state="disabled")

    def _get_result(self) -> str:
        return self.result_text.get("1.0", "end-1c")

    def _set_ocr_text(self, text: str) -> None:
        if hasattr(self, "ocr_text"):
            self.ocr_text.configure(state="normal")
            self.ocr_text.delete("1.0", "end")
            self.ocr_text.insert("1.0", text)
            self.ocr_text.configure(state="disabled")
        else:
            self._set_source(text)

    def _get_ocr_text(self) -> str:
        if hasattr(self, "ocr_text"):
            return self.ocr_text.get("1.0", "end-1c")
        return self.source_text.get("1.0", "end-1c")

    def _clear_source(self) -> None:
        self._set_source("")
        self._set_result("")
        self.detected_var.set("")
        self.status_var.set("Đã xóa")
        self.source_text.focus_set()

    def _copy_text(self, text: str, label: str) -> None:
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set(f"Đã sao chép {label}")

    def _copy_source(self) -> None:
        self._copy_text(self.source_text.get("1.0", "end-1c"), "văn bản nguồn")

    def _copy_result(self) -> None:
        self._copy_text(self._get_result(), "bản dịch")

    def _copy_ocr_text(self) -> None:
        self._copy_text(self._get_ocr_text(), "văn bản OCR")

    def _speak_source(self) -> None:
        self._speak(self.source_text.get("1.0", "end-1c").strip(), LANGUAGES.get(self.source_var.get(), "en"))

    def _speak_result(self) -> None:
        self._speak(self._get_result().strip(), LANGUAGES.get(self.target_var.get(), "vi"))

    def _speak(self, text: str, language: str) -> None:
        if not text:
            self.status_var.set("Không có văn bản để đọc")
            return
        if os.name != "nt":
            self.status_var.set("Đọc thành tiếng chỉ khả dụng trên Windows")
            return
        self._stop_speaking()
        encoded_text = base64.b64encode(text.encode("utf-16le")).decode("ascii")
        encoded_lang = base64.b64encode(language.split("-")[0].encode("utf-16le")).decode("ascii")
        script = (
            "$t=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('" + encoded_text + "'));"
            "$l=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('" + encoded_lang + "'));"
            "Add-Type -AssemblyName System.Speech;"
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            "try{$s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet,[System.Speech.Synthesis.VoiceAge]::NotSet,0,[Globalization.CultureInfo]::GetCultureInfo($l))}catch{};"
            "$s.Speak($t);$s.Dispose()"
        )
        try:
            self.tts_process = subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.status_var.set("Đang đọc...")
        except OSError as exc:
            self.status_var.set(f"Không thể đọc thành tiếng: {exc}")

    def _stop_speaking(self) -> None:
        if self.tts_process is not None and self.tts_process.poll() is None:
            self.tts_process.terminate()
        self.tts_process = None

    def _open_image_for_ocr(self) -> None:
        path = filedialog.askopenfilename(title="Chọn ảnh", filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.bmp *.webp *.tiff"), ("Tất cả", "*.*")])
        if not path:
            return
        try:
            from PIL import Image
            image = Image.open(path)
            self._show_image_preview(image)
        except ImportError:
            messagebox.showerror("Thiếu Pillow", "Hãy chạy install_ocr.bat trước khi dùng OCR.", parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Không thể mở ảnh", str(exc), parent=self)
            return
        self._show_mode("Hình ảnh")
        self.ocr_selection_running = True
        self.status_var.set("Đang nhận dạng chữ trong ảnh...")
        threading.Thread(target=self._ocr_worker, args=(image.copy(),), daemon=True).start()

    def _show_image_preview(self, image) -> None:
        # The compact QTranslate layout intentionally hides the image-preview
        # pane. Keep the method as a safe hook for the OCR workflow.
        if not hasattr(self, "image_preview"):
            return
        try:
            from PIL import ImageTk
            thumbnail = image.copy()
            thumbnail.thumbnail((520, 390))
            self.preview_photo = ImageTk.PhotoImage(thumbnail)
            self.image_preview.configure(image=self.preview_photo, text="")
        except Exception:
            self.image_preview.configure(text="Đã chọn ảnh")

    def _start_ocr_capture(self) -> None:
        if self.ocr_selection_running:
            return
        vx, vy, vwidth, vheight = get_virtual_screen_bbox()
        try:
            from PIL import ImageGrab
            # Capture across every connected monitor (the Windows "virtual
            # screen"), not just the primary display, so the selection
            # overlay and image coordinates stay aligned on multi-monitor
            # setups too.
            if vwidth > 0 and vheight > 0:
                self.ocr_screenshot = ImageGrab.grab(
                    bbox=(vx, vy, vx + vwidth, vy + vheight), all_screens=True
                )
            else:
                vx, vy = 0, 0
                self.ocr_screenshot = ImageGrab.grab(all_screens=True)
        except TypeError:
            # Older Pillow versions do not support all_screens; fall back to
            # the primary-monitor capture rather than failing outright.
            vx, vy = 0, 0
            self.ocr_screenshot = ImageGrab.grab()
        except ImportError:
            messagebox.showerror("Thiếu Pillow", "Hãy chạy install_ocr.bat trước khi dùng OCR.", parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Không thể chụp màn hình", str(exc), parent=self)
            return
        width, height = self.ocr_screenshot.size
        self.ocr_selection_running = True
        self.status_var.set("Kéo chuột chọn vùng cần nhận dạng — Esc để hủy")
        self.withdraw()
        self.after(160, lambda: self._open_ocr_overlay(vx, vy, width, height))

    def _open_ocr_overlay(self, offset_x: int, offset_y: int, width: int, height: int) -> None:
        if not self.ocr_selection_running:
            return
        self.ocr_overlay = tk.Toplevel(self)
        self.ocr_overlay.overrideredirect(True)
        self.ocr_overlay.attributes("-topmost", True)
        self.ocr_overlay.attributes("-alpha", 0.3)
        # Always use the "+" sign and let the number itself carry the minus,
        # e.g. "+-100" — this is the Tk geometry convention for placing a
        # window at a literal negative coordinate (monitors positioned to
        # the left of or above the primary display).
        self.ocr_overlay.geometry(f"{width}x{height}+{offset_x}+{offset_y}")
        self.ocr_overlay.configure(bg="#1a73e8", cursor="crosshair")
        canvas = tk.Canvas(self.ocr_overlay, bg="#1a73e8", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        self.ocr_overlay.canvas = canvas
        canvas.create_text(width // 2, 30, text="Kéo để chọn vùng OCR  •  Esc để hủy", fill="#ffffff", font=("Segoe UI", 13, "bold"))
        canvas.bind("<ButtonPress-1>", self._ocr_mouse_down)
        canvas.bind("<B1-Motion>", self._ocr_mouse_drag)
        canvas.bind("<ButtonRelease-1>", self._ocr_mouse_up)
        self.ocr_overlay.bind("<Escape>", lambda _event: self._cancel_ocr_capture())
        self.ocr_overlay.focus_force()

    def _ocr_mouse_down(self, event) -> None:
        self.ocr_start_x, self.ocr_start_y = event.x, event.y
        self.ocr_rectangle = self.ocr_overlay.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#ffd54f", width=3)

    def _ocr_mouse_drag(self, event) -> None:
        if self.ocr_rectangle is not None:
            self.ocr_overlay.canvas.coords(self.ocr_rectangle, self.ocr_start_x, self.ocr_start_y, event.x, event.y)

    def _ocr_mouse_up(self, event) -> None:
        left, right = sorted((self.ocr_start_x, event.x))
        top, bottom = sorted((self.ocr_start_y, event.y))
        if right - left < 10 or bottom - top < 10:
            self._cancel_ocr_capture()
            return
        crop = self.ocr_screenshot.crop((left, top, right, bottom))
        self._close_ocr_overlay()
        self.ocr_selection_running = True
        self._show_image_preview(crop)
        self._show_mode("Hình ảnh")
        self.status_var.set("Đang nhận dạng chữ trong vùng đã chọn...")
        threading.Thread(target=self._ocr_worker, args=(crop,), daemon=True).start()

    def _close_ocr_overlay(self) -> None:
        if self.ocr_overlay is not None:
            try:
                self.ocr_overlay.destroy()
            except tk.TclError:
                pass
        self.ocr_overlay = None
        self.ocr_rectangle = None

    def _cancel_ocr_capture(self) -> None:
        if self.ocr_overlay is not None:
            self._close_ocr_overlay()
        self.ocr_screenshot = None
        self.ocr_selection_running = False
        self.deiconify()
        self.lift()
        self.status_var.set("Đã hủy OCR")

    @staticmethod
    def _resource_path(*parts: str) -> Path:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        return base.joinpath(*parts)

    def _ocr_space_language(self) -> str:
        code = LANGUAGES.get(self.source_var.get(), "auto")
        mapping = {
            "auto": "auto", "vi": "vnm", "en": "eng", "zh-CN": "chs", "zh-TW": "cht",
            "ja": "jpn", "ko": "kor", "fr": "fre", "de": "ger", "es": "spa",
            "pt": "por", "it": "ita", "ru": "rus", "th": "tha",
        }
        return mapping.get(code, "auto")

    def _ocr_space_extract(self, image, api_key: str) -> str:
        image_buffer = io.BytesIO()
        image = image.convert("RGB")
        image.save(image_buffer, format="JPEG", quality=90, optimize=True)
        image_bytes = image_buffer.getvalue()
        boundary = "----LensTranslateOCRBoundary"
        fields = {
            "language": self._ocr_space_language(),
            "OCREngine": self.ocr_engine_var.get() if self.ocr_engine_var.get() in {"1", "2", "3"} else "2",
            "scale": "true",
            "isOverlayRequired": "false",
            "filetype": "JPG",
        }
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.extend([
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode(),
                b"\r\n",
            ])
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="capture.jpg"\r\n',
            b"Content-Type: image/jpeg\r\n\r\n",
            image_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ])
        body = b"".join(chunks)
        connection = http.client.HTTPSConnection("api.ocr.space", timeout=45)
        try:
            connection.request(
                "POST", "/parse/image", body=body,
                headers={
                    "apikey": api_key,
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Content-Length": str(len(body)),
                    "User-Agent": "LensTranslate/1.0",
                },
            )
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if response.status in {401, 403}:
                raise RuntimeError("OCR.space API key không hợp lệ hoặc không có quyền sử dụng.")
            if response.status != 200:
                raise RuntimeError(f"OCR.space trả về HTTP {response.status}.")
            if payload.get("IsErroredOnProcessing"):
                detail = payload.get("ErrorMessage") or payload.get("ErrorDetails") or "Dịch vụ OCR báo lỗi."
                raise RuntimeError(str(detail))
            parsed = payload.get("ParsedResults") or []
            text = "\n".join(str(item.get("ParsedText", "")) for item in parsed if isinstance(item, dict)).strip()
            if not text:
                raise RuntimeError("OCR.space không nhận dạng được chữ trong ảnh.")
            return text
        except json.JSONDecodeError as exc:
            raise RuntimeError("OCR.space trả về dữ liệu không hợp lệ.") from exc
        finally:
            connection.close()

    def _gemini_extract_and_translate(self, image, api_key: str) -> tuple[str, str]:
        image_buffer = io.BytesIO()
        image = image.convert("RGB")
        image.thumbnail((2400, 2400))
        image.save(image_buffer, format="JPEG", quality=88, optimize=True)
        encoded_image = base64.b64encode(image_buffer.getvalue()).decode("ascii")
        source = self.source_var.get()
        target = self.target_var.get()
        source_instruction = "tự động phát hiện" if source == "Phát hiện ngôn ngữ" else source
        prompt = (
            "Bạn là công cụ OCR và dịch thuật. Đọc toàn bộ chữ nhìn thấy trong ảnh, giữ nguyên xuống dòng "
            f"và dịch từ {source_instruction} sang {target}. Chỉ trả về JSON hợp lệ, không markdown, theo đúng mẫu: "
            '{"extracted_text":"...","translation":"..."}. '
            "Nếu ảnh không có chữ, trả về hai chuỗi rỗng. Không thêm giải thích ngoài JSON."
        )
        payload = {
            "contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": encoded_image}},
            ]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        connection = http.client.HTTPSConnection(GEMINI_API_HOST, timeout=60)
        try:
            connection.request(
                "POST", f"/v1beta/models/{GEMINI_MODEL}:generateContent", body=body,
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                    "User-Agent": "LensTranslate/1.0",
                },
            )
            response = connection.getresponse()
            raw = response.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Gemini trả về dữ liệu không hợp lệ.") from exc
            if response.status in {401, 403}:
                raise RuntimeError("Gemini API key không hợp lệ hoặc chưa được cấp quyền Gemini API.")
            if response.status != 200:
                detail = payload.get("error", {}).get("message", f"HTTP {response.status}")
                raise RuntimeError(f"Gemini: {detail}")
            candidates = payload.get("candidates") or []
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            response_text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict)).strip()
            if not response_text:
                raise RuntimeError("Gemini không trả về kết quả nhận dạng.")
            if response_text.startswith("```"):
                response_text = response_text.strip("`").strip()
                if response_text.lower().startswith("json"):
                    response_text = response_text[4:].strip()
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Gemini trả về kết quả không đúng định dạng JSON.") from exc
            extracted = str(result.get("extracted_text", "")).strip()
            translated = str(result.get("translation", "")).strip()
            if not extracted:
                raise RuntimeError("Gemini không nhận dạng được chữ trong ảnh.")
            return extracted, translated
        finally:
            connection.close()

    def _gemini_succeeded(self, extracted: str, translated: str) -> None:
        self.ocr_selection_running = False
        self.ocr_screenshot = None
        self.deiconify()
        self.lift()
        self._set_ocr_text(extracted)
        self._set_source(extracted)
        self._show_mode("Văn bản")
        if translated:
            self._set_result(translated)
            self.status_var.set("Đã nhận dạng và dịch bằng Gemini")
            self.history.append((extracted, translated))
        else:
            self._set_result("Gemini không trả về bản dịch.")
            self.status_var.set("Đã nhận dạng bằng Gemini nhưng chưa có bản dịch")

    def _ocr_worker(self, image) -> None:
        try:
            if self.ocr_provider_var.get() == "Gemini Vision API":
                api_key = self.gemini_api_key.strip()
                if not api_key:
                    raise RuntimeError("Chưa nhập Gemini API key. Mở ⋮ > Cài đặt API để nhập key.")
                extracted, translated = self._gemini_extract_and_translate(image, api_key)
                self._post_to_ui(self._gemini_succeeded, extracted, translated)
                return

            if self.ocr_provider_var.get() == "OCR.space API":
                api_key = self.ocr_api_key.strip()
                if not api_key:
                    raise RuntimeError("Chưa nhập OCR.space API key. Mở ⋮ > Cài đặt API để nhập key.")
                text = self._ocr_space_extract(image, api_key)
                self._post_to_ui(self._ocr_succeeded, text)
                return

            import pytesseract
            from PIL import ImageEnhance, ImageFilter, ImageOps

            executable = shutil.which("tesseract")
            candidates = [
                self._resource_path("tesseract", "tesseract.exe"),
                Path(r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"),
                Path(r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe"),
            ]
            installed = next((path for path in candidates if path.exists()), None)
            if installed:
                pytesseract.pytesseract.tesseract_cmd = str(installed)
            elif executable:
                pytesseract.pytesseract.tesseract_cmd = executable
            else:
                raise RuntimeError("Chưa tìm thấy Tesseract OCR. Hãy cài Tesseract OCR cho Windows.")

            local_data = self._resource_path("tessdata")
            if local_data.exists():
                # Keep the path unquoted because pytesseract passes config through
                # the Windows argument parser.
                available = {path.stem for path in local_data.glob("*.traineddata")}
                tessdata_config = f"--tessdata-dir {local_data}"
            else:
                available = set(pytesseract.get_languages(config=""))
                tessdata_config = ""
            preferred = self._ocr_languages()
            languages = [lang for lang in preferred if lang in available]
            if not languages and "eng" in available:
                languages = ["eng"]
            if not languages:
                raise RuntimeError("Chưa có gói ngôn ngữ OCR phù hợp. Bản này kèm English và Vietnamese.")

            image = image.convert("RGB")
            # Small UI text is the common failure case. Upscale it before OCR,
            # then use a high-contrast grayscale variant as a second pass.
            scale = 2 if max(image.size) < 1800 else 1
            if scale > 1:
                image = image.resize((image.width * scale, image.height * scale))
            gray = ImageOps.grayscale(image)
            gray = ImageOps.autocontrast(gray)
            gray = ImageEnhance.Contrast(gray).enhance(1.35)
            gray = gray.filter(ImageFilter.SHARPEN)
            variants = [(image, "--psm 6"), (gray, "--psm 6"), (gray, "--psm 11")]
            text = ""
            for candidate, layout in variants:
                config = f"{tessdata_config} {layout}".strip()
                text = pytesseract.image_to_string(candidate, lang="+".join(languages), config=config).strip()
                if text:
                    break
            self._post_to_ui(self._ocr_succeeded, text)
        except Exception as exc:
            self._post_to_ui(self._ocr_failed, str(exc))

    def _ocr_languages(self) -> list[str]:
        code = LANGUAGES.get(self.source_var.get(), "auto")
        mapping = {
            "vi": ["vie", "eng"], "en": ["eng"], "zh-CN": ["chi_sim", "eng"], "zh-TW": ["chi_tra", "eng"],
            "ja": ["jpn", "eng"], "ko": ["kor", "eng"], "fr": ["fra", "eng"], "de": ["deu", "eng"],
            "es": ["spa", "eng"], "pt": ["por", "eng"], "it": ["ita", "eng"], "ru": ["rus", "eng"], "th": ["tha", "eng"],
        }
        return mapping.get(code, ["eng", "vie"])

    def _ocr_succeeded(self, text: str) -> None:
        self.ocr_selection_running = False
        self.ocr_screenshot = None
        self.deiconify()
        self.lift()
        if not text:
            self._ocr_failed("Không nhận dạng được chữ trong ảnh.")
            return
        self._set_ocr_text(text)
        self._set_source(text)
        # Return to the translation panel so OCR text and its translation are
        # visible immediately after scanning.
        self._show_mode("Văn bản")
        self.status_var.set("Đã nhận dạng chữ — đang dịch...")
        self._start_translation()

    def _ocr_failed(self, error: str) -> None:
        self.ocr_selection_running = False
        self.ocr_screenshot = None
        self._close_ocr_overlay()
        self.deiconify()
        self.lift()
        self.status_var.set("OCR thất bại")
        messagebox.showwarning("OCR không thành công", error, parent=self)

    def _clipboard_sequence(self) -> int:
        if os.name != "nt":
            return 0
        try:
            return int(ctypes.windll.user32.GetClipboardSequenceNumber())
        except (AttributeError, OSError):
            return 0

    def _get_clipboard_text(self) -> str:
        try:
            return self.clipboard_get()
        except tk.TclError:
            return ""

    def _restore_clipboard(self) -> None:
        try:
            self.clipboard_clear()
            if self.clipboard_before_hotkey:
                self.clipboard_append(self.clipboard_before_hotkey)
            self.update()
        except tk.TclError:
            pass

    def _handle_global_hotkey(self) -> None:
        if self.hotkey_capture_running:
            return
        self.hotkey_capture_running = True
        self.clipboard_before_hotkey = self._get_clipboard_text()
        self.clipboard_sequence_before = self._clipboard_sequence()
        self.status_var.set("Đang lấy văn bản đã chọn...")
        threading.Thread(target=self._send_copy_shortcut, daemon=True).start()
        self.after(120, self._read_hotkey_clipboard, 0)

    @staticmethod
    def _send_copy_shortcut() -> None:
        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_C, 0, 0, 0)
            user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        except (AttributeError, OSError):
            pass

    def _read_hotkey_clipboard(self, attempt: int) -> None:
        if not self.hotkey_capture_running:
            return
        if self._clipboard_sequence() != self.clipboard_sequence_before:
            selected = self._get_clipboard_text().strip()
            self._restore_clipboard()
            self.hotkey_capture_running = False
            if selected:
                self._show_mode("Văn bản")
                self.deiconify()
                self.lift()
                self.focus_force()
                self._set_source(selected)
                self.status_var.set("Đã lấy vùng chọn — đang dịch...")
                self._start_translation()
            else:
                self.status_var.set("Không có văn bản được chọn")
            return
        if attempt < 6:
            self.after(100, self._read_hotkey_clipboard, attempt + 1)
            return
        self.hotkey_capture_running = False
        self.status_var.set("Không lấy được văn bản đã chọn")

    @staticmethod
    def _parse_hotkey(hotkey: str) -> tuple[int, int] | None:
        if not hotkey:
            return None
        if hotkey.strip() == "-":
            return (MOD_NOREPEAT, SINGLE_KEY_VK["MINUS"])
        parts = [part.strip() for part in hotkey.replace("-", "+").split("+") if part.strip()]
        if not parts:
            return None
        key_name = parts[-1].upper()
        modifiers = MOD_NOREPEAT
        for modifier in parts[:-1]:
            modifier = modifier.upper()
            if modifier in {"CTRL", "CONTROL"}:
                modifiers |= MOD_CONTROL
            elif modifier == "SHIFT":
                modifiers |= MOD_SHIFT
            elif modifier in {"ALT", "MENU"}:
                modifiers |= MOD_ALT
            elif modifier in {"WIN", "WINDOWS"}:
                modifiers |= MOD_WIN
            else:
                return None
        if key_name in {"`", "~", "OEM_3", "GRAVE"}:
            key = VK_OEM_3
        elif key_name in SINGLE_KEY_VK:
            key = SINGLE_KEY_VK[key_name]
        elif len(key_name) == 1 and key_name.isalnum():
            key = ord(key_name)
        elif key_name.startswith("F") and key_name[1:].isdigit() and 1 <= int(key_name[1:]) <= 24:
            key = 0x70 + int(key_name[1:]) - 1
        else:
            key = {"SPACE": 0x20, "TAB": 0x09, "ESC": 0x1B, "ESCAPE": 0x1B}.get(key_name)
        return (modifiers, key) if key is not None else None

    def _start_global_hotkey(self) -> None:
        if os.name != "nt" or (self.hotkey_thread is not None and self.hotkey_thread.is_alive()):
            return
        self.hotkey_thread = threading.Thread(target=self._global_hotkey_loop, args=(self.hotkeys_enabled_var.get(), dict(self.hotkey_config)), daemon=True, name="LensTranslateHotkeys")
        self.hotkey_thread.start()

    def _global_hotkey_loop(self, enabled: bool, config: dict[str, str]) -> None:
        user32 = ctypes.windll.user32
        self.hotkey_thread_id = int(ctypes.windll.kernel32.GetCurrentThreadId())
        actions = {
            HOTKEY_ID_SELECTION: ("translate_selection", self._handle_global_hotkey),
            HOTKEY_ID_OCR: ("ocr_screen", self._start_ocr_capture),
            HOTKEY_ID_SHOW: ("show_window", self._show_window),
        }
        registered: dict[int, str] = {}
        if enabled:
            for hotkey_id, (action, _callback) in actions.items():
                parsed = self._parse_hotkey(config.get(action, ""))
                if parsed and user32.RegisterHotKey(None, hotkey_id, parsed[0], parsed[1]):
                    registered[hotkey_id] = action
        self.hotkey_registered_ids = set(registered)
        self.hotkey_registered = HOTKEY_ID_SELECTION in registered
        self._post_to_ui(self._hotkey_status, bool(registered))
        if not registered:
            return
        message = wintypes.MSG()
        while not self.closing:
            result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result <= 0:
                break
            if message.message == WM_HOTKEY and message.wParam in registered:
                self._post_to_ui(actions[message.wParam][1])
        for hotkey_id in registered:
            user32.UnregisterHotKey(None, hotkey_id)
        self.hotkey_registered_ids.clear()
        self.hotkey_registered = False

    def _hotkey_status(self, registered: bool) -> None:
        if not self.hotkeys_enabled_var.get():
            self.status_var.set("Sẵn sàng — đã tắt phím tắt toàn hệ thống")
        elif registered:
            self.status_var.set(f"Sẵn sàng — nhấn {self.hotkey_config.get('translate_selection', '`')} để dịch vùng chọn")
        else:
            self.status_var.set("Sẵn sàng — chưa đăng ký được phím tắt toàn hệ thống")

    def _show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _startup_file(self) -> Path:
        startup_dir = Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        return startup_dir / "LensTranslate.bat"

    def _apply_start_with_windows(self, enabled: bool) -> None:
        if os.name != "nt":
            return
        startup_file = self._startup_file()
        try:
            if enabled:
                startup_file.parent.mkdir(parents=True, exist_ok=True)
                if getattr(sys, "frozen", False):
                    target = str(Path(sys.executable).resolve())
                    command = f'start "" "{target}"'
                else:
                    target = str(Path(__file__).resolve())
                    command = f'start "" "{sys.executable}" "{target}"'
                startup_file.write_text("@echo off\nset \"LENS_TRANSLATE_START_HIDDEN=1\"\n" + command + "\n", encoding="utf-8")
            elif startup_file.exists():
                startup_file.unlink()
        except OSError as exc:
            messagebox.showwarning("Không thể đổi khởi động Windows", str(exc), parent=self)

    def _toggle_start_with_windows(self) -> None:
        self._apply_start_with_windows(self.start_with_windows_var.get())
        self._settings_changed()
        self.status_var.set("Đã cập nhật khởi động cùng Windows")

    def _restart_global_hotkeys(self) -> None:
        self._stop_global_hotkey()
        self.after(300, self._start_global_hotkey)

    def _stop_global_hotkey(self) -> None:
        if self.hotkey_thread_id and os.name == "nt":
            try:
                ctypes.windll.user32.PostThreadMessageW(self.hotkey_thread_id, WM_QUIT, 0, 0)
            except (AttributeError, OSError):
                pass
            self.hotkey_thread_id = 0

    def _capture_hotkey_event(self, event, variable: tk.StringVar):
        modifier_keys = {"Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R", "Win_L", "Win_R"}
        if event.keysym in modifier_keys:
            self.hotkey_modifier_down.add(event.keysym)
            return "break"
        if event.keysym in {"BackSpace", "Delete"}:
            variable.set("")
            self.hotkey_modifier_down.clear()
            return "break"

        # Do not infer Alt from event.state alone. On some Windows keyboard
        # layouts Tkinter reports an Alt-like bit for an ordinary number key.
        # Modifiers are included only when their own key-down event was seen
        # while the hotkey field had focus.
        modifiers = []
        if any(key.startswith("Control_") for key in self.hotkey_modifier_down):
            modifiers.append("Ctrl")
        if any(key.startswith("Shift_") for key in self.hotkey_modifier_down):
            modifiers.append("Shift")
        if any(key.startswith("Alt_") for key in self.hotkey_modifier_down):
            modifiers.append("Alt")
        if any(key.startswith("Win_") for key in self.hotkey_modifier_down):
            modifiers.append("Win")
        key_names = {
            "grave": "`", "asciitilde": "`", "space": "Space", "Escape": "Esc", "Tab": "Tab",
            "minus": "-", "equal": "=", "plus": "Plus", "bracketleft": "[", "bracketright": "]",
            "backslash": "\\", "semicolon": ";", "apostrophe": "'", "comma": ",", "period": ".", "slash": "/",
            "Left": "Left", "Right": "Right", "Up": "Up", "Down": "Down",
        }
        key = key_names.get(event.keysym, event.keysym.upper() if len(event.keysym) == 1 else event.keysym)
        variable.set("+".join(modifiers + [key]))
        self.hotkey_modifier_down.clear()
        return "break"

    def _release_hotkey_modifier(self, event):
        self.hotkey_modifier_down.discard(event.keysym)
        return "break"

    def _show_options(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Tùy chọn")
        dialog.geometry("720x450")
        dialog.minsize(640, 390)
        dialog.configure(bg="#f0f0f0")
        dialog.transient(self)
        dialog.grab_set()
        enabled = tk.BooleanVar(value=self.hotkeys_enabled_var.get())
        draft = {key: tk.StringVar(value=self.hotkey_config.get(key, "")) for key in DEFAULT_HOTKEYS}

        body = tk.Frame(dialog, bg="#f0f0f0")
        body.pack(fill="both", expand=True, padx=8, pady=8)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        categories = tk.Listbox(body, width=17, exportselection=False, activestyle="none", bg="#ffffff", fg="#202124", selectbackground="#1675c4", selectforeground="#ffffff", relief="solid", bd=1, font=("Segoe UI", 9))
        categories.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        for label in ("Cơ bản", "Phím tắt", "Internet", "Dịch vụ", "Ngôn ngữ", "Xuất hiện", "Ngoại lệ", "Nâng cao", "Cập nhật"):
            categories.insert("end", label)
        categories.selection_set(1)
        page = tk.Frame(body, bg="#ffffff", relief="solid", bd=1)
        page.grid(row=0, column=1, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)
        tk.Checkbutton(page, text="Kích hoạt Phím tắt", variable=enabled, bg="#ffffff", activebackground="#ffffff", anchor="w", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        tk.Label(page, text="Nhấn vào ô Hotkey rồi bấm một phím đơn hoặc tổ hợp phím mới.", bg="#ffffff", fg="#6c7782", anchor="w", font=("Segoe UI", 8)).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        table = ttk.Frame(page)
        table.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        table.columnconfigure(0, weight=1)
        ttk.Label(table, text="Action", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Label(table, text="Hotkey", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=5, pady=5)
        ttk.Separator(table, orient="horizontal").grid(row=1, column=0, columnspan=2, sticky="ew")
        for row, key in enumerate(DEFAULT_HOTKEYS, start=2):
            ttk.Label(table, text=HOTKEY_LABELS[key]).grid(row=row, column=0, sticky="w", padx=5, pady=8)
            entry = ttk.Entry(table, textvariable=draft[key], width=22)
            entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
            entry.bind("<KeyPress>", lambda event, variable=draft[key]: self._capture_hotkey_event(event, variable))
            entry.bind("<KeyRelease>", self._release_hotkey_modifier)

        def apply(close=False):
            values = {key: draft[key].get().strip() for key in DEFAULT_HOTKEYS}
            if any(value and self._parse_hotkey(value) is None for value in values.values()):
                messagebox.showwarning("Hotkey không hợp lệ", "Ví dụ hợp lệ: Ctrl+Shift+O, Ctrl+Q hoặc `.", parent=dialog)
                return
            normalized = [value.lower() for value in values.values() if value]
            if len(normalized) != len(set(normalized)):
                messagebox.showwarning("Hotkey trùng nhau", "Mỗi hành động cần một hotkey khác nhau.", parent=dialog)
                return
            self.hotkey_config = values
            self.hotkeys_enabled_var.set(enabled.get())
            self._settings_changed()
            self._restart_global_hotkeys()
            self.status_var.set("Đã áp dụng cài đặt phím tắt")
            if close:
                dialog.grab_release()
                dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(buttons, text="Đồng ý", command=lambda: apply(True)).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Hủy", command=dialog.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Áp dụng", command=apply).pack(side="right")
        dialog.after_idle(lambda: self._theme_widget_tree(dialog))

    def _show_api_settings(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Cài đặt API")
        # Reserve enough vertical space for the card and the action buttons.
        # The previous 390px height allowed the expanding card to push the
        # Apply/OK/Cancel row below the visible dialog area on Windows.
        dialog.geometry("620x550")
        dialog.minsize(560, 510)
        dialog.configure(bg="#f0f0f0")
        dialog.transient(self)
        dialog.grab_set()

        provider = tk.StringVar(value=self.ocr_provider_var.get())
        translation_provider = tk.StringVar(value=self.translation_provider_var.get())
        key_var = tk.StringVar(value=self.ocr_api_key)
        gemini_key_var = tk.StringVar(value=self.gemini_api_key)
        engine = tk.StringVar(value=self.ocr_engine_var.get())
        show_key = tk.BooleanVar(value=False)

        card = tk.Frame(dialog, bg="#ffffff", relief="solid", bd=1)
        card.pack(fill="both", expand=True, padx=12, pady=12)
        card.columnconfigure(1, weight=1)
        tk.Label(card, text="Cài đặt API", bg="#ffffff", fg="#202124", font=("Segoe UI", 15, "bold"), anchor="w").grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(18, 4))
        tk.Label(card, text="Chọn dịch vụ OCR và nhập API key mà không cần sửa mã nguồn.", bg="#ffffff", fg="#5f6368", font=("Segoe UI", 9), anchor="w").grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 18))
        tk.Label(card, text="OCR provider", bg="#ffffff", fg="#3c4043", font=("Segoe UI", 10), anchor="w").grid(row=2, column=0, sticky="w", padx=20, pady=8)
        provider_box = ttk.Combobox(card, textvariable=provider, state="readonly", values=["Tesseract (cục bộ)", "OCR.space API", "Gemini Vision API"], width=32)
        provider_box.grid(row=2, column=1, sticky="ew", padx=(0, 20), pady=8)
        tk.Label(card, text="OCR.space API key", bg="#ffffff", fg="#3c4043", font=("Segoe UI", 10), anchor="w").grid(row=3, column=0, sticky="w", padx=20, pady=8)
        key_entry = ttk.Entry(card, textvariable=key_var, show="*", width=34)
        key_entry.grid(row=3, column=1, sticky="ew", padx=(0, 20), pady=8)
        tk.Label(card, text="Gemini API key", bg="#ffffff", fg="#3c4043", font=("Segoe UI", 10), anchor="w").grid(row=4, column=0, sticky="w", padx=20, pady=8)
        gemini_key_entry = ttk.Entry(card, textvariable=gemini_key_var, show="*", width=34)
        gemini_key_entry.grid(row=4, column=1, sticky="ew", padx=(0, 20), pady=8)
        tk.Checkbutton(card, text="Hiển thị key", variable=show_key, command=lambda: (key_entry.configure(show="" if show_key.get() else "*"), gemini_key_entry.configure(show="" if show_key.get() else "*")), bg="#ffffff", activebackground="#ffffff", fg="#5f6368", font=("Segoe UI", 9)).grid(row=5, column=1, sticky="w", padx=(0, 20))
        tk.Label(card, text="Nguồn dịch văn bản", bg="#ffffff", fg="#3c4043", font=("Segoe UI", 10), anchor="w").grid(row=6, column=0, sticky="w", padx=20, pady=8)
        ttk.Combobox(card, textvariable=translation_provider, state="readonly", values=["MyMemory Translation API", "Gemini API"], width=32).grid(row=6, column=1, sticky="ew", padx=(0, 20), pady=8)
        tk.Label(card, text="OCR engine", bg="#ffffff", fg="#3c4043", font=("Segoe UI", 10), anchor="w").grid(row=7, column=0, sticky="w", padx=20, pady=8)
        ttk.Combobox(card, textvariable=engine, state="readonly", values=["1", "2", "3"], width=10).grid(row=7, column=1, sticky="w", padx=(0, 20), pady=8)
        tk.Label(card, text="Gemini Vision nhận dạng và dịch ảnh trong một lần gọi. Gemini API dịch văn bản thường.\nOCR.space dùng Engine 2/3; các key được lưu cục bộ trong cấu hình ứng dụng.", bg="#ffffff", fg="#6c7782", justify="left", anchor="w", font=("Segoe UI", 8)).grid(row=8, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 12))
        api_status = tk.StringVar(value="")
        tk.Label(card, textvariable=api_status, bg="#ffffff", fg="#188038", anchor="w", font=("Segoe UI", 9)).grid(row=9, column=0, columnspan=2, sticky="ew", padx=20)

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=12, pady=(0, 12))

        def save_api(close=False):
            if provider.get() == "OCR.space API" and not key_var.get().strip():
                api_status.set("Hãy nhập API key trước khi chọn OCR.space API.")
                return
            if provider.get() == "Gemini Vision API" and not gemini_key_var.get().strip():
                api_status.set("Hãy nhập Gemini API key trước khi chọn Gemini Vision API.")
                return
            if translation_provider.get() == "Gemini API" and not gemini_key_var.get().strip():
                api_status.set("Hãy nhập Gemini API key trước khi chọn Gemini API.")
                return
            self.ocr_provider_var.set(provider.get())
            self.ocr_provider = provider.get()
            self.translation_provider_var.set(translation_provider.get())
            self.translation_provider = translation_provider.get()
            self.ocr_api_key = key_var.get().strip()
            self.gemini_api_key = gemini_key_var.get().strip()
            self.ocr_engine_var.set(engine.get() if engine.get() in {"1", "2", "3"} else "2")
            self._settings_changed()
            self.status_var.set(f"Đã lưu OCR: {provider.get()} | Dịch: {translation_provider.get()}")
            api_status.set("Đã lưu cài đặt.")
            if close:
                dialog.grab_release()
                dialog.destroy()

        ttk.Button(buttons, text="Đồng ý", command=lambda: save_api(True)).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Hủy", command=dialog.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Áp dụng", command=save_api).pack(side="right")
        dialog.after_idle(lambda: self._theme_widget_tree(dialog))

    def _apply_text_font_size(self) -> None:
        font = ("Segoe UI", self.text_font_size)
        for widget_name in ("source_text", "result_text"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.configure(font=font)

    def _set_text_font_size(self, value: int) -> None:
        self.text_font_size = self._valid_text_font_size(value)
        self.text_font_size_var.set(self.text_font_size)
        self._apply_text_font_size()
        self._settings_changed()
        self.status_var.set(f"Đã đổi cỡ chữ: {self.text_font_size}px")

    def _show_menu(self) -> None:
        c = self.colors
        menu = tk.Menu(self, tearoff=False, bg=c["surface"], fg=c["text"], activebackground=c["accent_bg"], activeforeground=c["accent"], bd=0)
        menu.add_command(label="Hiện cửa sổ", command=self._show_window)
        menu.add_command(label="Dịch văn bản đã chọn", command=self._handle_global_hotkey)
        menu.add_command(label="OCR vùng màn hình", command=self._start_ocr_capture)
        menu.add_command(label="Mở ảnh để OCR", command=self._open_image_for_ocr)
        menu.add_separator()
        menu.add_command(label="Tùy chọn phím tắt...", command=self._show_options)
        menu.add_command(label="Cài đặt API...", command=self._show_api_settings)
        font_menu = tk.Menu(menu, tearoff=False, bg=c["surface"], fg=c["text"], activebackground=c["accent_bg"], activeforeground=c["accent"], bd=0)
        menu.add_cascade(label="Cỡ chữ", menu=font_menu)
        for size in (9, 10, 11, 12, 13, 14, 16, 18, 20, 24, 28, 30):
            font_menu.add_radiobutton(label=f"{size}px", variable=self.text_font_size_var, value=size, command=lambda s=size: self._set_text_font_size(s))
        menu.add_checkbutton(label="Tự động dịch", variable=self.auto_translate_var, command=self._settings_changed)
        menu.add_checkbutton(label="Luôn ở trên cùng", variable=self.always_on_top_var, command=self._toggle_always_on_top)
        menu.add_checkbutton(label="Khởi động cùng Windows", variable=self.start_with_windows_var, command=self._toggle_start_with_windows)
        menu.add_checkbutton(label="Dark mode", variable=self.dark_mode_var, command=self._toggle_dark_mode)
        menu.add_separator()
        menu.add_command(label="Thoát", command=self._exit_app)
        menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _toggle_always_on_top(self) -> None:
        self.attributes("-topmost", self.always_on_top_var.get())
        self._settings_changed()

    def _setup_tray(self) -> None:
        if os.name != "nt":
            return
        try:
            import pystray
            from PIL import Image, ImageDraw
            icon_image = Image.new("RGBA", (64, 64), "#4285f4")
            draw = ImageDraw.Draw(icon_image)
            draw.ellipse((14, 14, 50, 50), fill="#ffffff")
            draw.text((27, 20), "L", fill="#4285f4")
            menu = pystray.Menu(
                pystray.MenuItem("Hiện LensTranslate", lambda _icon, _item: self._post_to_ui(self._show_window)),
                pystray.MenuItem("OCR vùng màn hình", lambda _icon, _item: self._post_to_ui(self._start_ocr_capture)),
                pystray.MenuItem("Thoát", lambda _icon, _item: self._post_to_ui(self._exit_app)),
            )
            self.tray_icon = pystray.Icon("LensTranslate", icon_image, APP_TITLE, menu)
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True, name="LensTranslateTray")
            self.tray_thread.start()
        except (ImportError, OSError):
            self.tray_icon = None

    def _on_close(self) -> None:
        if self.tray_icon is not None and not self.closing:
            self.withdraw()
            self.status_var.set("Đang chạy nền — dùng hotkey hoặc biểu tượng ở khay hệ thống")
            return
        self._exit_app()

    def _exit_app(self) -> None:
        if self.closing:
            return
        self.closing = True
        self._close_ocr_overlay()
        self._stop_global_hotkey()
        self._stop_speaking()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self._settings_changed()
        self.destroy()

    def _post_to_ui(self, callback, *args) -> None:
        try:
            self.after(0, callback, *args)
        except (tk.TclError, RuntimeError):
            pass


if __name__ == "__main__":
    enable_windows_dpi_awareness()
    app = LensTranslateApp()
    app.mainloop()
