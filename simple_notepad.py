"""
Simple Notepad - a lightweight, fully offline text editor for Windows.
Built with Python's standard library only (tkinter) - no internet, no extra installs.

Run:
    python simple_notepad.py

Build a standalone .exe (optional):
    pip install pyinstaller
    pyinstaller --onefile --noconsole --name SimpleNotepad simple_notepad.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont
import os
import sys

APP_NAME = "Simple Notepad"

# ---- Themes ----
LIGHT_THEME = {
    "bg": "#ffffff", "fg": "#000000", "insert": "#000000",
    "select_bg": "#3399FF", "select_fg": "#ffffff",
    "status_bg": "#f0f0f0", "status_fg": "#000000",
}
DARK_THEME = {
    "bg": "#1e1e1e", "fg": "#d4d4d4", "insert": "#ffffff",
    "select_bg": "#264f78", "select_fg": "#ffffff",
    "status_bg": "#2d2d2d", "status_fg": "#d4d4d4",
}


class SimpleNotepad:
    def __init__(self, root, startup_file=None):
        self.root = root
        self.current_file = None
        self.font_size = 12
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
        self.root.geometry("900x650")
        self.root.minsize(400, 300)

        # Text area + scrollbars
        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True)

        self.text_font = tkfont.Font(family="Consolas", size=self.font_size)
        self.text = tk.Text(container, undo=True, wrap="word", font=self.text_font)
        self.text.pack(side="left", fill="both", expand=True)

        self.vscroll = tk.Scrollbar(container, command=self.text.yview)
        self.vscroll.pack(side="right", fill="y")
        self.text.config(yscrollcommand=self.vscroll.set)

        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", self._update_status)
        self.text.bind("<ButtonRelease>", self._update_status)

        # Status bar
        self.status = tk.Label(
            self.root, anchor="e", padx=10,
            text="Ln 1, Col 0    |    0 words, 0 chars"
        )
        self.status.pack(side="bottom", fill="x")

        self._build_menu()

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", accelerator="Ctrl+N", command=self.new_file)
        file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_file)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_file)
        file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=lambda: self.text.event_generate("<<Undo>>"))
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=lambda: self.text.event_generate("<<Redo>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=lambda: self.text.event_generate("<<Cut>>"))
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=lambda: self.text.event_generate("<<Copy>>"))
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=lambda: self.text.event_generate("<<Paste>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Find & Replace...", accelerator="Ctrl+H", command=self.open_find_replace)
        edit_menu.add_command(label="Select All", accelerator="Ctrl+A", command=self.select_all)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        self.wrap_var = tk.BooleanVar(value=True)
        view_menu.add_checkbutton(label="Word Wrap", variable=self.wrap_var, command=self.toggle_wrap)
        view_menu.add_separator()
        view_menu.add_command(label="Zoom In", accelerator="Ctrl++", command=lambda: self.change_font_size(1))
        view_menu.add_command(label="Zoom Out", accelerator="Ctrl+-", command=lambda: self.change_font_size(-1))
        view_menu.add_command(label="Reset Zoom", accelerator="Ctrl+0", command=self.reset_font_size)
        view_menu.add_separator()
        self.dark_var = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(label="Night Mode", accelerator="Ctrl+M", variable=self.dark_var, command=self.toggle_night_mode)
        menubar.add_cascade(label="View", menu=view_menu)

        self.root.config(menu=menubar)

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
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- File operations ----------
    def new_file(self):
        if not self._confirm_discard_changes():
            return
        self.text.delete("1.0", "end")
        self.current_file = None
        self.text.edit_modified(False)
        self._update_title()
        self._update_status()

    def open_file(self):
        if not self._confirm_discard_changes():
            return
        path = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not path:
            return
        self._load_file(path)

    def _load_file(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open file:\n{e}")
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
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
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not path:
            return
        self._write_to_path(path)
        self.current_file = path
        self._update_title()

    def _write_to_path(self, path):
        try:
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
        FindReplaceDialog(self.root, self.text)

    # ---------- View helpers ----------
    def toggle_wrap(self):
        self.wrap_enabled = self.wrap_var.get()
        self.text.config(wrap="word" if self.wrap_enabled else "none")

    def change_font_size(self, delta):
        self.font_size = max(6, min(72, self.font_size + delta))
        self.text_font.configure(size=self.font_size)

    def reset_font_size(self):
        self.font_size = 12
        self.text_font.configure(size=self.font_size)

    def toggle_night_mode(self, from_shortcut=False):
        if from_shortcut:
            self.dark_mode = not self.dark_mode
            self.dark_var.set(self.dark_mode)
        else:
            self.dark_mode = self.dark_var.get()
        self._apply_theme()

    def _apply_theme(self):
        theme = DARK_THEME if self.dark_mode else LIGHT_THEME
        self.text.config(
            bg=theme["bg"], fg=theme["fg"],
            insertbackground=theme["insert"],
            selectbackground=theme["select_bg"],
            selectforeground=theme["select_fg"],
        )
        self.status.config(bg=theme["status_bg"], fg=theme["status_fg"])
        self.root.config(bg=theme["status_bg"])

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


class FindReplaceDialog(tk.Toplevel):
    def __init__(self, parent, text_widget):
        super().__init__(parent)
        self.text = text_widget
        self.title("Find & Replace")
        self.resizable(False, False)
        self.transient(parent)

        tk.Label(self, text="Find:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(self, text="Replace:").grid(row=1, column=0, sticky="e", padx=5, pady=5)

        self.find_entry = tk.Entry(self, width=30)
        self.find_entry.grid(row=0, column=1, padx=5, pady=5)
        self.replace_entry = tk.Entry(self, width=30)
        self.replace_entry.grid(row=1, column=1, padx=5, pady=5)

        btn_frame = tk.Frame(self)
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
        self.text.tag_config("found", background="yellow")
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
