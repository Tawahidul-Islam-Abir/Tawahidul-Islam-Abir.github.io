import tkinter as tk
from tkinter import ttk

class ChatbotApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Chatbot")
        self.geometry("500x600")

        self.dark = tk.BooleanVar(value=True)
        self.style = ttk.Style(self)
        self._set_theme()

        self._create_header()
        self._create_chat_area()
        self._create_input_area()

    def _set_theme(self):
        if self.dark.get():
            self.bg, self.fg, self.accent = "#1f1f23", "#e6eef8", "#00b3a6"
        else:
            self.bg, self.fg, self.accent = "#f4f7fb", "#222222", "#0077cc"
        self.configure(bg=self.bg)
        self.style.configure("TLabel", background=self.bg, foreground=self.fg)
        self.style.configure("TButton", background=self.accent, foreground="white")

    def _create_header(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)
        ttk.Label(header, text="Chatbot", font=("Arial", 16, "bold")).pack(side="left")
        ttk.Checkbutton(header, text="Dark", variable=self.dark, command=self._toggle_theme).pack(side="right")

    def _create_chat_area(self):
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.text_area = tk.Text(frame, wrap="word", state="disabled", bg=self.bg, fg=self.fg, font=("Arial", 12))
        self.text_area.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(frame, command=self.text_area.yview)
        scrollbar.pack(side="right", fill="y")
        self.text_area["yscrollcommand"] = scrollbar.set

    def _create_input_area(self):
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=10, pady=5)
        self.entry = ttk.Entry(frame, font=("Arial", 12))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.entry.bind("<Return>", self._send_message)
        ttk.Button(frame, text="Send", command=self._send_message).pack(side="right")

    def _send_message(self, event=None):
        user_msg = self.entry.get().strip()
        if not user_msg:
            return
        self._insert_message("You", user_msg)
        self.entry.delete(0, "end")
        bot_response = self._get_response(user_msg)
        self._insert_message("Bot", bot_response)

    def _insert_message(self, sender, msg):
        self.text_area.configure(state="normal")
        self.text_area.insert("end", f"{sender}: {msg}\n")
        self.text_area.configure(state="disabled")
        self.text_area.yview_moveto(1)

    def _get_response(self, msg: str) -> str:
        msg = msg.lower()
        if "hello" in msg or "hi" in msg:
            return "Hello! How can I help you today?"
        if "how are you" in msg:
            return "I'm just a bot, but I'm doing great! How about you?"
        if "your name" in msg:
            return "I'm a simple Python Chatbot."
        if "bye" in msg:
            return "Goodbye! Have a great day!"
        if "can you help me" in msg:
            return "Yes but in  limited cases."
        if "IS it abir??" in msg:
            return "Yes!!"
        if "I need a help" in msg:
            return "What's the issue?"
        if "I am feeling bored." in msg:
            return "You can play some game."
        if "I dont want to play games" in msg:
            return "You can take a nap."
        if "I need to go to the shopping" in msg:
            return "What you need to buy?"
        if "I need to buy some outfits" in msg:
            return "But you have many."
        if "I want to buy some more" in msg:
            return "You should spend your money efficiently and carefully."
        if "Okh, I will be careful from the next time." in msg:
            return "Yes, be careful."
        return "I'm not sure how to respond to that."

    def _toggle_theme(self):
        self._set_theme()
        self.text_area.configure(bg=self.bg, fg=self.fg)

if __name__ == "__main__":
    app = ChatbotApp()
    app.mainloop()