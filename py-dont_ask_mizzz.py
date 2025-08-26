#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Don't Ask Mizzz – ( Quiz )“
Source: github.com/py-dont_ask_mizzz
"""

import json
import os
import random
import re
import sys
import threading
import queue
import colorsys
import tkinter as tk

# ---------- 1) Freche Rückmeldungen ----------
CORRECT_RESPONSES = [
    "Genau, du Wissens-Rampensau!",
    "Zack! Korrekt wie ein Schweizer Uhrwerk auf Espresso!",
    "Richtig! Wenn du so weitermachst, wirst du mein Endgegner.",
    "Stimmt. Ich geb’s ungern zu, aber das war gut.",
    "Bravo! Das tat sogar mir ein bisschen weh, so gut war’s.",
    "Korrekt! Du bist entweder klug – oder sehr gut im Raten.",
    "Perfekt! Ich notiere: Gefährlich belesen.",
    "Richtig! Ich hege leichten Verdacht auf Google… Spaß. Oder?",
    "Jo, passt! Heute bist du on fire.",
    "Richtig! Und nein, es gibt dafür keine Paywall.",
    "Halt mich fest – das war astrein.",
    "Du bist der Endgegner der Fragen.",
    "So präzise, ich hör’ die Winkelmesser klatschen.",
    "Richtiger als eine Bahnhofsuhr.",
    "Korrekt wie ein frisch gezogener Scheitel.",
    "Du hast das Fragezeichen domestiziert.",
    "Das war chirurgisch.",
    "Quiz-Yoga: alles sitzt.",
    "Fehlerquote: 0 %. Eiskalt.",
    "Ich würd’ dir ’nen Orden basteln – mit Glitzer."
]

WRONG_RESPONSES = [
    "Uff. Das war so daneben, das Navi weigert sich, neu zu routen.",
    "Nope! Das war ein Griff ins Datenklo.",
    "Nein. Aber mutig. Also… sehr mutig.",
    "Fast! Also… wenn 'fast' bedeuten würde: 'nicht'.",
    "Schade! Ich hab kurz gehofft – und dann deine Antwort gesehen.",
    "Autsch. Das war ein Tritt in die Synapsen.",
    "Negativ! Vielleicht erstmal Kaffee? Oder zwei.",
    "Nope! Selbst der Zufall würfelt heute gegen dich.",
    "Nicht richtig. Aber hey – Charakterbildung!",
    "Nein. Doch. Ohhh.. Aber im ernst - Das war sowas von daneben. Haha.",
    "Ui. Das war ein Luftloch.",
    "Fiip. Falsch das war wohl ein Gehirnfurz.",
    "Falscher Zug, falscher Bahnhof, ohne Bahnsteigkarte.",
    "Das war mehr Kunst als Wissen – leider moderne.",
    "Kunst ist nicht alles aber alles ist Kunst. Leider trifft das nicht auf deine Antwort zu.",
    "Echt jetzt ? Ist das dein ernst ? - NEIN!",
    "Nope. Aber die Pose war stark.",
    "Leg dich bitte wieder hin, schlaf nochmal drüber oder trink nen Kaffee und wach auf, das war ja mal sowas von inkorrekt, mehr geht nicht.",
    "Ich buche dich unter ‚kreativ‘.",
    "Dein Bauchgefühl will wahrscheinlich mit dem Hirn reden. L.O.L",
    "Das war so falsch, dass es schon wieder charmant ist.",
    "Knapp wie eine Billigjeans, sehr sehr eng.",
    "Völlig falsch aber mach dir nichts draus. Ist nicht tragisch – ich hab’ noch mehr Fragen die dich aufwühlen werden.",
    "Faul im Mittelfeld. Rote Karte. Freistoß für die Realität."
]

# ---------- 2) Datenpfad ----------
SCRIPT_DIR = os.path.dirname(__file__)

def resource_path(rel: str) -> str:
    """Return absolute path to resource, works for dev and PyInstaller onefile."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, rel)
    return os.path.join(SCRIPT_DIR, rel)

# Session log (per run): store asked question filenames; auto-cleared on start
import tempfile
SESSION_FILE = os.path.join(tempfile.gettempdir(), "dont_ask_mizzz_session.json")

DATA_DIR = resource_path("data")

