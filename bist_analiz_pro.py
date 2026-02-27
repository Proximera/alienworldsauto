import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import pandas as pd
import time
import datetime
from isyatirimhisse import fetch_financials

# --- CONSTANTS & CONFIGURATION ---
SECTOR_MAPPINGS = {
    "Endüstriyel": {
        "check": ["Hasılat", "Satış Gelirleri"],
        "map": {
            "Revenue": ["Satış Gelirleri", "Hasılat", "Net Satışlar"],
            "Operating_Profit": ["Esas Faaliyet Karı (Zararı)", "Faaliyet Karı (Zararı)"],
            "Net_Profit": ["Dönem Karı (Zararı)", "Net Dönem Karı/Zararı"],
            "Equity": ["Ana Ortaklığa Ait Özkaynaklar", "Özkaynaklar"],
            "Amortization": ["Amortisman Giderleri", "Amortisman ve İtfa Giderleri", "Amortisman"],
            "Flow_Items": ["Revenue", "Operating_Profit", "Net_Profit", "Amortization"] # Items to subtract previous quarter
        }
    },
    "Banka": {
        "check": ["I. FAİZ GELİRLERİ", "III. NET FAİZ GELİRİ/GİDERİ (I - II)"],
        "map": {
            "Revenue": ["III. NET FAİZ GELİRİ/GİDERİ (I - II)", "Net Faiz Geliri"], # Proxy for core income
            "Operating_Profit": ["XI. NET FAALİYET KARI/ZARARI (VIII-IX-X)", "Net Faaliyet Karı"],
            "Net_Profit": ["XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)", "Net Dönem Karı/Zararı"],
            "Equity": ["XVI. ÖZKAYNAKLAR", "Özkaynaklar"],
            "Amortization": [], # Usually not added back for Banks in simple view
            "Flow_Items": ["Revenue", "Operating_Profit", "Net_Profit"]
        }
    },
    "Sigorta": {
        "check": ["A- Hayat Dışı Teknik Gelir", "J- Genel Teknik Bölüm Dengesi"],
        "map": {
            "Revenue": ["J- Genel Teknik Bölüm Dengesi", "Genel Teknik Bölüm Dengesi"], # Technical Balance
            "Operating_Profit": ["M- Diğer Faaliyetlerden ve Olağandışı Faal. Gelir ve Karlar(+/-)", "Diğer Faaliyet Gelirleri"], # This might be tricky, let's use Net Profit as main driver
            "Net_Profit": ["N- Dönem Net Karı veya Zararı", "Dönem Net Karı"],
            "Equity": ["Özsermaye Toplamı", "Özkaynaklar"],
            "Amortization": [],
            "Flow_Items": ["Revenue", "Operating_Profit", "Net_Profit"]
        }
    },
    "Girişim/GYO": { # Group 3 often resembles Bank/Financials structure
        "check": ["III. NET FAİZ GELİRİ/GİDERİ (I - II)", "XVI. ÖZKAYNAKLAR"],
        "map": {
             "Revenue": ["III. NET FAİZ GELİRİ/GİDERİ (I - II)", "Net Faiz Geliri"],
             "Operating_Profit": ["XI. NET FAALİYET KARI/ZARARI (VIII-IX-X)"],
             "Net_Profit": ["XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)"],
             "Equity": ["XVI. ÖZKAYNAKLAR"],
             "Amortization": [],
             "Flow_Items": ["Revenue", "Operating_Profit", "Net_Profit"]
        }
    }
}

class SmartFetcher:
    """Handles fetching data by trying multiple financial groups."""

    @staticmethod
    def fetch(symbol, start_year, end_year):
        groups = ['1', '2', '3']
        errors = []

        for group in groups:
            try:
                # print(f"DEBUG: Trying {symbol} with Group {group}...")
                df = fetch_financials(
                    symbols=[symbol],
                    start_year=start_year,
                    end_year=end_year,
                    exchange='TRY',
                    financial_group=group
                )

                if df is not None and not df.empty:
                    # Verify it has columns other than metadata
                    if len(df.columns) > 5: # Basic check
                        return df, group
            except Exception as e:
                errors.append(f"G{group}: {str(e)}")

        return None, errors

