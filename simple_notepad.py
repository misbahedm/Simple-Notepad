"""
Simple Notepad - a lightweight, offline text editor for Windows.
Built with Python's standard library only (tkinter) - no internet, no extra installs.

Features:
    - New / Open / Save / Save As (.txt and .rtf)
    - Undo/redo, cut/copy/paste, find & replace
    - Word wrap, zoom
    - Bold / Italic / Underline / font family / font size / text color / highlight
    - Full-window night mode (menus, scrollbar, status bar, and Windows title bar)
    - Opens a file passed on the command line, so it can be set as the
      default Windows app for .txt files (see bottom of this file for how)

Run:
    python simple_notepad.py

Build a standalone .exe (optional):
    pip install pyinstaller
    pyinstaller --onefile --noconsole --name SimpleNotepad simple_notepad.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont, colorchooser, ttk
import os
import sys
import re

APP_NAME = "Simple Notepad"

# ---------------- Themes ----------------
LIGHT_THEME = {
    "bg": "#ffffff", "fg": "#000000", "insert": "#000000",
    "select_bg": "#3399FF", "select_fg": "#ffffff",
    "window_bg": "#f0f0f0", "window_fg": "#000000",
    "status_bg": "#f0f0f0", "status_fg": "#000000",
    "toolbar_bg": "#f0f0f0", "toolbar_fg": "#000000",
    "menu_bg": "#f0f0f0", "menu_fg": "#000000",
    "menu_active_bg": "#3399FF", "menu_active_fg": "#ffffff",
    "trough": "#e0e0e0", "scrollbar": "#c0c0c0",
    "entry_bg": "#ffffff", "entry_fg": "#000000",
}
DARK_THEME = {
    "bg": "#1e1e1e", "fg": "#d4d4d4", "insert": "#ffffff",
    "select_bg": "#264f78", "select_fg": "#ffffff",
    "window_bg": "#252526", "window_fg": "#d4d4d4",
    "status_bg": "#252526", "status_fg": "#d4d4d4",
    "toolbar_bg": "#2d2d2d", "toolbar_fg": "#d4d4d4",
    "menu_bg": "#2d2d2d", "menu_fg": "#d4d4d4",
    "menu_active_bg": "#094771", "menu_active_fg": "#ffffff",
    "trough": "#1e1e1e", "scrollbar": "#3e3e3e",
    "entry_bg": "#3c3c3c", "entry_fg": "#d4d4d4",
}


def set_windows_titlebar_dark(root, enabled: bool):
    """Best-effort: darken the native Windows title bar (Windows 10 1809+/11)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1 if enabled else 0)
        # Try the modern attribute id first, fall back to the older one.
        for attr in (20, 19):
            res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
            )
            if res == 0:
                break
    except Exception:
        pass  # Not on Windows, or OS too old - silently skip.


