"""Read-only: tiny topmost window showing the game's internal area number for the hunter.

Source: +0x526 of any large monster (tracks the hunter's area); falls back to the
+0x527 area of small monsters (they only exist in the hunter's area).
"""
import sys, threading, time
from collections import Counter
import tkinter as tk
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from mh3u_mem import Proc
from names import LARGE, SMALL

p = Proc()
state = {"text": "…", "ents": []}


def scan():
    while True:
        try:
            state["ents"] = p.find_monsters()
        except (OSError, SystemExit):
            state["ents"] = []
        time.sleep(2)


def current():
    large, small = Counter(), Counter()
    for e in state["ents"]:
        a = e["hp_addr"]
        try:
            if e["id"] in LARGE:
                large[p.read(a + 0x526, 1)[0]] += 1
            elif e["id"] in SMALL and p.u16(a + 4):
                small[p.read(a + 0x527, 1)[0]] += 1
        except OSError:
            pass
    src = large or small
    return src.most_common(1)[0][0] if src else None


root = tk.Tk()
root.title("Area ID")
root.attributes("-topmost", True)
root.geometry("+40+40")
root.configure(bg="#14161a")
lbl = tk.Label(root, font=("Segoe UI", 28, "bold"), bg="#14161a", fg="#5ad16a", padx=24, pady=10)
lbl.pack()
tk.Label(root, text="game's area number", font=("Segoe UI", 10), bg="#14161a", fg="#8a8f98").pack(pady=(0, 8))


def tick():
    a = current()
    lbl.config(text=f"{a}" if a is not None else "?")
    root.after(300, tick)


threading.Thread(target=scan, daemon=True).start()
tick()
root.mainloop()