class FinancialAnalyzer:
    """Parses the dataframe, detects sector, and calculates quarterly isolated values."""

    @staticmethod
    def detect_sector(df):
        columns = df['FINANCIAL_ITEM_NAME_TR'].astype(str).tolist()
        # Flatten columns for easier searching
        col_str = " ".join(columns).upper()

        for sector, config in SECTOR_MAPPINGS.items():
            for keyword in config["check"]:
                if keyword.upper() in col_str or any(keyword.upper() in c.upper() for c in columns):
                    return sector
        return "Bilinmeyen"

    @staticmethod
    def get_value(df, period, keywords):
        """
        Retrieves a value from the dataframe for a specific period and list of possible keywords.
        Returns 0.0 if not found.
        """
        if period not in df.columns:
            return 0.0

        # Clean up dataframe names for matching
        df['clean_name'] = df['FINANCIAL_ITEM_NAME_TR'].astype(str).str.strip().str.replace('İ', 'i').str.replace('I', 'ı').str.lower()

        for kw in keywords:
            target = kw.strip().replace('İ', 'i').replace('I', 'ı').lower()
            match = df[df['clean_name'] == target]
            if not match.empty:
                val = match[period].iloc[0]
                return float(val) if pd.notna(val) else 0.0

        return 0.0

    @staticmethod
    def calculate_period(df, sector, item_type, year, quarter, mode="izole"):
        """
        Calculates the value for a specific item (Revenue, Net Profit, etc.)
        Handles Quarterly Isolation (Q3 = 9M - 6M) if mode is 'izole'.
        """
        mapping = SECTOR_MAPPINGS.get(sector, SECTOR_MAPPINGS["Endüstriyel"])["map"]
        keywords = mapping.get(item_type, [])
        flow_items = mapping.get("Flow_Items", [])

        current_period = f"{year}/{quarter}"

        def get_isolated_val(kws, is_flow):
            val_curr = FinancialAnalyzer.get_value(df, current_period, kws)

            if mode == "kumulatif" or not is_flow:
                return val_curr

            if quarter == "3":
                return val_curr

            prev_quarter_map = {"6": "3", "9": "6", "12": "9"}
            if quarter in prev_quarter_map:
                prev_q = prev_quarter_map[quarter]
                prev_period = f"{year}/{prev_q}"
                val_prev = FinancialAnalyzer.get_value(df, prev_period, kws)
                return val_curr - val_prev
            return val_curr

        # If requesting EBITDA (FAVÖK), we sum Operating Profit + Amortization
        if item_type == "EBITDA":
            op_profit = get_isolated_val(mapping.get("Operating_Profit", []), True)

            # Add amortization only for industrial usually, but we check if mapping has it
            amort_kws = mapping.get("Amortization", [])
            if amort_kws:
                # Amortization is an expense (usually positive number in statement or negative?),
                # but in Turkish statements usually positive. EBITDA = OP + Amortization.
                # NOTE: In TR statements 'General Admin Expenses' includes amortization, so we add it back.
                # However, fetch_financials usually returns positive values for expenses in detail lines?
                # Let's assume standard add-back.
                amort = get_isolated_val(amort_kws, True)
                return op_profit + amort
            return op_profit

        # Standard calculation
        return get_isolated_val(keywords, item_type in flow_items)

class BistAnalizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BIST Pro Analiz Terminali v2.0")
        self.root.geometry("1600x750")
        self.root.configure(bg="#f4f6f8")

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Treeview",
                        background="white",
                        foreground="black",
                        rowheight=28,
                        fieldbackground="white",
                        font=('Segoe UI', 9))

        style.configure("Treeview.Heading",
                        font=('Segoe UI', 9, 'bold'),
                        background="#e1e4e8",
                        foreground="#333")

        style.map('Treeview', background=[('selected', '#0078D7')])

    def _build_ui(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#24292e", pady=10)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="BIST Finansal Analiz Pro", font=("Segoe UI", 16, "bold"), fg="white", bg="#24292e").pack()

        # Input Panel
        input_frame = tk.Frame(self.root, bg="#f4f6f8", pady=15, padx=15)
        input_frame.pack(fill=tk.X)

        # Row 1: Stocks
        tk.Label(input_frame, text="Hisseler:", bg="#f4f6f8", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.entry_stocks = tk.Entry(input_frame, width=80, font=("Consolas", 11))
        self.entry_stocks.insert(0, "THYAO, AKBNK, AKGRT, ISGYO, FROTO")
        self.entry_stocks.grid(row=0, column=1, columnspan=4, padx=10, sticky="w")

        # Row 2: Periods
        curr_year = datetime.datetime.now().year
        years = [str(y) for y in range(curr_year, 2015, -1)]
        quarters = ["3", "6", "9", "12"]

        tk.Label(input_frame, text="Baz Dönem (Eski):", bg="#f4f6f8").grid(row=1, column=0, sticky="w", pady=10)
        self.cb_y1 = ttk.Combobox(input_frame, values=years, width=6, state="readonly")
        self.cb_y1.set(str(curr_year-1))
        self.cb_y1.grid(row=1, column=1, sticky="w", padx=(10,0))
        self.cb_q1 = ttk.Combobox(input_frame, values=quarters, width=4, state="readonly")
        self.cb_q1.set("12")
        self.cb_q1.grid(row=1, column=1, sticky="w", padx=(80,0))

        tk.Label(input_frame, text="Hedef Dönem (Yeni):", bg="#f4f6f8").grid(row=1, column=2, sticky="w", padx=20)
        self.cb_y2 = ttk.Combobox(input_frame, values=years, width=6, state="readonly")
        self.cb_y2.set(str(curr_year))
        self.cb_y2.grid(row=1, column=3, sticky="w", padx=(0,0))
        self.cb_q2 = ttk.Combobox(input_frame, values=quarters, width=4, state="readonly")
        self.cb_q2.set("12")
        self.cb_q2.grid(row=1, column=3, sticky="w", padx=(70,0))

        # Mode
        self.var_mode = tk.StringVar(value="izole")
        tk.Radiobutton(input_frame, text="Çeyreklik İzole (Q)", variable=self.var_mode, value="izole", bg="#f4f6f8").grid(row=1, column=4, padx=10)
        tk.Radiobutton(input_frame, text="Kümülatif (Yıllık)", variable=self.var_mode, value="kumulatif", bg="#f4f6f8").grid(row=1, column=5)

        # Buttons
        btn_frame = tk.Frame(input_frame, bg="#f4f6f8")
        btn_frame.grid(row=2, column=0, columnspan=6, pady=15, sticky="w")

        self.btn_start = tk.Button(btn_frame, text="ANALİZ ET", bg="#28a745", fg="white", font=("Segoe UI", 10, "bold"), padx=20, pady=5, command=self.start_analysis)
        self.btn_start.pack(side=tk.LEFT)

        self.btn_export = tk.Button(btn_frame, text="EXCEL İNDİR", bg="#007bff", fg="white", font=("Segoe UI", 10, "bold"), padx=20, pady=5, state=tk.DISABLED, command=self.export_excel)
        self.btn_export.pack(side=tk.LEFT, padx=10)

        self.lbl_status = tk.Label(btn_frame, text="Hazır", bg="#f4f6f8", fg="#666", font=("Segoe UI", 9, "italic"))
        self.lbl_status.pack(side=tk.LEFT, padx=20)

        # Progress Bar
        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(fill=tk.X, padx=15)

        # Results Table
        self.tree_frame = tk.Frame(self.root)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        # Expanded columns to show Old and New values and Margins
        self.cols = [
            "Hisse", "Sektör",
            "Ciro (Eski)", "Ciro (Yeni)", "Ciro Büyüme",
            "FAVÖK (Eski)", "FAVÖK (Yeni)", "FAVÖK Büyüme", "FAVÖK Marjı (Yeni)", "Marj Değişimi",
            "Net Kar (Eski)", "Net Kar (Yeni)", "Net Kar Büyüme", "Net Kar Marjı (Yeni)",
            "Özkaynak (Eski)", "Özkaynak (Yeni)", "Özk. Büyüme"
        ]

        self.tree = ttk.Treeview(self.tree_frame, columns=self.cols, show="headings")

        for col in self.cols:
            self.tree.heading(col, text=col)
            width = 50 if col == "Hisse" else 75 if col == "Sektör" else 95 if "Marj" in col or "Büyüme" in col else 105
            self.tree.column(col, width=width, anchor="center")

        scroll_y = tk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x = tk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Log
        self.txt_log = tk.Text(self.root, height=6, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        self.txt_log.pack(fill=tk.X, padx=15, pady=(0, 15))

    def log(self, msg):
        self.txt_log.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.txt_log.see(tk.END)

    def start_analysis(self):
        threading.Thread(target=self.run_process).start()

    def run_process(self):
        stocks = [s.strip().upper() for s in self.entry_stocks.get().split(",") if s.strip()]
        if not stocks:
            return

        self.btn_start.config(state=tk.DISABLED)
        self.btn_export.config(state=tk.DISABLED)
        self.tree.delete(*self.tree.get_children())
        self.progress['value'] = 0
        self.results_data = []

        y1, q1 = self.cb_y1.get(), self.cb_q1.get()
        y2, q2 = self.cb_y2.get(), self.cb_q2.get()
        mode = self.var_mode.get()

        # Determine needed years to fetch
        years_needed = {y1, y2}
        min_year = min([int(y) for y in years_needed])
        max_year = max([int(y) for y in years_needed])

        step_val = 100 / len(stocks)

        for i, symbol in enumerate(stocks):
            self.lbl_status.config(text=f"İşleniyor: {symbol}...")
            self.log(f"Fetching data for {symbol}...")

            df, group = SmartFetcher.fetch(symbol, str(min_year), str(max_year))

            if df is None:
                self.log(f"ERROR: Could not fetch data for {symbol}")
                self.progress['value'] += step_val
                continue

            sector = FinancialAnalyzer.detect_sector(df)
            self.log(f"{symbol} detected as {sector} (Group {group})")

            # Analyze
            try:
                # Calculate Values
                # Revenue
                rev_new = FinancialAnalyzer.calculate_period(df, sector, "Revenue", y2, q2, mode)
                rev_old = FinancialAnalyzer.calculate_period(df, sector, "Revenue", y1, q1, mode)

                # EBITDA (FAVÖK)
                # For banks/insurance, EBITDA might just be Op Profit or similar
                ebitda_new = FinancialAnalyzer.calculate_period(df, sector, "EBITDA", y2, q2, mode)
                ebitda_old = FinancialAnalyzer.calculate_period(df, sector, "EBITDA", y1, q1, mode)

                # Net Profit
                net_new = FinancialAnalyzer.calculate_period(df, sector, "Net_Profit", y2, q2, mode)
                net_old = FinancialAnalyzer.calculate_period(df, sector, "Net_Profit", y1, q1, mode)

                # Equity (Stock item)
                eq_new = FinancialAnalyzer.calculate_period(df, sector, "Equity", y2, q2, mode)
                eq_old = FinancialAnalyzer.calculate_period(df, sector, "Equity", y1, q1, mode)

                # Growth Calcs
                def calc_growth(new, old):
                    if old == 0: return 0.0
                    return ((new - old) / abs(old)) * 100

                def calc_margin(profit, rev):
                    if rev == 0: return 0.0
                    return (profit / rev) * 100

                def fmt(val):
                    return f"₺ {val/1_000_000:,.1f} Mn"

                # Margins
                ebitda_margin_new = calc_margin(ebitda_new, rev_new)
                ebitda_margin_old = calc_margin(ebitda_old, rev_old)
                ebitda_margin_diff = ebitda_margin_new - ebitda_margin_old

                net_margin_new = calc_margin(net_new, rev_new)

                row = {
                    "Hisse": symbol,
                    "Sektör": sector,
                    "Ciro (Eski)": fmt(rev_old), "Ciro (Yeni)": fmt(rev_new), "Ciro Büyüme": f"% {calc_growth(rev_new, rev_old):.1f}",
                    "FAVÖK (Eski)": fmt(ebitda_old), "FAVÖK (Yeni)": fmt(ebitda_new), "FAVÖK Büyüme": f"% {calc_growth(ebitda_new, ebitda_old):.1f}",
                    "FAVÖK Marjı (Yeni)": f"% {ebitda_margin_new:.1f}",
                    "Marj Değişimi": f"{'+' if ebitda_margin_diff > 0 else ''}{ebitda_margin_diff:.1f} Puan",
                    "Net Kar (Eski)": fmt(net_old), "Net Kar (Yeni)": fmt(net_new), "Net Kar Büyüme": f"% {calc_growth(net_new, net_old):.1f}",
                    "Net Kar Marjı (Yeni)": f"% {net_margin_new:.1f}",
                    "Özkaynak (Eski)": fmt(eq_old), "Özkaynak (Yeni)": fmt(eq_new), "Özk. Büyüme": f"% {calc_growth(eq_new, eq_old):.1f}",
                    "_raw_rev": rev_new,
                    "_raw_net": net_new
                }

                self.results_data.append(row)

                # Insert into Treeview
                values = [row[c] for c in self.cols]
                self.tree.insert("", "end", values=values)

            except Exception as e:
                self.log(f"Error analyzing {symbol}: {e}")

            self.progress['value'] += step_val

        self.btn_start.config(state=tk.NORMAL)
        self.btn_export.config(state=tk.NORMAL)
        self.lbl_status.config(text="Tamamlandı.")
        self.log("Analysis Complete.")

    def export_excel(self):
        if not self.results_data:
            return

        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            pd.DataFrame(self.results_data).drop(columns=["_raw_rev", "_raw_net"]).to_excel(path, index=False)
            messagebox.showinfo("Başarılı", "Excel dosyası kaydedildi.")

if __name__ == "__main__":
    root = tk.Tk()
    app = BistAnalizApp(root)
    root.mainloop()