class SimpleNotepad:
    def __init__(self, root, startup_file=None):
        self.root = root
        self.current_file = None
        self.font_size = 12
        self.font_family = "Consolas"
        self.wrap_enabled = True
        self.dark_mode = False

        self._build_ui()
        self._bind_shortcuts()
        self._apply_theme()
        self._update_title()
        self.text.focus_set()

        if startup_file and os.path.isfile(startup_file):
            self._load_file(startup_file)

    # ---------- UI ----------
    def _build_ui(self):
        self.root.geometry("950x680")
        self.root.minsize(400, 300)

        # ttk style, used for the scrollbar so we can theme it
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.menubar = tk.Menu(self.root, tearoff=0)
        self._build_menu()
        self.root.config(menu=self.menubar)

        self.toolbar = tk.Frame(self.root, bd=0)
        self.toolbar.pack(side="top", fill="x")
        self._build_toolbar()

        container = tk.Frame(self.root, bd=0)
        container.pack(fill="both", expand=True)
        self.container = container

        self.text_font = tkfont.Font(family=self.font_family, size=self.font_size)
        self.text = tk.Text(
            container, undo=True, wrap="word", font=self.text_font,
            relief="flat", bd=0, padx=8, pady=6
        )
        self.text.pack(side="left", fill="both", expand=True)

        self.vscroll = ttk.Scrollbar(container, command=self.text.yview, style="Dark.Vertical.TScrollbar")
        self.vscroll.pack(side="right", fill="y")
        self.text.config(yscrollcommand=self.vscroll.set)

        # Formatting tags
        self.text.tag_configure("bold", font=self._variant_font(bold=True))
        self.text.tag_configure("italic", font=self._variant_font(italic=True))
        self.text.tag_configure("bold_italic", font=self._variant_font(bold=True, italic=True))
        self.text.tag_configure("underline", underline=True)

        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", self._update_status)
        self.text.bind("<ButtonRelease>", self._update_status)

        # Status bar
        self.status = tk.Label(self.root, anchor="e", padx=10, bd=0)
        self.status.pack(side="bottom", fill="x")
        self._update_status()

    def _variant_font(self, bold=False, italic=False):
        f = tkfont.Font(family=self.font_family, size=self.font_size)
        f.configure(weight="bold" if bold else "normal", slant="italic" if italic else "roman")
        return f

    def _build_menu(self):
        file_menu = tk.Menu(self.menubar, tearoff=0)
        file_menu.add_command(label="New", accelerator="Ctrl+N", command=self.new_file)
        file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_file)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_file)
        file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        self.menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(self.menubar, tearoff=0)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=lambda: self.text.event_generate("<<Undo>>"))
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=lambda: self.text.event_generate("<<Redo>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=lambda: self.text.event_generate("<<Cut>>"))
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=lambda: self.text.event_generate("<<Copy>>"))
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=lambda: self.text.event_generate("<<Paste>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Find & Replace...", accelerator="Ctrl+H", command=self.open_find_replace)
        edit_menu.add_command(label="Select All", accelerator="Ctrl+A", command=self.select_all)
        self.menubar.add_cascade(label="Edit", menu=edit_menu)

        format_menu = tk.Menu(self.menubar, tearoff=0)
        format_menu.add_command(label="Bold", accelerator="Ctrl+B", command=self.toggle_bold)
        format_menu.add_command(label="Italic", accelerator="Ctrl+I", command=self.toggle_italic)
        format_menu.add_command(label="Underline", accelerator="Ctrl+U", command=self.toggle_underline)
        format_menu.add_separator()
        format_menu.add_command(label="Text Color...", command=self.pick_text_color)
        format_menu.add_command(label="Highlight Color...", command=self.pick_highlight_color)
        format_menu.add_command(label="Clear Formatting", command=self.clear_formatting)
        self.menubar.add_cascade(label="Format", menu=format_menu)

        view_menu = tk.Menu(self.menubar, tearoff=0)
        self.wrap_var = tk.BooleanVar(value=True)
        view_menu.add_checkbutton(label="Word Wrap", variable=self.wrap_var, command=self.toggle_wrap)
        view_menu.add_separator()
        view_menu.add_command(label="Zoom In", accelerator="Ctrl++", command=lambda: self.change_font_size(1))
        view_menu.add_command(label="Zoom Out", accelerator="Ctrl+-", command=lambda: self.change_font_size(-1))
        view_menu.add_command(label="Reset Zoom", accelerator="Ctrl+0", command=self.reset_font_size)
        view_menu.add_separator()
        self.dark_var = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(label="Night Mode", accelerator="Ctrl+M", variable=self.dark_var, command=self.toggle_night_mode)
        self.menubar.add_cascade(label="View", menu=view_menu)

        self._all_menus = [file_menu, edit_menu, format_menu, view_menu]

    def _build_toolbar(self):
        self.font_families = sorted(tkfont.families())
        common = ["Consolas", "Arial", "Calibri", "Times New Roman", "Courier New", "Segoe UI", "Georgia", "Verdana"]
        family_list = [f for f in common if f in self.font_families] + \
                      [f for f in self.font_families if f not in common]

        self.font_family_var = tk.StringVar(value=self.font_family)
        self.family_combo = ttk.Combobox(
            self.toolbar, textvariable=self.font_family_var, values=family_list,
            width=18, state="readonly"
        )
        self.family_combo.pack(side="left", padx=(6, 2), pady=4)
        self.family_combo.bind("<<ComboboxSelected>>", self.apply_font_family)

        self.font_size_var = tk.StringVar(value=str(self.font_size))
        self.size_combo = ttk.Combobox(
            self.toolbar, textvariable=self.font_size_var,
            values=[str(s) for s in (8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 40)],
            width=4, state="readonly"
        )
        self.size_combo.pack(side="left", padx=2, pady=4)
        self.size_combo.bind("<<ComboboxSelected>>", self.apply_font_size)

        sep1 = tk.Frame(self.toolbar, width=1, bg="#999999")
        sep1.pack(side="left", fill="y", padx=6, pady=4)

        self.bold_btn = tk.Button(self.toolbar, text="B", width=3, font=("Segoe UI", 10, "bold"), command=self.toggle_bold, relief="flat")
        self.bold_btn.pack(side="left", padx=1, pady=4)
        self.italic_btn = tk.Button(self.toolbar, text="I", width=3, font=("Segoe UI", 10, "italic"), command=self.toggle_italic, relief="flat")
        self.italic_btn.pack(side="left", padx=1, pady=4)
        self.underline_btn = tk.Button(self.toolbar, text="U", width=3, font=("Segoe UI", 10, "underline"), command=self.toggle_underline, relief="flat")
        self.underline_btn.pack(side="left", padx=1, pady=4)

        sep2 = tk.Frame(self.toolbar, width=1, bg="#999999")
        sep2.pack(side="left", fill="y", padx=6, pady=4)

        self.color_btn = tk.Button(self.toolbar, text="A", width=3, fg="#cc0000", command=self.pick_text_color, relief="flat")
        self.color_btn.pack(side="left", padx=1, pady=4)
        self.highlight_btn = tk.Button(self.toolbar, text="\u2592", width=3, command=self.pick_highlight_color, relief="flat")
        self.highlight_btn.pack(side="left", padx=1, pady=4)

        self._toolbar_widgets = [self.bold_btn, self.italic_btn, self.underline_btn, self.color_btn, self.highlight_btn]
        self._toolbar_separators = [sep1, sep2]

    def _bind_shortcuts(self):
        self.root.bind("<Control-n>", lambda e: self.new_file())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-S>", lambda e: self.save_file_as())
        self.root.bind("<Control-h>", lambda e: self.open_find_replace())
        self.root.bind("<Control-a>", lambda e: self.select_all())
        self.root.bind("<Control-plus>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-equal>", lambda e: self.change_font_size(1))
        self.root.bind("<Control-minus>", lambda e: self.change_font_size(-1))
        self.root.bind("<Control-0>", lambda e: self.reset_font_size())
        self.root.bind("<Control-m>", lambda e: self.toggle_night_mode(from_shortcut=True))
        self.root.bind("<Control-b>", lambda e: (self.toggle_bold(), "break")[1])
        self.root.bind("<Control-i>", lambda e: (self.toggle_italic(), "break")[1])
        self.root.bind("<Control-u>", lambda e: (self.toggle_underline(), "break")[1])
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- File operations ----------
    def new_file(self):
        if not self._confirm_discard_changes():
            return
        self.text.delete("1.0", "end")
        for tag in self.text.tag_names():
            if tag != "sel":
                self.text.tag_remove(tag, "1.0", "end")
        self.current_file = None
        self.text.edit_modified(False)
        self._update_title()
        self._update_status()

    def open_file(self):
        if not self._confirm_discard_changes():
            return
        path = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("Rich Text Format", "*.rtf"), ("All Files", "*.*")]
        )
        if not path:
            return
        self._load_file(path)

    def _load_file(self, path):
        try:
            if path.lower().endswith(".rtf"):
                self._load_rtf(path)
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self.text.delete("1.0", "end")
                self.text.insert("1.0", content)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open file:\n{e}")
            return
        self.current_file = path
        self.text.edit_modified(False)
        self._update_title()
        self._update_status()

    def save_file(self):
        if self.current_file:
            self._write_to_path(self.current_file)
        else:
            self.save_file_as()

    def save_file_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("Rich Text Format", "*.rtf"), ("All Files", "*.*")]
        )
        if not path:
            return
        self._write_to_path(path)
        self.current_file = path
        self._update_title()

    def _write_to_path(self, path):
        try:
            if path.lower().endswith(".rtf"):
                self._save_rtf(path)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.text.get("1.0", "end-1c"))
            self.text.edit_modified(False)
            self._update_title()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not save file:\n{e}")

    def _confirm_discard_changes(self):
        if not self.text.edit_modified():
            return True
        name = os.path.basename(self.current_file) if self.current_file else "Untitled"
        answer = messagebox.askyesnocancel(
            APP_NAME, f'Do you want to save changes to "{name}"?'
        )
        if answer is None:
            return False
        if answer:
            self.save_file()
            return not self.text.edit_modified()
        return True

    def on_close(self):
        if self._confirm_discard_changes():
            self.root.destroy()

    # ---------- Edit helpers ----------
    def select_all(self):
        self.text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def open_find_replace(self):
        FindReplaceDialog(self.root, self.text, self._current_theme())

    # ---------- Formatting ----------
    def _get_sel_range(self):
        try:
            return self.text.index("sel.first"), self.text.index("sel.last")
        except tk.TclError:
            return None, None

    def toggle_bold(self):
        self._toggle_font_tag("bold")

    def toggle_italic(self):
        self._toggle_font_tag("italic")

    def toggle_underline(self):
        start, end = self._get_sel_range()
        if not start:
            return
        tags_at_start = self.text.tag_names(start)
        currently_on = "underline" in tags_at_start
        if currently_on:
            self.text.tag_remove("underline", start, end)
        else:
            self.text.tag_add("underline", start, end)
        self.text.edit_modified(True)

    def _toggle_font_tag(self, base_tag):
        """Handles bold/italic which combine into bold_italic."""
        start, end = self._get_sel_range()
        if not start:
            return
        tags_at_start = set(self.text.tag_names(start))
        has_bold = "bold" in tags_at_start or "bold_italic" in tags_at_start
        has_italic = "italic" in tags_at_start or "bold_italic" in tags_at_start

        if base_tag == "bold":
            new_bold, new_italic = not has_bold, has_italic
        else:
            new_bold, new_italic = has_bold, not has_italic

        for t in ("bold", "italic", "bold_italic"):
            self.text.tag_remove(t, start, end)

        if new_bold and new_italic:
            self.text.tag_add("bold_italic", start, end)
        elif new_bold:
            self.text.tag_add("bold", start, end)
        elif new_italic:
            self.text.tag_add("italic", start, end)

        self.text.edit_modified(True)

    def pick_text_color(self):
        start, end = self._get_sel_range()
        if not start:
            return
        color = colorchooser.askcolor(title="Text Color")[1]
        if not color:
            return
        tag_name = f"fg_{color.replace('#', '')}"
        self.text.tag_configure(tag_name, foreground=color)
        self.text.tag_add(tag_name, start, end)
        self.text.edit_modified(True)

    def pick_highlight_color(self):
        start, end = self._get_sel_range()
        if not start:
            return
        color = colorchooser.askcolor(title="Highlight Color")[1]
        if not color:
            return
        tag_name = f"bg_{color.replace('#', '')}"
        self.text.tag_configure(tag_name, background=color)
        self.text.tag_add(tag_name, start, end)
        self.text.edit_modified(True)

    def clear_formatting(self):
        start, end = self._get_sel_range()
        if not start:
            return
        for tag in self.text.tag_names():
            if tag != "sel":
                self.text.tag_remove(tag, start, end)
        self.text.edit_modified(True)

    def apply_font_family(self, event=None):
        self.font_family = self.font_family_var.get()
        self.text_font.configure(family=self.font_family)
        self._refresh_variant_fonts()

    def apply_font_size(self, event=None):
        try:
            self.font_size = int(self.font_size_var.get())
        except ValueError:
            return
        self.text_font.configure(size=self.font_size)
        self._refresh_variant_fonts()

    def _refresh_variant_fonts(self):
        self.text.tag_configure("bold", font=self._variant_font(bold=True))
        self.text.tag_configure("italic", font=self._variant_font(italic=True))
        self.text.tag_configure("bold_italic", font=self._variant_font(bold=True, italic=True))

    # ---------- View helpers ----------
    def toggle_wrap(self):
        self.wrap_enabled = self.wrap_var.get()
        self.text.config(wrap="word" if self.wrap_enabled else "none")

    def change_font_size(self, delta):
        self.font_size = max(6, min(72, self.font_size + delta))
        self.text_font.configure(size=self.font_size)
        self.font_size_var.set(str(self.font_size))
        self._refresh_variant_fonts()

    def reset_font_size(self):
        self.font_size = 12
        self.text_font.configure(size=self.font_size)
        self.font_size_var.set(str(self.font_size))
        self._refresh_variant_fonts()

    def toggle_night_mode(self, from_shortcut=False):
        if from_shortcut:
            self.dark_mode = not self.dark_mode
            self.dark_var.set(self.dark_mode)
        else:
            self.dark_mode = self.dark_var.get()
        self._apply_theme()

    def _current_theme(self):
        return DARK_THEME if self.dark_mode else LIGHT_THEME

    def _apply_theme(self):
        t = self._current_theme()

        self.root.config(bg=t["window_bg"])
        self.container.config(bg=t["window_bg"])
        self.toolbar.config(bg=t["toolbar_bg"])

        self.text.config(
            bg=t["bg"], fg=t["fg"],
            insertbackground=t["insert"],
            selectbackground=t["select_bg"],
            selectforeground=t["select_fg"],
        )
        self.status.config(bg=t["status_bg"], fg=t["status_fg"])

        # Toolbar buttons & separators
        for w in self._toolbar_widgets:
            w.config(bg=t["toolbar_bg"], fg=t["toolbar_fg"],
                     activebackground=t["select_bg"], activeforeground=t["select_fg"],
                     highlightthickness=0)
        for s in self._toolbar_separators:
            s.config(bg=t["scrollbar"])

        # ttk combobox styling
        self.style.configure("TCombobox",
                              fieldbackground=t["entry_bg"], background=t["toolbar_bg"],
                              foreground=t["entry_fg"], arrowcolor=t["fg"])
        self.root.option_add("*TCombobox*Listbox.background", t["entry_bg"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["entry_fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["select_bg"])

        # ttk scrollbar styling
        self.style.configure("Dark.Vertical.TScrollbar",
                              background=t["scrollbar"], troughcolor=t["trough"],
                              bordercolor=t["window_bg"], arrowcolor=t["fg"],
                              lightcolor=t["scrollbar"], darkcolor=t["scrollbar"])
        self.style.map("Dark.Vertical.TScrollbar", background=[("active", t["select_bg"])])

        # Menus (tk.Menu respects bg/fg on Windows)
        self.menubar.config(bg=t["menu_bg"], fg=t["menu_fg"],
                             activebackground=t["menu_active_bg"], activeforeground=t["menu_active_fg"])
        for m in self._all_menus:
            m.config(bg=t["menu_bg"], fg=t["menu_fg"],
                     activebackground=t["menu_active_bg"], activeforeground=t["menu_active_fg"])

        set_windows_titlebar_dark(self.root, self.dark_mode)

    # ---------- Status / title ----------
    def _on_modified(self, event=None):
        self._update_title()
        self._update_status()

    def _update_title(self):
        name = os.path.basename(self.current_file) if self.current_file else "Untitled"
        star = "*" if self.text.edit_modified() else ""
        self.root.title(f"{star}{name} - {APP_NAME}")

    def _update_status(self, event=None):
        content = self.text.get("1.0", "end-1c")
        words = len(content.split())
        chars = len(content)
        line, col = self.text.index("insert").split(".")
        self.status.config(text=f"Ln {line}, Col {col}    |    {words} words, {chars} chars")
        self._update_title()

    # ---------- Minimal RTF export/import (covers bold/italic/underline/color/font) ----------
    def _save_rtf(self, path):
        colors = ["\\red0\\green0\\blue0;"]  # index 0 reserved (auto)
        color_index = {}

        def color_idx(hexcolor):
            if hexcolor not in color_index:
                r = int(hexcolor[1:3], 16)
                g = int(hexcolor[3:5], 16)
                b = int(hexcolor[5:7], 16)
                colors.append(f"\\red{r}\\green{g}\\blue{b};")
                color_index[hexcolor] = len(colors) - 1
            return color_index[hexcolor]

        body_parts = []
        index = "1.0"
        end_index = self.text.index("end-1c")
        while self.text.compare(index, "<", end_index):
            next_index = self.text.index(f"{index}+1c")
            ch = self.text.get(index, next_index)
            tags = self.text.tag_names(index)

            bold = "bold" in tags or "bold_italic" in tags
            italic = "italic" in tags or "bold_italic" in tags
            underline = "underline" in tags
            fg_hex = next((t[3:] for t in tags if t.startswith("fg_")), None)
            bg_hex = next((t[3:] for t in tags if t.startswith("bg_")), None)

            run = ""
            if bold:
                run += "\\b "
            if italic:
                run += "\\i "
            if underline:
                run += "\\ul "
            if fg_hex:
                run += f"\\cf{color_idx('#' + fg_hex)} "
            if bg_hex:
                run += f"\\highlight{color_idx('#' + bg_hex)} "

            if ch == "\n":
                escaped = "\\par\n"
            elif ch in ("\\", "{", "}"):
                escaped = "\\" + ch
            elif ord(ch) > 127:
                escaped = f"\\u{ord(ch)}?"
            else:
                escaped = ch

            body_parts.append(f"{{{run}{escaped}}}" if run else escaped)
            index = next_index

        color_table = "{\\colortbl;" + "".join(colors[1:]) + "}" if len(colors) > 1 else ""
        rtf = (
            "{\\rtf1\\ansi\\deff0"
            "{\\fonttbl{\\f0 " + self.font_family + ";}}"
            + color_table +
            f"\\f0\\fs{self.font_size * 2} "
            + "".join(body_parts) +
            "}"
        )
        with open(path, "w", encoding="ascii", errors="replace") as f:
            f.write(rtf)

    def _load_rtf(self, path):
        """Minimal RTF reader for files this app produced (best-effort for others)."""
        with open(path, "r", encoding="ascii", errors="replace") as f:
            raw = f.read()

        self.text.delete("1.0", "end")
        for tag in list(self.text.tag_names()):
            if tag not in ("sel", "bold", "italic", "bold_italic", "underline"):
                self.text.tag_delete(tag)

        # Strip header groups we don't render (font table, color table)
        body = re.sub(r"\{\\fonttbl.*?\}\}", "", raw, flags=re.S)
        body = re.sub(r"\{\\colortbl.*?\}", "", body, flags=re.S)
        body = re.sub(r"^\{\\rtf1[^\n]*", "", body)

        pos_i = 0
        n = len(body)
        bold = italic = underline = False
        while pos_i < n:
            c = body[pos_i]
            if c in "{}":
                pos_i += 1
                continue
            if c == "\\":
                m = re.match(r"\\(par\b|b\b|i\b|ul\b|u(\d+)\?|\\|\{|\})", body[pos_i:])
                if m:
                    tok = m.group(1)
                    pos_i += m.end()
                    if body[pos_i:pos_i + 1] == " ":
                        pos_i += 1
                    if tok == "par":
                        self._insert_char("\n", bold, italic, underline)
                    elif tok == "b":
                        bold = True
                    elif tok == "i":
                        italic = True
                    elif tok == "ul":
                        underline = True
                    elif tok.startswith("u"):
                        code = int(m.group(2))
                        self._insert_char(chr(code), bold, italic, underline)
                    elif tok in ("\\", "{", "}"):
                        self._insert_char(tok, bold, italic, underline)
                    continue
                else:
                    m2 = re.match(r"\\[a-zA-Z]+-?\d*", body[pos_i:])
                    if m2:
                        pos_i += m2.end()
                        if body[pos_i:pos_i + 1] == " ":
                            pos_i += 1
                        continue
                    pos_i += 1
                    continue
            else:
                self._insert_char(c, bold, italic, underline)
                pos_i += 1

    def _insert_char(self, ch, bold, italic, underline):
        idx = self.text.index("end-1c")
        self.text.insert("end", ch)
        end_idx = self.text.index("end-1c")
        if bold and italic:
            self.text.tag_add("bold_italic", idx, end_idx)
        elif bold:
            self.text.tag_add("bold", idx, end_idx)
        elif italic:
            self.text.tag_add("italic", idx, end_idx)
        if underline:
            self.text.tag_add("underline", idx, end_idx)


class FindReplaceDialog(tk.Toplevel):
    def __init__(self, parent, text_widget, theme):
        super().__init__(parent)
        self.text = text_widget
        self.title("Find & Replace")
        self.resizable(False, False)
        self.transient(parent)
        self.config(bg=theme["window_bg"])

        tk.Label(self, text="Find:", bg=theme["window_bg"], fg=theme["window_fg"]).grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(self, text="Replace:", bg=theme["window_bg"], fg=theme["window_fg"]).grid(row=1, column=0, sticky="e", padx=5, pady=5)

        self.find_entry = tk.Entry(self, width=30, bg=theme["entry_bg"], fg=theme["entry_fg"], insertbackground=theme["window_fg"])
        self.find_entry.grid(row=0, column=1, padx=5, pady=5)
        self.replace_entry = tk.Entry(self, width=30, bg=theme["entry_bg"], fg=theme["entry_fg"], insertbackground=theme["window_fg"])
        self.replace_entry.grid(row=1, column=1, padx=5, pady=5)

        btn_frame = tk.Frame(self, bg=theme["window_bg"])
        btn_frame.grid(row=2, column=0, columnspan=2, pady=5)

        tk.Button(btn_frame, text="Find Next", command=self.find_next).pack(side="left", padx=3)
        tk.Button(btn_frame, text="Replace", command=self.replace_one).pack(side="left", padx=3)
        tk.Button(btn_frame, text="Replace All", command=self.replace_all).pack(side="left", padx=3)

        self.find_entry.focus_set()
        self._last_index = "1.0"

    def find_next(self):
        self.text.tag_remove("found", "1.0", "end")
        needle = self.find_entry.get()
        if not needle:
            return
        idx = self.text.search(needle, self._last_index, stopindex="end")
        if not idx:
            idx = self.text.search(needle, "1.0", stopindex="end")
            if not idx:
                messagebox.showinfo("Find", f'Cannot find "{needle}"')
                return
        end_idx = f"{idx}+{len(needle)}c"
        self.text.tag_add("found", idx, end_idx)
        self.text.tag_config("found", background="yellow", foreground="black")
        self.text.mark_set("insert", end_idx)
        self.text.see(idx)
        self._last_index = end_idx

    def replace_one(self):
        needle = self.find_entry.get()
        replacement = self.replace_entry.get()
        if not needle:
            return
        sel_ranges = self.text.tag_ranges("found")
        if sel_ranges:
            self.text.delete(sel_ranges[0], sel_ranges[1])
            self.text.insert(sel_ranges[0], replacement)
        self.find_next()

    def replace_all(self):
        needle = self.find_entry.get()
        replacement = self.replace_entry.get()
        if not needle:
            return
        content = self.text.get("1.0", "end-1c")
        count = content.count(needle)
        if count == 0:
            messagebox.showinfo("Replace All", f'Cannot find "{needle}"')
            return
        new_content = content.replace(needle, replacement)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", new_content)
        messagebox.showinfo("Replace All", f"Replaced {count} occurrence(s).")


def main():
    startup_file = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    app = SimpleNotepad(root, startup_file=startup_file)
    root.mainloop()


if __name__ == "__main__":
    main()
