"""The finished app: an English settings window and a tray icon.

While the app runs, finished is on and its icon sits in the tray. Closing the window only
hides it to the tray. "Quit finished" in the tray (or `finished quit`) turns finished off:
agents' notifications stay silent until the app is opened again. With "Start with Windows"
the app starts in the tray at sign-in.
"""
import ctypes
import os
import queue
import subprocess
import threading
import tkinter as tk
import webbrowser
import winreg
from tkinter import messagebox, ttk

import finished as fin

REPO = "https://github.com/spixyy7/agent-finished"
SCRIPT = os.path.abspath(fin.__file__)
PYW = fin.PYW if os.path.exists(fin.PYW) else fin.PY
ICO = os.path.join(fin.HOME, "icon.ico")
SHOW_SIGNAL = os.path.join(fin.CACHE, "app.show")
QUIT_SIGNAL = os.path.join(fin.CACHE, "app.quit")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MUTEX = "Local\\finished-app"
_mutex = None


# ---------------------------------------------------------------- process helpers

def touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("1")


def take(path):
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def first_instance():
    global _mutex
    k = ctypes.windll.kernel32
    _mutex = k.CreateMutexW(None, False, MUTEX)
    return k.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def is_running():
    k = ctypes.windll.kernel32
    handle = k.OpenMutexW(0x00100000, False, MUTEX)  # SYNCHRONIZE
    if handle:
        k.CloseHandle(handle)
        return True
    return False


def autostart(on=None):
    """Read (on=None) or set 'Start with Windows'."""
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        if on is None:
            try:
                winreg.QueryValueEx(key, "finished")
                return True
            except FileNotFoundError:
                return False
        if on:
            winreg.SetValueEx(key, "finished", 0, winreg.REG_SZ, f'"{PYW}" "{SCRIPT}" tray')
        else:
            try:
                winreg.DeleteValue(key, "finished")
            except FileNotFoundError:
                pass
        return on


def ensure_ico():
    if not os.path.exists(ICO):
        from PIL import Image
        Image.open(fin.ICON).save(ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128)])
    return ICO


def launch(hidden):
    subprocess.Popen([PYW, SCRIPT, "tray" if hidden else "app", "--here"],
                     creationflags=0x00000008 | 0x00000200, cwd=fin.HOME, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def set_enabled(on):
    cfg = fin.load_cfg()
    cfg["enabled"] = on
    fin.save_cfg(cfg)


def command(cmd, rest):
    """finished app | tray | on | quit | off"""
    here = "--here" in rest
    if cmd in ("app", "tray") and here:
        return run(hidden=cmd == "tray")
    if cmd == "tray" and not fin.load_cfg().get("enabled", True):
        return 0  # started with Windows while turned off: stay off
    if cmd in ("app", "tray", "on"):
        set_enabled(True)
        if is_running():
            if cmd == "app":
                touch(SHOW_SIGNAL)
        else:
            launch(hidden=cmd != "app")
        print("finished is on (tray icon).")
        return 0
    if cmd in ("quit", "off"):
        set_enabled(False)
        if is_running():
            touch(QUIT_SIGNAL)
        print("finished is off: agents' notifications are silent until you open it again (finished app).")
        return 0
    if cmd == "uninstall":
        set_enabled(False)
        if is_running():
            touch(QUIT_SIGNAL)
        autostart(False)
        import agents
        agents.connect(["all"], remove=True)
        removed = []
        lnk = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "finished.lnk")
        shims = [os.path.join(os.path.expanduser("~"), ".local", "bin", n) for n in ("finished.cmd", "finished")]
        for path in [lnk] + shims:
            try:
                if path != lnk:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        if "finished.py" not in f.read():
                            continue  # not ours
                os.remove(path)
                removed.append(path)
            except OSError:
                pass
        print("Removed: start with Windows" + "".join(f", {p}" for p in removed))
        print(f"To remove finished completely, delete its folder: {fin.HOME}")
        return 0
    return 1


def run(hidden):
    if not first_instance():
        if not hidden:
            touch(SHOW_SIGNAL)
        return 0
    take(SHOW_SIGNAL)
    take(QUIT_SIGNAL)
    set_enabled(True)
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("finished.app")
    except (AttributeError, OSError):
        pass
    App(hidden).mainloop()
    return 0


def windows_theme():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return "light" if winreg.QueryValueEx(key, "AppsUseLightTheme")[0] else "dark"
    except OSError:
        return "light"


# ---------------------------------------------------------------- window