# ---------- 3) TTS Worker ----------
class SpeechWorker:
    """
    Start/Stop-fähiger TTS-Worker für SAPI (Windows).
    - say_sequence(texts, on_done): spricht ALLE Texte in Reihenfolge vollständig,
      wartet intern (WaitUntilDone) und ruft danach on_done im GUI-Thread.
    - Neue Sequenz purgt vorher die SAPI-Queue.
    """
    def __init__(self, tk_root: tk.Tk):
        self.tk_root = tk_root
        self._q = queue.Queue()
        self._th = threading.Thread(target=self._run, daemon=True)
        self._stop = threading.Event()
        self._th.start()

    def say_sequence(self, texts, on_done=None):
        self._q.put(("SEQ", list(texts), on_done))

    def stop(self):
        self._stop.set()
        self._q.put(("STOP", None, None))

    @staticmethod
    def _normalize(text: str) -> str:
        # Umlaute/ß + leichte Heuristiken für robustere deutsche TTS
        mapping = [
            ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"),
            ("ä", "ae"), ("ö", "oe"), ("ü", "ue"),
            ("ß", "ss"),
            (r"\bUI\b", "User Interface"),
            (r"\bIT\b", "Ih Tee"),
            (r"qu", "kw"), (r"Qu", "Kw"),
            (r"tion\b", "tzion"),
            (r"sion\b", "ssion"),
        ]
        out = text
        for pat, rep in mapping:
            out = re.sub(pat, rep, out)
        # Dekor/ASCII, die SAPI sonst wörtlich als „gleich“ und Co. liest, entfernen:
        out = re.sub(r"[=\-\_\*\#~^`]+", " ", out)
        # Emojis/Non-ASCII streichen (SAPI stolpert teils)
        out = re.sub(r"[^\x00-\x7F]", " ", out)
        out = re.sub(r"\s{2,}", " ", out)
        return out.strip()

    def _run(self):
        try:
            import win32com.client
            tts = win32com.client.Dispatch("SAPI.SpVoice")
            SVS_ASYNC = 1      # SVSFlagsAsync
            SVS_PURGE = 2      # SVSFPurgeBeforeSpeak
        except Exception:
            tts = None
            SVS_ASYNC = 0
            SVS_PURGE = 0

        while not self._stop.is_set():
            try:
                kind, payload, on_done = self._q.get(timeout=0.2)
            except queue.Empty:
                continue

            if kind == "STOP":
                break

            if kind == "SEQ":
                texts = payload or []
                if not tts:
                    if on_done:
                        self.tk_root.after(0, on_done)
                    continue
                try:
                    # Purge bevor wir starten
                    tts.Speak("", SVS_ASYNC | SVS_PURGE)
                except Exception:
                    pass
                try:
                    for raw in texts:
                        clean = self._normalize(raw)
                        if not clean:
                            continue
                        # Asynchron queue'n, dann blockierend warten bis fertig
                        tts.Speak(clean, SVS_ASYNC)
                        tts.WaitUntilDone(0x7fffffff)  # blockt bis fertig (siehe SAPI)  # noqa
                except Exception:
                    pass
                finally:
                    if on_done:
                        self.tk_root.after(0, on_done)

# ---------- 4) Gradient-Animator (oben farbig → unten schwarz) ----------
class GradientAnimator:
    def __init__(self, canvas: tk.Canvas, fps: int = 30):
        self.canvas = canvas
        self.fps = max(10, min(60, fps))
        self.tag = "bg"
        # Hues über Blau/Violett hinaus auch Grün/Orange/Rot:
        self.keys = [
            (0.60, 0.75, 0.22),  # Türkis/Blau
            (0.66, 0.75, 0.22),  # Kaltblau
            (0.72, 0.70, 0.22),  # Violett
            (0.33, 0.70, 0.22),  # Grün
            (0.08, 0.80, 0.24),  # Orange
            (0.00, 0.78, 0.24),  # Rot
            (0.64, 0.75, 0.22),  # zurück Richtung Blau
        ]
        self.idx = 0
        self.t = 0.0
        self.duration = 6.0

    def _lerp(self, a, b, t): return a + (b - a) * t

    def _hsl_to_hex(self, h, s, l):
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    def _draw_gradient(self, w: int, h: int, top_hex: str):
        self.canvas.delete(self.tag)
        def hex_to_rgb(hx):
            hx = hx.lstrip("#")
            return tuple(int(hx[i:i+2], 16) for i in (0,2,4))
        def rgb_to_hex(rgb):
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        r1,g1,b1 = hex_to_rgb(top_hex)
        r2,g2,b2 = (0,0,0)
        for y in range(h):
            ty = y / max(1, (h-1))
            r = int(self._lerp(r1, r2, ty))
            g = int(self._lerp(g1, g2, ty))
            b = int(self._lerp(b1, b2, ty))
            self.canvas.create_line(0, y, w, y, fill=rgb_to_hex((r,g,b)), width=1, tags=self.tag)
        self.canvas.tag_lower(self.tag)  # Hintergrund nach hinten

    def tick(self):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 4 or h < 4:
            self.canvas.after(int(1000/self.fps), self.tick)
            return

        a = self.keys[self.idx]
        b = self.keys[(self.idx + 1) % len(self.keys)]
        # ease in-out
        tt = (1 - (1 - self.t) * (1 - self.t)) if self.t < 1 else 1

        top_hex = self._hsl_to_hex(
            self._lerp(a[0], b[0], tt),
            self._lerp(a[1], b[1], tt),
            self._lerp(a[2], b[2], tt)
        )
        self._draw_gradient(w, h, top_hex)

        dt = 1.0 / self.fps
        self.t += dt / self.duration
        if self.t >= 1.0:
            self.t = 0.0
            self.idx = (self.idx + 1) % len(self.keys)

        self.canvas.after(int(1000/self.fps), self.tick)

