import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import pandas as pd
import time
import datetime
from isyatirimhisse import fetch_financials

class EsnekBilancoTerminali:
    def __init__(self, root):
        self.root = root
        self.root.title("İzole Çeyreklik (Q) BIST Analiz Terminali")
        self.root.geometry("1350x600")
        self.root.configure(bg="#f0f2f5")

        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Treeview", background="#ffffff", foreground="#333333",
                        rowheight=30, fieldbackground="#ffffff", font=('Segoe UI', 10))
        style.map('Treeview', background=[('selected', '#0078D7')], foreground=[('selected', 'white')])
        style.configure("Treeview.Heading", font=('Segoe UI', 9, 'bold'), background="#e1e4e8", foreground="#24292e")

        self.ana_tablo = pd.DataFrame()

        # --- ÜST PANEL (Hisse) ---
        ust_frame = tk.Frame(self.root, pady=10, padx=15, bg="#f0f2f5")
        ust_frame.pack(fill=tk.X)

        tk.Label(ust_frame, text="Hisseler (Virgülle):", font=("Segoe UI", 10, "bold"), bg="#f0f2f5").pack(side=tk.LEFT, padx=(0, 10))

        self.hisse_entry = tk.Entry(ust_frame, width=70, font=("Segoe UI", 11), relief="solid", bd=1)
        self.hisse_entry.insert(0, "ASTOR, THYAO, TUPRS, FROTO, ASELS, BIMAS")
        self.hisse_entry.pack(side=tk.LEFT, ipady=3)

        # --- SEÇİM PANELİ (Dönem ve Mod) ---
        secim_frame = tk.Frame(self.root, pady=5, padx=15, bg="#f0f2f5")
        secim_frame.pack(fill=tk.X)

        su_an_yil = datetime.datetime.now().year
        yillar = list(range(2015, su_an_yil + 1))
        ceyrekler = ["3", "6", "9", "12"]

        # 1. DÖNEM
        tk.Label(secim_frame, text="1. Dönem (Baz):", font=("Segoe UI", 10), bg="#f0f2f5", fg="#555").pack(side=tk.LEFT)
        self.yil1_cb = ttk.Combobox(secim_frame, values=yillar, width=6, state="readonly")
        self.yil1_cb.set(su_an_yil - 1)
        self.yil1_cb.pack(side=tk.LEFT, padx=(5, 0))

        self.ceyrek1_cb = ttk.Combobox(secim_frame, values=ceyrekler, width=4, state="readonly")
        self.ceyrek1_cb.set("12")
        self.ceyrek1_cb.pack(side=tk.LEFT, padx=(5, 0))

        tk.Label(secim_frame, text="   VS   ", font=("Segoe UI", 11, "bold"), bg="#f0f2f5", fg="#0078D7").pack(side=tk.LEFT, padx=10)

        # 2. DÖNEM
        tk.Label(secim_frame, text="2. Dönem (Hedef):", font=("Segoe UI", 10), bg="#f0f2f5", fg="#555").pack(side=tk.LEFT)
        self.yil2_cb = ttk.Combobox(secim_frame, values=yillar, width=6, state="readonly")
        self.yil2_cb.set(su_an_yil)
        self.yil2_cb.pack(side=tk.LEFT, padx=(5, 0))

        self.ceyrek2_cb = ttk.Combobox(secim_frame, values=ceyrekler, width=4, state="readonly")
        self.ceyrek2_cb.set("12")
        self.ceyrek2_cb.pack(side=tk.LEFT, padx=(5, 0))

        # HESAPLAMA MODU (Radyo Butonları)
        self.hesap_modu = tk.StringVar(value="izole")
        mod_frame = tk.Frame(secim_frame, bg="#f0f2f5")
        mod_frame.pack(side=tk.LEFT, padx=20)

        tk.Radiobutton(mod_frame, text="Kümülatif (Yıllık Toplam)", variable=self.hesap_modu, value="kumulatif", bg="#f0f2f5").pack(anchor=tk.W)
        tk.Radiobutton(mod_frame, text="İzole Çeyrek (Örn: Sadece 4. Çeyrek)", variable=self.hesap_modu, value="izole", bg="#f0f2f5", fg="#d35400", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

        # BUTONLAR
        self.basla_btn = tk.Button(secim_frame, text="Analizi Başlat", bg="#2ea44f", fg="white", font=("Segoe UI", 10, "bold"),
                                   relief="flat", cursor="hand2", padx=15, pady=5, command=self.islemi_baslat)
        self.basla_btn.pack(side=tk.LEFT, padx=10)

        self.excel_btn = tk.Button(secim_frame, text="Excel'e Aktar", bg="#0078D7", fg="white", font=("Segoe UI", 10, "bold"),
                                   relief="flat", cursor="hand2", padx=15, pady=5, state=tk.DISABLED, command=self.excele_aktar)
        self.excel_btn.pack(side=tk.LEFT)

        # --- ORTA PANEL ---
        orta_frame = tk.Frame(self.root, bg="#f0f2f5", bd=0)
        orta_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        tree_scroll_y = tk.Scrollbar(orta_frame, orient="vertical")
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x = tk.Scrollbar(orta_frame, orient="horizontal")
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree = ttk.Treeview(orta_frame, yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)

        self.tree.tag_configure('tek_satir', background='#f9fafc')
        self.tree.tag_configure('cift_satir', background='#ffffff')

        # --- ALT PANEL ---
        alt_frame = tk.Frame(self.root, bg="#f0f2f5", padx=15, pady=15)
        alt_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.log_ekrani = tk.Text(alt_frame, height=5, state=tk.DISABLED, bg="#1e1e1e", fg="#00ffcc",
                                  font=("Consolas", 10), relief="flat", padx=10, pady=10)
        self.log_ekrani.pack(fill=tk.X)

    def log_yaz(self, mesaj):
        self.log_ekrani.config(state=tk.NORMAL)
        self.log_ekrani.insert(tk.END, mesaj + "\n")
        self.log_ekrani.see(tk.END)
        self.log_ekrani.config(state=tk.DISABLED)

    def islemi_baslat(self):
        hisse_metni = self.hisse_entry.get()
        if not hisse_metni.strip(): return

        self.hisse_listesi = [h.strip().upper() for h in hisse_metni.split(',')]

        self.y1, self.c1 = self.yil1_cb.get(), self.ceyrek1_cb.get()
        self.y2, self.c2 = self.yil2_cb.get(), self.ceyrek2_cb.get()

        self.basla_btn.config(state=tk.DISABLED, text="Hesaplanıyor...", bg="#6e7681")
        self.excel_btn.config(state=tk.DISABLED)
        self.tree.delete(*self.tree.get_children())
        self.ana_tablo = pd.DataFrame()

        threading.Thread(target=self.verileri_cek_ve_hesapla).start()

    def verileri_cek_ve_hesapla(self):
        analiz_sonuclari = []
        min_yil = min(int(self.y1), int(self.y2))
        max_yil = max(int(self.y1), int(self.y2))

        mod = self.hesap_modu.get()
        mod_metin = "İzole Çeyrek (Q)" if mod == "izole" else "Kümülatif Toplam"
        self.log_yaz(f">>> Analiz Başlatıldı: {self.y2}/{self.c2} vs {self.y1}/{self.c1} | Mod: {mod_metin}")

        for hisse in self.hisse_listesi:
            try:
                self.log_yaz(f"[BAĞLANTI] {hisse} verileri çekiliyor...")
                df = fetch_financials(
                    symbols=[hisse],
                    start_year=str(min_yil),
                    end_year=str(max_yil),
                    exchange='TRY',
                    financial_group='1'
                )

                if df is not None and not df.empty:
                    hesaplanmis_satir = self.analiz_yap(df, hisse, self.y1, self.c1, self.y2, self.c2, mod)
                    if hesaplanmis_satir:
                        analiz_sonuclari.append(hesaplanmis_satir)
                        self.log_yaz(f"[BAŞARILI] {hisse} hesaplandı.")
                    else:
                        self.log_yaz(f"[UYARI] {hisse} için gerekli dönem eksik.")
                else:
                    self.log_yaz(f"[UYARI] {hisse} bilançosu bulunamadı.")
            except Exception as e:
                self.log_yaz(f"[HATA] {hisse}: {str(e)}")

            time.sleep(1.5)

        if analiz_sonuclari:
            self.log_yaz(">>> Tablo oluşturuluyor...")
            self.ana_tablo = pd.DataFrame(analiz_sonuclari)
            self.tabloyu_olustur(self.ana_tablo)
            self.excel_btn.config(state=tk.NORMAL)
        else:
            self.log_yaz("[SONUÇ] Eşleşen veri bulunamadı.")

        self.basla_btn.config(state=tk.NORMAL, text="Analizi Başlat", bg="#2ea44f")

    def analiz_yap(self, df, hisse, y1, c1, y2, c2, mod):

        def ham_deger_getir(donem, aranan_kelimeler):
            if donem not in df.columns: return 0.0
            isimler = df['FINANCIAL_ITEM_NAME_TR'].astype(str).str.strip().str.replace('I', 'ı').str.replace('İ', 'i').str.lower()
            for kelime in aranan_kelimeler:
                hedef = kelime.replace('I', 'ı').replace('İ', 'i').lower()
                satir = df[isimler == hedef]
                if not satir.empty:
                    try:
                        deger = float(satir[donem].iloc[0])
                        return deger if pd.notna(deger) else 0.0
                    except: pass
            return 0.0

        def deger_hesapla(yil, ceyrek, aranan_kelimeler, gelir_tablosu_mu=True):
            """İzole Q hesaplaması için kritik fonksiyon (12A - 9A yapar)"""
            hedef_donem = f"{yil}/{ceyrek}"
            hedef_deger = ham_deger_getir(hedef_donem, aranan_kelimeler)

            if mod == "kumulatif" or not gelir_tablosu_mu or ceyrek == "3":
                return hedef_deger # Çıkarma işlemi yapma

            # İzole Çeyrek isteniyorsa ve kalem Gelir Tablosuysa, önceki çeyreği bul ve çıkar
            onceki_ceyrek = str(int(ceyrek) - 3)
            onceki_donem = f"{yil}/{onceki_ceyrek}"
            onceki_deger = ham_deger_getir(onceki_donem, aranan_kelimeler)

            return hedef_deger - onceki_deger

        # Kelime Havuzu
        k_ciro = ['Hasılat', 'Satış Gelirleri', 'Net Satışlar', 'Faiz Gelirleri']
        k_faal = ['Esas Faaliyet Karı (Zararı)', 'Faaliyet Karı (Zararı)', 'Net Faaliyet Kar/Zararı']
        k_amort = ['Amortisman Giderleri', 'Amortisman ve İtfa Giderleri', 'Amortisman']
        k_net = ['Ana Ortaklık Payları', 'Dönem Karı (Zararı)', 'Net Dönem Karı/Zararı']
        k_ozk = ['Ana Ortaklığa Ait Özkaynaklar', 'Toplam Özkaynaklar', 'Özkaynaklar'] # Bilanço (Çıkarılmaz)

        # Yeni Dönem Hesapları (Gelir Tablosu kalemleri için True, Bilanço için False gönderiyoruz)
        ciro_yeni = deger_hesapla(y2, c2, k_ciro, True)
        faal_yeni = deger_hesapla(y2, c2, k_faal, True)
        amort_yeni = deger_hesapla(y2, c2, k_amort, True)
        net_yeni = deger_hesapla(y2, c2, k_net, True)
        ozk_yeni = deger_hesapla(y2, c2, k_ozk, False)
        favok_yeni = faal_yeni + amort_yeni

        # Eski Dönem Hesapları
        ciro_eski = deger_hesapla(y1, c1, k_ciro, True)
        faal_eski = deger_hesapla(y1, c1, k_faal, True)
        amort_eski = deger_hesapla(y1, c1, k_amort, True)
        net_eski = deger_hesapla(y1, c1, k_net, True)
        ozk_eski = deger_hesapla(y1, c1, k_ozk, False)
        favok_eski = faal_eski + amort_eski

        # Formatlama
        def buyume(yeni, eski):
            if eski == 0: return "% 0.00"
            oran = ((yeni - eski) / abs(eski)) * 100
            return f"% {'+' if oran > 0 else ''}{oran:.2f}"

        def milyon_tl(deger):
            return f"{deger / 1_000_000:,.1f} Mn".replace(',', 'X').replace('.', ',').replace('X', '.')

        favok_marji_yeni = (favok_yeni / ciro_yeni * 100) if ciro_yeni != 0 else 0
        favok_marji_eski = (favok_eski / ciro_eski * 100) if ciro_eski != 0 else 0
        marj_farki = favok_marji_yeni - favok_marji_eski

        gosterge_mod = f" (Sadece Q{int(c2)//3})" if mod == "izole" else " (Kümülatif)"

        return {
            "Hisse": hisse,
            "Karşılaştırma": f"{y2}/{c2} vs {y1}/{c1}{gosterge_mod}",
            "Yeni Ciro": milyon_tl(ciro_yeni),
            "Ciro Büyümesi": buyume(ciro_yeni, ciro_eski),
            "Yeni FAVÖK": milyon_tl(favok_yeni),
            "FAVÖK Büyümesi": buyume(favok_yeni, favok_eski),
            "Yeni FAVÖK Marjı": f"% {favok_marji_yeni:.1f} ({'+' if marj_farki > 0 else ''}{marj_farki:.1f} Puan)",
            "Yeni Net Kar": milyon_tl(net_yeni),
            "Net Kar Büyümesi": buyume(net_yeni, net_eski),
            "Özkaynak Büyümesi": buyume(ozk_yeni, ozk_eski) # Bilanço kalemi olduğu için Q izolasyonundan etkilenmez
        }

    def tabloyu_olustur(self, df):
        self.tree["column"] = list(df.columns)
        self.tree["show"] = "headings"
        for col in self.tree["column"]:
            self.tree.heading(col, text=col)
            genislik = 60 if col == "Hisse" else 110
            self.tree.column(col, width=genislik, anchor=tk.CENTER)

        df_satirlari = df.to_numpy().tolist()
        for i, satir in enumerate(df_satirlari):
            self.tree.insert("", "end", values=satir, tags=('cift_satir' if i % 2 == 0 else 'tek_satir',))

    def excele_aktar(self):
        if self.ana_tablo.empty: return
        dosya_adi = f"BIST_Analiz_{self.y2}_{self.c2}_vs_{self.y1}_{self.c1}_{self.hesap_modu.get()}.xlsx"
        dosya_yolu = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")], initialfile=dosya_adi)
        if dosya_yolu:
            self.ana_tablo.to_excel(dosya_yolu, index=False)
            messagebox.showinfo("Başarılı", "Veriler Excel'e aktarıldı!")

if __name__ == "__main__":
    root = tk.Tk()
    app = EsnekBilancoTerminali(root)
    root.mainloop()