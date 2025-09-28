import tkinter as tk
from tkinter import ttk, messagebox
import math
import ast
import operator

# ---------------------- Safe eval ----------------------
SAFE_NAMES = {k: getattr(math, k) for k in dir(math) if not k.startswith("__")}
SAFE_NAMES.update({
    'abs': abs,
    'round': round,
    'pow': pow,
    'ln': math.log
})

ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

class EvalError(Exception):
    pass

def safe_eval(expr: str):
    try:
        node = ast.parse(expr, mode='eval')
    except Exception:
        raise EvalError("Syntax error")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise EvalError("Invalid constant")
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.BinOp):
            left, right = _eval(node.left), _eval(node.right)
            if type(node.op) in ALLOWED_OPERATORS:
                return ALLOWED_OPERATORS[type(node.op)](left, right)
            raise EvalError("Invalid operator")
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if type(node.op) in ALLOWED_OPERATORS:
                return ALLOWED_OPERATORS[type(node.op)](operand)
            raise EvalError("Invalid unary operator")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in SAFE_NAMES:
                args = [_eval(a) for a in node.args]
                return SAFE_NAMES[node.func.id](*args)
            raise EvalError("Invalid function call")
        if isinstance(node, ast.Name):
            if node.id in SAFE_NAMES:
                return SAFE_NAMES[node.id]
            raise EvalError(f"Unknown name {node.id}")
        if isinstance(node, ast.Expr):
            return _eval(node.value)
        raise EvalError("Unsupported expression")

    return _eval(node)

# ---------------------- GUI ----------------------

class FancyCalculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fancy Modern Calculator")
        self.geometry("520x600")
        self.minsize(380, 520)

        self.expression = tk.StringVar()
        self.result = tk.StringVar()
        self.history = []
        self.dark = tk.BooleanVar(value=True)

        self.style = ttk.Style(self)
        self._set_theme()

        self._create_header()
        self._create_display()
        self._create_body()
        self._bind_keys()

    def _set_theme(self):
        if self.dark.get():
            bg, fg, btn_bg, accent =  '#00b3a6', "#D4D4D2", "#1C1C1C", '#1f1f23'
        else:
            bg, fg, btn_bg, accent =  "#505050", '#ffffff', "#FF9500", '#f4f7fb',

        self.configure(bg=bg)
        self.style.configure('TFrame', background=bg)
        self.style.configure('TLabel', background=bg, foreground=fg, font=('Arial', 12))
        self.style.configure('Result.TLabel', font=('Arial', 24, 'bold'))
        self.btn_bg, self.btn_fg, self.accent = btn_bg, fg, accent

    def _create_header(self):
        header = ttk.Frame(self)
        header.pack(fill='x', padx=12, pady=(12, 6))
        ttk.Label(header, text="Abir's Calculator", font=('Arial', 16, 'bold')).pack(side='left')
        ttk.Checkbutton(header, text='Dark', variable=self.dark, command=self._toggle_theme).pack(side='right')

    def _create_display(self):
        frame = ttk.Frame(self)
        frame.pack(fill='x', padx=12)
        ttk.Entry(frame, textvariable=self.expression, font=('Arial', 18)).pack(fill='x', pady=(6, 4))
        ttk.Label(frame, textvariable=self.result, style='Result.TLabel').pack(anchor='e')

    def _create_body(self):
        body = ttk.Frame(self)
        body.pack(fill='both', expand=True, padx=12, pady=12)

        # Left: buttons
        btn_frame = ttk.Frame(body)
        btn_frame.pack(side='left', fill='both', expand=True)

        buttons = [
            ['7', '8', '9', '/', 'sqrt'],
            ['4', '5', '6', '*', 'pow'],
            ['1', '2', '3', '-', 'log'],
            ['0', '.', '%', '+', 'ln'],
            ['(', ')', 'ans', 'C', '='],
            ['sin', 'cos', 'tan', 'pi', 'e']
        ]

        for row in buttons:
            row_frame = ttk.Frame(btn_frame)
            row_frame.pack(fill='x', expand=True)
            for label in row:
                btn = tk.Button(row_frame, text=label, relief='flat', bd=0,
                                command=lambda l=label: self._on_button(l))
                btn.pack(side='left', expand=True, fill='both', padx=3, pady=3)
                btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=self.accent, fg='white'))
                btn.bind('<Leave>', lambda e, b=btn: b.configure(bg=self.btn_bg, fg=self.btn_fg))
                btn.configure(bg=self.btn_bg, fg=self.btn_fg)

        # Right: history with scrollbar
        hist_frame = ttk.Frame(body)
        hist_frame.pack(side='right', fill='y')
        ttk.Label(hist_frame, text='History').pack()
        hist_container = ttk.Frame(hist_frame)
        hist_container.pack(fill='both', expand=True)
        scrollbar = ttk.Scrollbar(hist_container)
        scrollbar.pack(side='right', fill='y')
        self.hist_list = tk.Listbox(hist_container, height=20, yscrollcommand=scrollbar.set)
        self.hist_list.pack(side='left', fill='y', expand=True)
        scrollbar.config(command=self.hist_list.yview)
        self.hist_list.bind('<<ListboxSelect>>', self._on_history_select)

    def _bind_keys(self):
        for k in '0123456789+-*/().%':
            self.bind(k, self._key_insert)
        self.bind('<Return>', lambda e: self._on_button('='))
        self.bind('<BackSpace>', lambda e: self._on_button('BACK'))
        self.bind('<Escape>', lambda e: self._on_button('C'))

    def _on_button(self, label):
        expr = self.expression.get()
        if label == 'C':
            self.expression.set(''); self.result.set(''); return
        if label == 'BACK':
            self.expression.set(expr[:-1]); return
        if label == 'ans' and self.history:
            self.expression.set(expr + str(self.history[-1][1])); return
        if label == '=':
            self._calculate(); return

        mapping = {
            'sqrt': 'sqrt(', 'pow': 'pow(', 'log': 'log(', 'ln': 'ln(',
            'pi': str(math.pi), 'e': str(math.e),
            'sin': 'sin(', 'cos': 'cos(', 'tan': 'tan('
        }
        self.expression.set(expr + mapping.get(label, label))

    def _key_insert(self, event):
        if event.char:
            self.expression.set(self.expression.get() + event.char)

    def _calculate(self):
        expr = self.expression.get()
        if not expr.strip():
            return
        try:
            val = safe_eval(expr)
            display = str(round(val, 12)).rstrip('0').rstrip('.') if isinstance(val, float) else str(val)
            self.result.set(display)
            self.history.append((expr, display))
            self.hist_list.insert('end', f"{expr} = {display}")
            self.hist_list.yview_moveto(1)
        except EvalError as e:
            messagebox.showerror("Error", f"{e}")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected: {e}")

    def _on_history_select(self, event):
        sel = event.widget.curselection()
        if sel:
            expr, res = self.history[sel[0]]
            self.expression.set(expr)
            self.result.set(res)

    def _toggle_theme(self):
        self._set_theme()
        self._recolor_widgets(self)

    def _recolor_widgets(self, widget):
        for w in widget.winfo_children():
            if isinstance(w, tk.Button):
                w.configure(bg=self.btn_bg, fg=self.btn_fg)
            self._recolor_widgets(w)

if __name__ == '__main__':
    app = FancyCalculator()
    app.mainloop()