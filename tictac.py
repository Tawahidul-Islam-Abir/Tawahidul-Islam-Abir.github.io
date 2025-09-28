import tkinter as tk
from tkinter import messagebox

class TicTacToe:
    def __init__(self, root):
        self.root = root
        self.root.title("Tic Tac Toe - Modern Edition")
        self.root.configure(bg="#2c3e50")
        self.current_player = "X"
        self.board = [""] * 9
        self.buttons = []

        self.status_label = tk.Label(
            self.root,
            text=f"Player {self.current_player}'s Turn",
            font=("Helvetica", 16, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        self.status_label.pack(pady=15)

        frame = tk.Frame(self.root, bg="#2c3e50")
        frame.pack()

        for i in range(9):
            button = tk.Button(
                frame,
                text="",
                font=("Helvetica", 24, "bold"),
                width=5,
                height=2,
                bg="#34495e",
                fg="white",
                activebackground="#16a085",
                relief="flat",
                command=lambda i=i: self.on_click(i)
            )
            button.grid(row=i // 3, column=i % 3, padx=5, pady=5)
            self.buttons.append(button)

        reset_btn = tk.Button(
            self.root,
            text="🔄 Reset Game",
            font=("Helvetica", 14, "bold"),
            bg="#e74c3c",
            fg="white",
            activebackground="#c0392b",
            relief="flat",
            command=self.reset_game
        )
        reset_btn.pack(pady=15)

    def on_click(self, index):
        if self.board[index] == "" and not self.check_winner():
            self.board[index] = self.current_player
            self.buttons[index].config(text=self.current_player)

            if self.check_winner():
                self.status_label.config(text=f"🎉 Player {self.current_player} Wins!", fg="#f1c40f")
                messagebox.showinfo("Game Over", f"Player {self.current_player} Wins!")
            elif "" not in self.board:
                self.status_label.config(text="🤝 It's a Draw!", fg="#f39c12")
                messagebox.showinfo("Game Over", "It's a Draw!")
            else:
                self.current_player = "O" if self.current_player == "X" else "X"
                self.status_label.config(text=f"Player {self.current_player}'s Turn")

    def check_winner(self):
        win_patterns = [
            [0,1,2], [3,4,5], [6,7,8], # rows
            [0,3,6], [1,4,7], [2,5,8], # cols
            [0,4,8], [2,4,6]           # diagonals
        ]
        for pattern in win_patterns:
            a, b, c = pattern
            if self.board[a] == self.board[b] == self.board[c] != "":
                for i in pattern:
                    self.buttons[i].config(bg="#27ae60")  # highlight win
                return True
        return False

    def reset_game(self):
        self.current_player = "X"
        self.board = [""] * 9
        for btn in self.buttons:
            btn.config(text="", bg="#34495e")
        self.status_label.config(text=f"Player {self.current_player}'s Turn", fg="white")

if __name__ == "__main__":
    root = tk.Tk()
    app = TicTacToe(root)
    root.mainloop()