class App(tk.Tk):
    def __init__(self, hidden):
        super().__init__()
        self.withdraw()
        self.events = queue.Queue()
        self.told_tray = False
        self.theme = windows_theme()
        self.title("finished")
        self.resizable(False, False)
        try:
            self.iconbitmap(ensure_ico())
        except Exception:
            pass
        self.themed = False
        try:
            import sv_ttk
            sv_ttk.set_theme(self.theme)
            self.themed = True
        except Exception:
            pass
        self.build()
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.tray = self.make_tray()
        self.refresh_agents()
        self.after(250, self.poll)
        if not hidden:
            self.show()

    # ---- layout

    def build(self):
        cfg = fin.load_cfg()
        root = ttk.Frame(self, padding=(22, 14, 22, 14))
        root.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        r = 0

        head = ttk.Frame(root)
        head.grid(row=r, column=0, sticky="ew")
        try:
            from PIL import Image, ImageTk
            self.logo = ImageTk.PhotoImage(Image.open(fin.ICON).resize((44, 44), Image.LANCZOS))
            ttk.Label(head, image=self.logo).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        except Exception:
            pass
        ttk.Label(head, text="finished", font=("Segoe UI Semibold", 20)).grid(row=0, column=1, sticky="w")
        ttk.Label(head, text="Your AI agents tell you when they're done, out loud.",
                  foreground="#8a8a8a").grid(row=1, column=1, sticky="w")
        ttk.Label(head, text="●  On", foreground="#2fbf71",
                  font=("Segoe UI Semibold", 10)).grid(row=0, column=2, sticky="ne", padx=(24, 0))
        head.columnconfigure(1, weight=1)
        r += 1

        def section(title, hint=None):
            nonlocal r
            ttk.Label(root, text=title, font=("Segoe UI Semibold", 11)).grid(row=r, column=0, sticky="w", pady=(12, 2))
            r += 1
            if hint:
                ttk.Label(root, text=hint, foreground="#8a8a8a").grid(row=r, column=0, sticky="w", pady=(0, 4))
                r += 1

        # Voice
        section("Voice", "Local voices work offline. Online voices need internet.")
        row = ttk.Frame(root)
        row.grid(row=r, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        self.voice_names = ([n for n, v in fin.VOICES.items() if v["lang"] == "en"]
                            + sorted((n for n, v in fin.VOICES.items() if v["lang"] != "en"),
                                     key=lambda n: (fin.lang_name(fin.VOICES[n]["lang"]), n)))
        self.voice_labels = [self.voice_label(n) for n in self.voice_names]
        self.voice = ttk.Combobox(row, values=self.voice_labels, state="readonly", width=52, height=18)
        self.voice.set(self.voice_label(cfg["voice"]))
        self.voice.grid(row=0, column=0, sticky="ew")
        self.voice.bind("<<ComboboxSelected>>", lambda e: self.on_voice())
        ttk.Button(row, text="▶  Listen", command=self.listen).grid(row=0, column=1, padx=(8, 0))
        r += 1

        # What to say
        section("What to say")
        self.mode = tk.StringVar(value=cfg["mode"])
        row = ttk.Frame(root)
        row.grid(row=r, column=0, sticky="w")
        for i, (val, text) in enumerate((("agent", "Agent's message"), ("preset", "Ready phrase"), ("both", "Both"))):
            ttk.Radiobutton(row, text=text, value=val, variable=self.mode,
                            command=lambda: self.save(mode=self.mode.get())).grid(row=0, column=i, padx=(0, 18))
        r += 1
        row = ttk.Frame(root)
        row.grid(row=r, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(row, text="Ready phrase").grid(row=0, column=0, padx=(0, 10))
        self.phrase = ttk.Combobox(row, values=fin.PHRASES, width=30)
        self.phrase.set(cfg["phrase"])
        self.phrase.grid(row=0, column=1, sticky="w")
        for ev in ("<<ComboboxSelected>>", "<Return>", "<FocusOut>"):
            self.phrase.bind(ev, lambda e: self.on_phrase())
        r += 1

        # Read aloud
        section("Read aloud")
        self.speak = tk.StringVar(value=cfg.get("speak", "all"))
        self.speak_main = ttk.Radiobutton(root, value="main", variable=self.speak,
                                          command=lambda: self.save(speak="main"))
        self.speak_main.grid(row=r, column=0, sticky="w")
        r += 1
        ttk.Radiobutton(root, text="Every language in a native voice (some sound robotic)", value="all",
                        variable=self.speak, command=lambda: self.save(speak="all")).grid(row=r, column=0, sticky="w")
        r += 1
        row = ttk.Frame(root)
        row.grid(row=r, column=0, sticky="w", pady=(8, 0))
        ttk.Label(row, text="Agents write in").grid(row=0, column=0, padx=(0, 10))
        self.detect = ttk.Entry(row, width=16)
        self.detect.insert(0, "all" if cfg["detect"] == "all" else ", ".join(cfg["detect"]))
        self.detect.grid(row=0, column=1)
        self.detect.bind("<Return>", lambda e: self.on_detect())
        self.detect.bind("<FocusOut>", lambda e: self.on_detect())
        self.detect_hint = ttk.Label(row, text="language codes, e.g. en, sr  (or all)", foreground="#8a8a8a")
        self.detect_hint.grid(row=0, column=2, padx=(10, 0))
        self.update_speak_label()
        r += 1

        # Volume and switches
        section("Sound and notification")
        row = ttk.Frame(root)
        row.grid(row=r, column=0, sticky="ew")
        ttk.Label(row, text="Volume").grid(row=0, column=0, padx=(0, 10))
        self.volume = tk.IntVar(value=cfg["volume"])
        self.volume_text = ttk.Label(row, text=f"{cfg['volume']}%", width=5)
        scale = ttk.Scale(row, from_=0, to=200, length=300, variable=self.volume,
                          command=lambda v: self.volume_text.config(text=f"{int(float(v))}%"))
        scale.grid(row=0, column=1)
        scale.bind("<ButtonRelease-1>", lambda e: self.save(volume=int(self.volume.get())))
        self.volume_text.grid(row=0, column=2, padx=(8, 0))
        r += 1
        row = ttk.Frame(root)
        row.grid(row=r, column=0, sticky="w", pady=(8, 0))
        self.sound = tk.BooleanVar(value=cfg["sound"])
        self.toast = tk.BooleanVar(value=cfg["toast"])
        self.boot = tk.BooleanVar(value=autostart())
        style = "Switch.TCheckbutton" if self.themed else "TCheckbutton"
        ttk.Checkbutton(row, text="Speak", variable=self.sound, style=style,
                        command=lambda: self.save(sound=self.sound.get())).grid(row=0, column=0, padx=(0, 18))
        ttk.Checkbutton(row, text="Show notification", variable=self.toast, style=style,
                        command=lambda: self.save(toast=self.toast.get())).grid(row=0, column=1, padx=(0, 18))
        ttk.Checkbutton(row, text="Start with Windows", variable=self.boot, style=style,
                        command=lambda: autostart(self.boot.get())).grid(row=0, column=2)
        r += 1

        # Agents
        section("Agents", "✓ tool = can call finished · auto = speaks when a turn ends · rule = told to use it")
        self.agents_box = ttk.Frame(root)
        self.agents_box.grid(row=r, column=0, sticky="ew")
        r += 1
        row = ttk.Frame(root)
        row.grid(row=r, column=0, sticky="w", pady=(8, 0))
        ttk.Button(row, text="Connect agents", command=lambda: self.agents_action(False)).grid(row=0, column=0)
        ttk.Button(row, text="Disconnect", command=lambda: self.agents_action(True)).grid(row=0, column=1, padx=(8, 0))
        r += 1

        # Bottom
        ttk.Separator(root).grid(row=r, column=0, sticky="ew", pady=(18, 12))
        r += 1
        row = ttk.Frame(root)
        row.grid(row=r, column=0, sticky="ew")
        row.columnconfigure(1, weight=1)
        ttk.Button(row, text="Send test notification", style="Accent.TButton" if self.themed else "TButton", command=self.test).grid(row=0, column=0)
        link = ttk.Label(row, text=f"v{fin.VERSION} · GitHub", foreground="#8a8a8a", cursor="hand2")
        link.grid(row=0, column=1, sticky="e", padx=12)
        link.bind("<Button-1>", lambda e: webbrowser.open(REPO))
        ttk.Button(row, text="Quit finished", command=self.quit_app).grid(row=0, column=2)
        r += 1
        ttk.Label(root, text="Closing this window keeps finished on in the tray. Quit turns it off.",
                  foreground="#8a8a8a").grid(row=r, column=0, sticky="w", pady=(10, 0))

    def voice_label(self, name):
        v = fin.VOICES[name]
        return f"{name}  —  {v['d']}"

    def update_speak_label(self):
        lang = fin.lang_name(fin.VOICES[fin.load_cfg()["voice"]]["lang"])
        self.speak_main.config(text=f"Only {lang}, other languages say the ready phrase (best quality)")

    # ---- actions

    def save(self, warm=False, **changes):
        cfg = fin.load_cfg()
        cfg.update(changes)
        fin.save_cfg(cfg)
        if warm:
            fin.spawn({"warm": True})

    def on_voice(self):
        name = self.voice_names[self.voice_labels.index(self.voice.get())]
        self.save(warm=True, voice=name)
        self.update_speak_label()

    def on_phrase(self):
        text = self.phrase.get().strip()
        if text and text != fin.load_cfg()["phrase"]:
            self.save(warm=True, phrase=text)

    def on_detect(self):
        codes = fin.parse_codes(self.detect.get())
        if codes is None:
            self.detect_hint.config(text="unknown code - see finished languages", foreground="#e5534b")
            return
        self.detect_hint.config(text="language codes, e.g. en, sr  (or all)", foreground="#8a8a8a")
        if codes != fin.load_cfg()["detect"]:
            self.save(detect=codes)

    def background(self, work, done=None):
        def run():
            result = work()
            if done:
                self.events.put(("call", lambda: done(result)))
        threading.Thread(target=run, daemon=True).start()

    def listen(self):
        name = self.voice_names[self.voice_labels.index(self.voice.get())]
        cfg = fin.load_cfg()
        sample = fin.SAMPLES.get(fin.VOICES[name]["lang"], fin.SAMPLES["en"])

        def work():
            path = fin.synth(fin.short_text(sample, 30), name, cfg)
            if path:
                fin.play([path])
        self.background(work)

    def test(self):
        fin.spawn({"message": "This is how finished sounds when an agent is done.", "agent": "finished",
                   "language": "en"})

    def refresh_agents(self):
        import agents

        def done(rows):
            for w in self.agents_box.winfo_children():
                w.destroy()
            for i, (name, installed, parts) in enumerate(rows):
                cell = (i // 2, (i % 2) * 2)  # two columns
                ttk.Label(self.agents_box, text=agents.LABELS.get(name, name), width=13).grid(
                    row=cell[0], column=cell[1], sticky="w")
                if not installed:
                    text, color = "not installed", "#8a8a8a"
                elif all(parts.values()):
                    text, color = "   ".join(f"✓ {p}" for p in parts), "#2fbf71"
                else:
                    text = "   ".join(("✓ " if ok else "✗ ") + p for p, ok in parts.items())
                    color = "#e5a50a"
                ttk.Label(self.agents_box, text=text, foreground=color, width=22).grid(
                    row=cell[0], column=cell[1] + 1, sticky="w", padx=(0, 12))
        self.background(agents.status, done)

    def agents_action(self, remove):
        if remove and not messagebox.askyesno(
                "finished", "Disconnect finished from all agents?\n\nAgents will stop calling it until you connect "
                "them again. Every changed file is backed up first.", parent=self):
            return
        import contextlib
        import io
        import agents

        def work():
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                agents.connect(["all"], remove=remove)
            return out.getvalue()

        def done(text):
            self.refresh_agents()
            messagebox.showinfo("finished", text.strip() + ("" if remove else "\n\nRestart your agents to load it."),
                                parent=self)
        self.background(work, done)

    # ---- window and tray

    def show(self):
        if not getattr(self, "placed", False):  # first time: centre it, top kept on screen
            self.placed = True
            self.update_idletasks()
            w, h = self.winfo_reqwidth(), self.winfo_reqheight()
            x = (self.winfo_screenwidth() - w) // 2
            y = max(0, (self.winfo_screenheight() - h) // 2 - 30)
            self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.update_idletasks()
        if self.theme == "dark":
            try:  # dark title bar on Windows 10/11
                hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
            except Exception:
                pass
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def hide(self):
        self.withdraw()
        if not self.told_tray:
            self.told_tray = True
            try:
                fin.show_toast("finished is still on", "It keeps running in the tray. Quit it there to turn it off.")
            except OSError:
                pass

    def make_tray(self):
        try:
            import pystray
            from PIL import Image
        except ImportError:
            return None

        def put(event):
            return lambda icon, item: self.events.put((event, None))

        menu = pystray.Menu(
            pystray.MenuItem("Open finished", put("show"), default=True),
            pystray.MenuItem("Send test notification", put("test")),
            pystray.MenuItem("Speak", put("toggle_sound"), checked=lambda item: fin.load_cfg()["sound"]),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit finished", put("quit")),
        )
        icon = pystray.Icon("finished", Image.open(fin.ICON), "finished — on", menu)
        icon.run_detached()
        return icon

    def poll(self):
        while not self.events.empty():
            event, arg = self.events.get()
            if event == "show":
                self.show()
            elif event == "test":
                self.test()
            elif event == "toggle_sound":
                self.sound.set(not fin.load_cfg()["sound"])
                self.save(sound=self.sound.get())
                if self.tray:
                    self.tray.update_menu()
            elif event == "quit":
                self.quit_app()
                return
            elif event == "call":
                arg()
        if take(SHOW_SIGNAL):
            self.show()
        if take(QUIT_SIGNAL):
            self.quit_app(already_off=True)
            return
        self.after(250, self.poll)

    def quit_app(self, already_off=False):
        if not already_off:
            set_enabled(False)
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.destroy()