# ---------- 5) Fragen laden ----------
def strip_question_meta(text: str) -> str:
    import re
    t = text or ""
    t = re.sub(r"\s*\((?:[A-Za-zÄÖÜäöüß .+-]*#\s*\d+)\)\s*", "", t)
    t = re.sub(r"\b(?:Allgemeinwissen|Bonus|Kategorie|Trivia)\s*#\s*\d+:?\s*", "", t)
    t = re.sub(r"^Welche Aussage trifft zu\??$", "Welche Aussage ist richtig?", t).strip()
    t = re.sub(r"\s{2,}", " ", t)
    return t

def load_questions() -> list:
    if not os.path.isdir(DATA_DIR):
        print(f"Warnung: Daten-Ordner {DATA_DIR} fehlt.", file=sys.stderr)
        return []
    out = []
    for fn in sorted(os.listdir(DATA_DIR)):
        if not fn.lower().endswith(".json"):
            continue
        p = os.path.join(DATA_DIR, fn)
        try:
            with open(p, "r", encoding="utf-8") as f:
                q = json.load(f)
            if {"question","options","answer","explanations"} <= set(q.keys()) \
               and set(q["options"].keys())=={"A","B","C"} \
               and q["answer"] in ("A","B","C"):
                q["_src"] = fn
                q["question"] = strip_question_meta(q.get("question",""))
                out.append(q)
        except Exception as e:
            print(f"Fehler in {p}: {e}", file=sys.stderr)
    return out

# ---------- 6) App (Canvas-only UI, dynamisches Layout) ----------
class GameApp(tk.Tk):
    NUM_QUESTIONS = 10

    def __init__(self):
        super().__init__()
        self.title("Don't Ask Mizzz – Vollbild")
        self.attributes("-fullscreen", True)
        self.configure(bg="black")
        self.bind("<Escape>", lambda e: self.quit_game())

        self.cv = tk.Canvas(self, bg="black", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", self._on_resize)

        self.anim = GradientAnimator(self.cv)

        # Session: clear previous log (new run) and init asked-set
        try:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
        except Exception:
            pass
        self.asked_set = set()

        self.after(60, self.anim.tick)

        self.speaker = SpeechWorker(self)

        # Tags
        self.tag_question = "q_text"
        self.tag_feedback = "q_feedback"
        self.tag_expl = "q_expl"
        self.tag_opt = {"A":"optA", "B":"optB", "C":"optC"}
        self.tag_prompt = "again_prompt"

        # Text-Items
        self.q_item = self.cv.create_text(0,0, text="", fill="#ffffff",
            font=("Arial", 36, "bold"), width=1200, anchor="n",
            tags=self.tag_question, justify="center")
        self.fb_item = self.cv.create_text(0,0, text="", fill="#ffd54f",
            font=("Arial", 24), width=1200, anchor="n",
            tags=self.tag_feedback, justify="center")
        self.ex_item = self.cv.create_text(0,0, text="", fill="#ffecb3",
            font=("Arial", 20), width=1200, anchor="n",
            tags=self.tag_expl, justify="center")

        self.opt_items = {}
        for key in ("A","B","C"):
            item = self.cv.create_text(0,0, text="", fill="#ffffff",
                font=("Arial", 24, "bold"), width=1400, anchor="n",
                tags=self.tag_opt[key], justify="center")
            self.opt_items[key] = item
            self.cv.tag_bind(item, "<Button-1>", lambda e, k=key: self.on_pick(k))
            self.cv.tag_bind(item, "<Enter>", lambda e, it=item: self.cv.itemconfig(it, fill="#ffee88"))
            self.cv.tag_bind(item, "<Leave>", lambda e, it=item: self.cv.itemconfig(it, fill="#ffffff"))

        # Replay-Prompt (wird erst am Ende sichtbar)
        self.again_item = self.cv.create_text(0,0, text="", fill="#ffffff",
            font=("Arial", 24, "bold"), width=1200, anchor="n",
            tags=self.tag_prompt, justify="center")
        self.cv.itemconfigure(self.again_item, state="hidden")

        # Daten
        self.questions_all = load_questions()
        if not self.questions_all:
            self.cv.itemconfig(self.q_item,
                text="Keine Fragen gefunden.\nLege JSON-Dateien im Ordner 'data' an.")
            self._on_resize()
            return

        self._prepare_new_round()

        # Hotkeys
        for key in ("a","b","c","A","B","C"):
            self.bind(key, lambda e, k=key.upper(): self.on_pick(k))
        for key in ("j","J","y","Y"):
            self.bind(key, lambda e: self.start_again())
        for key in ("n","N"):
            self.bind(key, lambda e: self.quit_game())

        # Initiale Koordinaten
        self._on_resize()
        self.after(200, self.next_question)

    # ----- Round management -----
    def _prepare_new_round(self):
        available = [q for q in self.questions_all if q.get("_src") not in self.asked_set]
        if not available:
            # Falls alles verfeuert ist: wieder auffüllen (neue Session)
            self.asked_set.clear()
            available = list(self.questions_all)
        n = min(self.NUM_QUESTIONS, len(available))
        self.selected = random.sample(available, n)

        self.q_index = 0
        self.score = 0
        self.input_locked = False

    # ----- Layout-Helfer -----
    def _stack_vertically(self, items, top_y, pad=10):
        """
        Stapelt eine Liste von Canvas-Item-IDs vertikal so,
        dass sich nichts überlappt (per bbox-Messung).
        items: [(item_id, initial_y)] – initial_y ist die gewünschte Startposition,
        wird aber dynamisch angepasst.
        """
        w = self.cv.winfo_width()
        y_cursor = top_y
        for item, _init in items:
            # Erstmal grob platzieren
            self.cv.coords(item, w/2, y_cursor)
            self.update_idletasks()
            # bbox messen und auf darunter setzen
            bbox = self.cv.bbox(item)  # (x1,y1,x2,y2)
            if not bbox:
                y_cursor += pad
                continue
            height = max(0, bbox[3] - bbox[1])
            # Setze die Oberkante genau auf y_cursor (item ist anchor='n')
            self.cv.coords(item, w/2, y_cursor)
            y_cursor += height + pad
        return y_cursor  # gibt die nächste freie Y-Position zurück
    # (Canvas-bbox: siehe Tkinter-Referenzen/Beispiele.)  # :contentReference[oaicite:2]{index=2}

    def _on_resize(self, evt=None):
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        if w <= 0 or h <= 0:
            return
        # Grundgerüst neu stapeln
        top_y = int(h*0.10)
        # Frage
        y_after_question = self._stack_vertically([(self.q_item, top_y)], top_y, pad=12)
        # Feedback + Erklärung (werden ggf. leer sein – ist ok)
        y_after_feedback = self._stack_vertically([(self.fb_item, y_after_question)], y_after_question, pad=8)
        y_after_expl = self._stack_vertically([(self.ex_item, y_after_feedback)], y_after_feedback, pad=12)
        # Optionen darunter (A,B,C) – dynamisch, falls Umbrüche eintreten
        y_options_start = max(y_after_expl, int(h*0.35))
        y_cursor = y_options_start
        for key in ("A","B","C"):
            y_cursor = self._stack_vertically([(self.opt_items[key], y_cursor)], y_cursor, pad=10)
        # Replay-Prompt irgendwo darunter
        self.cv.coords(self.again_item, w/2, min(h-120, y_cursor + 30))

        # Sicherheit: Text immer über dem Hintergrund
        self.cv.tag_raise(self.tag_question)
        self.cv.tag_raise(self.tag_feedback)
        self.cv.tag_raise(self.tag_expl)
        for t in self.tag_opt.values():
            self.cv.tag_raise(t)
        self.cv.tag_raise(self.tag_prompt)
        self.cv.tag_lower("bg")

    # ----- TTS Sequenz-Helfer -----
    def _speak_sequence_after_paint(self, texts, on_done):
        self.update_idletasks()
        self.after(80, lambda: self.speaker.say_sequence(texts, on_done))

    # ----- Spielfluss -----
    def next_question(self):
        # Replay-Prompt ausblenden (falls vorher sichtbar)
        self.cv.itemconfigure(self.again_item, state="hidden")

        if self.q_index >= len(self.selected):
            return self.show_result()

        self.input_locked = False
        self.cv.itemconfig(self.fb_item, text="")
        self.cv.itemconfig(self.ex_item, text="")

        q = self.selected[self.q_index]
        num = self.q_index + 1
        # Markiere Frage als verwendet (Session-Log)
        src = q.get("_src")
        if src and src not in self.asked_set:
            self.asked_set.add(src)
            try:
                import json
                if os.path.exists(SESSION_FILE):
                    with open(SESSION_FILE, "r+", encoding="utf-8") as f:
                        try:
                            data = json.load(f)
                        except Exception:
                            data = []
                        if src not in data:
                            data.append(src)
                        f.seek(0), f.truncate(0)
                        json.dump(data, f, ensure_ascii=False, indent=2)
                else:
                    with open(SESSION_FILE, "w", encoding="utf-8") as f:
                        json.dump([src], f, ensure_ascii=False, indent=2)
            except Exception:
                pass


        q_text = f"Frage {num}: {q['question']}"
        self.cv.itemconfig(self.q_item, text=q_text)

        for key in ("A","B","C"):
            self.cv.itemconfig(self.opt_items[key], text=f"{key}) {q['options'][key]}")
            self.cv.itemconfig(self.opt_items[key], fill="#ffffff")

        # Neu stapeln (umbruchsabhängig)
        self._on_resize()

        # TTS: Frage fertig sprechen, dann Eingaben freigeben
        def after_tts():
            self.input_locked = False
        self.input_locked = True
        self._speak_sequence_after_paint([q_text], after_tts)

    def on_pick(self, key):
        if self.input_locked or self.q_index >= len(self.selected):
            return
        self.input_locked = True

        q = self.selected[self.q_index]
        correct = q["answer"]

        if key == correct:
            line = random.choice(CORRECT_RESPONSES)
            self.cv.itemconfig(self.fb_item, text=f"✅ {line}")
            self._on_resize()
            def done():
                self.score += 1
                self.q_index += 1
                self.next_question()
            self._speak_sequence_after_paint([line], done)
        else:
            line = random.choice(WRONG_RESPONSES)
            self.cv.itemconfig(self.fb_item, text=f"❌ {line}")
            picked_exp = q["explanations"].get(key, "Keine Erklärung vorhanden.")
            self.cv.itemconfig(self.ex_item, text=picked_exp)
            corr_line = f"Richtige Antwort: {correct} – {q['options'][correct]}"
            # Neu stapeln, falls Erklärung mehrere Zeilen hat
            self._on_resize()
            def done():
                self.q_index += 1
                self.next_question()
            self._speak_sequence_after_paint([line, picked_exp, corr_line], done)

    def show_result(self):
        total = len(self.selected)
        head_text_ui = "=== Ergebnis ==="           # nur Anzeige
        head_text_tts = "Ergebnis"                  # nicht „gleich gleich…“ sagen
        msg = f"Du hast {self.score} von {total} Fragen richtig beantwortet."
        if self.score == total:
            tail = "Ganz stark – perfekter Lauf!"
        elif self.score >= max(1, total//2):
            tail = "Ordentlich! Nachschlag gefällig?"
        else:
            tail = "Warmwerden ist vorbei – nächste Runde wird ernst."

        self.cv.itemconfig(self.q_item, text=head_text_ui)
        self.cv.itemconfig(self.fb_item, text=msg)
        self.cv.itemconfig(self.ex_item, text=tail)
        self._on_resize()

        # Replay-Prompt einblenden
        prompt = "Möchtest du noch eine Runde spielen? (J/N)"
        self.cv.itemconfigure(self.again_item, text=prompt, state="normal")
        self._on_resize()

        def after_tts():
            # Eingaben J/N erlauben – (A/B/C bleibt egal, Runde ist vorbei)
            self.input_locked = False

        self.input_locked = True
        self._speak_sequence_after_paint([head_text_tts, msg, tail, "Neue Runde ?"], after_tts)

    def start_again(self):
        if self.q_index < len(self.selected):  # keine neue Runde mitten drin
            return
        self._prepare_new_round()
        self.next_question()

    def quit_game(self):
        try:
            self.speaker.stop()
        except Exception:
            pass
        self.destroy()

if __name__ == "__main__":
    app = GameApp()
    app.mainloop()