#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PdM Database Viewer - SQLite database görüntüleme ve sorgulama aracı
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from pathlib import Path
from database_manager import PdMDatabaseManager
import json
import csv
from datetime import datetime, timezone
from typing import List, Dict
import webbrowser
try:
    import matplotlib
    matplotlib.use('Agg')  # Headless backend; canvas will render via TkAgg
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
    HAS_MPL = True
except Exception:
    HAS_MPL = False

"""LEGACY VIEWER DISABLED

The following legacy implementation was kept in the repository but is now
disabled to avoid duplication and mojibake issues. Please use DatabaseViewer
below.
"""

class DatabaseViewerLegacy:
    """Database görüntüleme GUI sınıfı"""
    
    def __init__(self, root):
        """GUI başlat"""
        self.root = root
        self.root.title("📊 PdM Database Viewer")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')
        
        # DB kaynağı seçimi (PdM DB / Local DB / Özel dosya)
        # Sadelik: yalnızca PdM DB kullanılır

        # Varsayılan: PdM DB
        self.db_manager = PdMDatabaseManager()
        
        # Tekil pencereler (tekrar açılmayı engellemek için referans sakla)
        self.stats_window = None
        self.search_window = None
        self.detail_window = None
        self.search_window = None
        
        # Gelişmiş metin düzeltici kullan (mojibake temizleme)
        try:
            self._fix_text = self._fix_text_enhanced
        except Exception:
            pass
        _dv_create_widgets(self)
        # Pencere başlığını normalize et
        try:
            self.root.title(self._fix_text("PdM Database Viewer"))
        except Exception:
            pass
        self.refresh_data()

    def create_widgets(self):
        """Sade (PdM DB) arayüzünü oluştur."""
        # Başlık
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=60)
        title_frame.pack(fill='x', pady=(0, 10))
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="PdM Database Viewer", font=('Arial', 18, 'bold'), bg='#2c3e50', fg='white').pack(expand=True)

        # Üst kontrol butonları
        control_frame = tk.Frame(self.root, bg='#f0f0f0')
        control_frame.pack(fill='x', padx=10, pady=5)
        tk.Button(control_frame, text="Yenile", command=self.refresh_data, font=('Arial', 10, 'bold'), bg='#3498db', fg='white', width=12).pack(side='left', padx=5)
        tk.Button(control_frame, text="İstatistikler", command=self.show_statistics, font=('Arial', 10, 'bold'), bg='#27ae60', fg='white', width=12).pack(side='left', padx=5)
        tk.Button(control_frame, text="Arıza Ara", command=self.search_failures, font=('Arial', 10, 'bold'), bg='#e74c3c', fg='white', width=12).pack(side='left', padx=5)
        tk.Button(control_frame, text="Export", command=self.export_data, font=('Arial', 10, 'bold'), bg='#9b59b6', fg='white', width=12).pack(side='left', padx=5)

        # Filtre bölümü
        filter_frame = tk.LabelFrame(self.root, text="Filtreler", font=('Arial', 10, 'bold'), bg='#f0f0f0', padx=10, pady=5)
        filter_frame.pack(fill='x', padx=10, pady=5)

        # Limit
        tk.Label(filter_frame, text="Kayıt:", bg='#f0f0f0').pack(side='left')
        self.limit_var = tk.IntVar(value=50)
        limit_spin = tk.Spinbox(filter_frame, from_=10, to=1000, textvariable=self.limit_var, width=8)
        limit_spin.pack(side='left', padx=5)
        limit_spin.bind('<Return>', lambda e: self.apply_filters())
        limit_spin.bind('<KP_Enter>', lambda e: self.apply_filters())

        # Tahmin filtresi
        tk.Label(filter_frame, text="Tahmin:", bg='#f0f0f0').pack(side='left', padx=(15,5))
        self.prediction_var = tk.StringVar(value="Tümü")
        prediction_combo = ttk.Combobox(filter_frame, textvariable=self.prediction_var, values=["Tümü", "Normal (0)", "Arıza (1)"], width=10)
        prediction_combo.pack(side='left', padx=5)
        prediction_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())

        # Makine tipi filtresi
        tk.Label(filter_frame, text="Tip:", bg='#f0f0f0').pack(side='left', padx=(15,5))
        self.machine_type_var = tk.StringVar(value="Tümü")
        machine_combo = ttk.Combobox(filter_frame, textvariable=self.machine_type_var, values=["Tümü", "L", "M", "H"], width=6)
        machine_combo.pack(side='left', padx=5)
        machine_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())

        # Blockchain filtresi
        tk.Label(filter_frame, text="Blockchain:", bg='#f0f0f0').pack(side='left', padx=(15,5))
        self.blockchain_var = tk.StringVar(value="Tümü")
        bc_combo = ttk.Combobox(filter_frame, textvariable=self.blockchain_var, values=["Tümü", "Başarılı", "Başarısız"], width=10)
        bc_combo.pack(side='left', padx=5)
        bc_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())

        # Filtre uygula/temizle
        tk.Button(filter_frame, text="Filtrele", command=self.apply_filters, font=('Arial', 8, 'bold'), bg='#f39c12', fg='white', width=8).pack(side='left', padx=8)
        tk.Button(filter_frame, text="Temizle", command=self.clear_filters, font=('Arial', 8, 'bold'), bg='#95a5a6', fg='white', width=8).pack(side='left', padx=5)

        # Tarih aralığı
        date_frame = tk.Frame(filter_frame, bg='#f0f0f0')
        date_frame.pack(fill='x', pady=(10, 0))
        tk.Label(date_frame, text="Başlangıç:", bg='#f0f0f0').pack(side='left')
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.start_date_widget = tk.Entry(date_frame, textvariable=self.start_date_var, width=12)
        self.start_date_widget.pack(side='left', padx=5)
        self.start_date_widget.insert(0, "YYYY-MM-DD")
        self.start_date_widget.bind('<FocusIn>', lambda e: self._clear_placeholder(e, "YYYY-MM-DD"))
        self.start_date_widget.bind('<FocusOut>', lambda e: self._restore_placeholder(e, "YYYY-MM-DD"))
        self.start_date_widget.bind('<Return>', lambda e: self.apply_filters())
        self.start_date_widget.bind('<KP_Enter>', lambda e: self.apply_filters())
        tk.Label(date_frame, text="Bitiş:", bg='#f0f0f0').pack(side='left', padx=(15,5))
        self.end_date_widget = tk.Entry(date_frame, textvariable=self.end_date_var, width=12)
        self.end_date_widget.pack(side='left', padx=5)
        self.end_date_widget.insert(0, "YYYY-MM-DD")
        self.end_date_widget.bind('<FocusIn>', lambda e: self._clear_placeholder(e, "YYYY-MM-DD"))
        self.end_date_widget.bind('<FocusOut>', lambda e: self._restore_placeholder(e, "YYYY-MM-DD"))
        self.end_date_widget.bind('<Return>', lambda e: self.apply_filters())
        self.end_date_widget.bind('<KP_Enter>', lambda e: self.apply_filters())

        # Ana tablo
        table_frame = tk.Frame(self.root)
        table_frame.pack(fill='both', expand=True, padx=10, pady=5)
        columns = ('ID', 'Zaman', 'Veri Kanıtı', 'Hava Sıc.', 'İşlem Sıc.', 'Dönüş Hızı', 'Tork', 'Aşınma', 'Tip', 'Tahmin', 'Olasılık', 'Neden', 'Analiz S.', 'Blockchain')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        widths = [50, 120, 180, 80, 80, 90, 70, 70, 50, 70, 80, 150, 80, 100]
        for col, w in zip(columns, widths):
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_by_column(c))
            self.tree.column(col, width=w, anchor='center')
        vscroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vscroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vscroll.pack(side='right', fill='y')
        self.tree.tag_configure('failure', background='#ffcdd2')
        self.tree.tag_configure('normal', background='#e8f5e8')
        self.tree.bind('<Double-1>', self.on_item_double_click)

        # Durum çubuğu
        status_frame = tk.Frame(self.root, bg='#34495e', height=30)
        status_frame.pack(fill='x', side='bottom')
        status_frame.pack_propagate(False)
        self.status_label = tk.Label(status_frame, text="Hazır", bg='#34495e', fg='white', font=('Arial', 9))
        self.status_label.pack(side='left', padx=10, pady=5)
        self.loading_var = tk.BooleanVar(value=False)
        self.progressbar = ttk.Progressbar(status_frame, mode='indeterminate', length=150)
        self.progressbar.pack(side='right', padx=10)
        self.progressbar.stop()

    def create_widgets(self):
        """GUI bileşenlerini oluştur"""
        # Ana başlık
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=60)
        title_frame.pack(fill='x', pady=(0, 10))
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(title_frame, text="PdM Database Viewer", 
                              font=('Arial', 18, 'bold'), 
                              bg='#2c3e50', fg='white')
        title_label.pack(expand=True)
        
        # Kontrol paneli
        control_frame = tk.Frame(self.root, bg='#f0f0f0')
        control_frame.pack(fill='x', padx=10, pady=5)

        # Butonlar
        tk.Button(control_frame, text="Yenile", command=self.refresh_data,
                   font=('Arial', 10, 'bold'), bg='#3498db', fg='white',
                   width=12).pack(side='left', padx=5)
        
        tk.Button(control_frame, text="İstatistikler", command=self.show_statistics,
                 font=('Arial', 10, 'bold'), bg='#27ae60', fg='white',
                 width=12).pack(side='left', padx=5)
        
        tk.Button(control_frame, text="Arıza Ara", command=self.search_failures,
                 font=('Arial', 10, 'bold'), bg='#e74c3c', fg='white',
                 width=12).pack(side='left', padx=5)
        
        tk.Button(control_frame, text="Export", command=self.export_data,
                  font=('Arial', 10, 'bold'), bg='#9b59b6', fg='white',
                  width=12).pack(side='left', padx=5)


        # DB kaynağı seçimi kaldırıldı (yalnızca PdM DB)
        
        # Filtre frame
        filter_frame = tk.LabelFrame(self.root, text="Filtreler", 
                                   font=('Arial', 10, 'bold'),
                                   bg='#f0f0f0', padx=10, pady=5)
        filter_frame.pack(fill='x', padx=10, pady=5)
        
        # Limit kontrolü
        tk.Label(filter_frame, text="Kayıt:", bg='#f0f0f0').pack(side='left')
        self.limit_var = tk.IntVar(value=50)
        limit_spin = tk.Spinbox(
            filter_frame,
            from_=10,
            to=1000,
            textvariable=self.limit_var,
            width=8
        )
        limit_spin.pack(side='left', padx=5)
        # Enter ile filtrelemeyi tetikle
        limit_spin.bind('<Return>', lambda e: self.apply_filters())
        limit_spin.bind('<KP_Enter>', lambda e: self.apply_filters())
        
        # Tahmin filtresi
        tk.Label(filter_frame, text="Tahmin:", bg='#f0f0f0').pack(side='left', padx=(15,5))
        self.prediction_var = tk.StringVar(value="Tümü")
        prediction_combo = ttk.Combobox(filter_frame, textvariable=self.prediction_var,
                                      values=["Tümü", "Normal (0)", "Arıza (1)"], width=10)
        prediction_combo.pack(side='left', padx=5)
        # Enter / seçimde filtrele
        prediction_combo.bind('<Return>', lambda e: self.apply_filters())
        prediction_combo.bind('<KP_Enter>', lambda e: self.apply_filters())
        prediction_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())
        
        # Makine tipi filtresi
        tk.Label(filter_frame, text="Makine:", bg='#f0f0f0').pack(side='left', padx=(15,5))
        self.machine_type_var = tk.StringVar(value="Tümü")
        machine_combo = ttk.Combobox(filter_frame, textvariable=self.machine_type_var,
                                   values=["Tümü", "L", "M", "H"], width=6)
        machine_combo.pack(side='left', padx=5)
        machine_combo.bind('<Return>', lambda e: self.apply_filters())
        machine_combo.bind('<KP_Enter>', lambda e: self.apply_filters())
        machine_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())
        
        # Blockchain durumu filtresi
        tk.Label(filter_frame, text="Blockchain:", bg='#f0f0f0').pack(side='left', padx=(15,5))
        self.blockchain_var = tk.StringVar(value="Tümü")
        blockchain_combo = ttk.Combobox(filter_frame, textvariable=self.blockchain_var,
                                      values=["Tümü", "Başarılı", "Başarısız"], width=8)
        blockchain_combo.pack(side='left', padx=5)
        blockchain_combo.bind('<Return>', lambda e: self.apply_filters())
        blockchain_combo.bind('<KP_Enter>', lambda e: self.apply_filters())
        blockchain_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())
        
        # Filtre uygula butonu
        tk.Button(filter_frame, text="Filtrele", command=self.apply_filters,
                 font=('Arial', 8, 'bold'), bg='#f39c12', fg='white', width=8).pack(side='left', padx=8)
        
        # Filtreleri temizle butonu
        tk.Button(filter_frame, text="Temizle", command=self.clear_filters,
                 font=('Arial', 8, 'bold'), bg='#95a5a6', fg='white', width=8).pack(side='left', padx=5)
        
        # İkinci satır - Tarih aralığı filtresi
        date_frame = tk.Frame(filter_frame, bg='#f0f0f0')
        date_frame.pack(fill='x', pady=(10, 0))
        
        # Başlangıç/Bitiş tarihi (tkcalendar varsa DateEntry)
        tk.Label(date_frame, text="Başlangıç:", bg='#f0f0f0').pack(side='left')
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        try:
            from tkcalendar import DateEntry  # type: ignore
            self.start_date_widget = DateEntry(date_frame, textvariable=self.start_date_var, width=12, date_pattern='yyyy-mm-dd')
            self.start_date_widget.pack(side='left', padx=5)
            self.start_date_widget.bind('<Return>', lambda e: self.apply_filters())
            self.start_date_widget.bind('<KP_Enter>', lambda e: self.apply_filters())
            tk.Label(date_frame, text="Bitiş:", bg='#f0f0f0').pack(side='left', padx=(15,5))
            self.end_date_widget = DateEntry(date_frame, textvariable=self.end_date_var, width=12, date_pattern='yyyy-mm-dd')
            self.end_date_widget.pack(side='left', padx=5)
            self.end_date_widget.bind('<Return>', lambda e: self.apply_filters())
            self.end_date_widget.bind('<KP_Enter>', lambda e: self.apply_filters())
        except Exception:
            # Yedek: normal Entry + placeholder
            self.start_date_widget = tk.Entry(date_frame, textvariable=self.start_date_var, width=12)
            self.start_date_widget.pack(side='left', padx=5)
            self.start_date_widget.insert(0, "YYYY-MM-DD")
            self.start_date_widget.bind('<FocusIn>', lambda e: self._clear_placeholder(e, "YYYY-MM-DD"))
            self.start_date_widget.bind('<FocusOut>', lambda e: self._restore_placeholder(e, "YYYY-MM-DD"))
            self.start_date_widget.bind('<Return>', lambda e: self.apply_filters())
            self.start_date_widget.bind('<KP_Enter>', lambda e: self.apply_filters())
            tk.Label(date_frame, text="Bitiş:", bg='#f0f0f0').pack(side='left', padx=(15,5))
            self.end_date_widget = tk.Entry(date_frame, textvariable=self.end_date_var, width=12)
            self.end_date_widget.pack(side='left', padx=5)
            self.end_date_widget.insert(0, "YYYY-MM-DD")
            self.end_date_widget.bind('<FocusIn>', lambda e: self._clear_placeholder(e, "YYYY-MM-DD"))
            self.end_date_widget.bind('<FocusOut>', lambda e: self._restore_placeholder(e, "YYYY-MM-DD"))
            self.end_date_widget.bind('<Return>', lambda e: self.apply_filters())
            self.end_date_widget.bind('<KP_Enter>', lambda e: self.apply_filters())
        
        # Hızlı tarih seçenekleri - daha kompakt
        tk.Label(date_frame, text="Hızlı:", bg='#f0f0f0').pack(side='left', padx=(15,5))
        quick_date_btn = tk.Button(date_frame, text="7 Gün", command=lambda: self._set_quick_date(7),
                                  font=('Arial', 8), bg='#3498db', fg='white', width=6)
        quick_date_btn.pack(side='left', padx=2)
        
        quick_date_btn2 = tk.Button(date_frame, text="30 Gün", command=lambda: self._set_quick_date(30),
                                   font=('Arial', 8), bg='#3498db', fg='white', width=6)
        quick_date_btn2.pack(side='left', padx=2)
        
        # Treeview (tablo)
        tree_frame = tk.Frame(self.root)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Scrollbar'lar
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical')
        v_scrollbar.pack(side='right', fill='y')
        
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal')
        h_scrollbar.pack(side='bottom', fill='x')
        
        # Treeview
        columns = ('ID', 'Zaman', 'Veri Kanıtı', 'Hava Sıc.', 'İşlem Sıc.', 'Dönüş Hızı', 'Tork', 
          'Aşınma', 'Tip', 'Tahmin', 'Olasılık', 'Neden', 'Analiz S.', 'Blockchain')
        
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                yscrollcommand=v_scrollbar.set,
                                xscrollcommand=h_scrollbar.set)
        
        # Column başlıkları ve genişlikleri
        col_widths = [50, 120, 180, 80, 80, 90, 70, 70, 50, 70, 80, 150, 80, 100]
        for i, (col, width) in enumerate(zip(columns, col_widths)):
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_by_column(c))
            self.tree.column(col, width=width, minwidth=50)
        
        # Sıralama durumu takibi
        self.sort_column = None
        self.sort_reverse = False
        
        self.tree.pack(fill='both', expand=True)
        
        # Scrollbar bağlantıları
        v_scrollbar.config(command=self.tree.yview)
        h_scrollbar.config(command=self.tree.xview)

        # Sağ tık menüsü
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="Detay Göster", command=self._ctx_show_detail)
        self.tree_menu.add_command(label="CSV'ye Aktar (Seçili)", command=self._ctx_export_selected)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="TX Hash'i Kopyala", command=self._ctx_copy_tx_hash)
        self.tree_menu.add_command(label="Explorer'da Aç", command=self._ctx_open_explorer)
        self.tree.bind('<Button-3>', self._on_tree_right_click)
        
        # Durum çubuğu
        status_frame = tk.Frame(self.root, bg='#34495e', height=30)
        status_frame.pack(fill='x', side='bottom')
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="Hazır",
                                   bg='#34495e', fg='white', font=('Arial', 9))
        self.status_label.pack(side='left', padx=10, pady=5)

        # Yükleme göstergesi (non-blocking)
        self.loading_var = tk.BooleanVar(value=False)
        self.progressbar = ttk.Progressbar(status_frame, mode='indeterminate', length=150)
        self.progressbar.pack(side='right', padx=10)
        self.progressbar.stop()
        
        # Double-click event
        self.tree.bind('<Double-1>', self.on_item_double_click)
        # Normalize any mojibake texts in UI widgets
        try:
            self._normalize_widget_texts()
        except Exception:
            pass
class DatabaseViewer:
    """Database görüntüleme GUI sınıfı"""
    
    def __init__(self, root):
        """GUI başlat"""
        self.root = root
        self.root.title("📊 PdM Database Viewer")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')
        
        # DB kaynağı seçimi (PdM DB / Local DB / Özel dosya)
        self.db_source_var = tk.StringVar(value='PdM DB')
        self.db_path_var = tk.StringVar(value='')

        # Varsayılan: PdM DB
        self.db_manager = PdMDatabaseManager()
        try:
            self.db_path_var.set(str(self.db_manager.db_path))
        except Exception:
            pass
        # Tekil pencereler (tekrar açılmayı engellemek için referans sakla)
        self.stats_window = None
        self.search_window = None
        self.detail_window = None
        self.search_window = None
        
        _dv_create_widgets(self)
        self.refresh_data()
        
        
    def refresh_data(self):
        """Verileri yenile"""
        try:
            self._start_loading("Veriler yükleniyor...")
            
            # Sıralama durumunu sıfırla
            self.sort_column = None
            self.sort_reverse = False
            
            # Verileri getir ve yükle (ana sayfa görünümü: en yeni → en eski)
            # Varsayılan: tüm veriler
            records = self.db_manager.get_sensor_data(limit=self.limit_var.get() if hasattr(self, 'limit_var') else 100)
            self._load_data(records)
            
        except Exception as e:
            messagebox.showerror("Hata", f"Veri yükleme hatası: {e}")
            self.status_label.config(text="❌ Hata oluştu")

    # --- DB Kaynağı Yardımcıları ---
    def _on_db_source_change(self):
        pass

    def _choose_db_file(self):
        pass

    def _update_db_path_label(self):
        pass
    
    def apply_filters(self):
        """Filtreleri uygula"""
        try:
            self._start_loading("Filtreler uygulanıyor...")
            
            # Sıralama durumunu sıfırla
            self.sort_column = None
            self.sort_reverse = False
            
            # Aktif filtreleri al ve verileri yükle
            filters = self._get_active_filters()
            # Filtre değerlerini normalize et (mojibake ve farklı yazımlara dayanıklı)
            try:
                pf = filters.get('prediction_filter_db')
                if isinstance(pf, str):
                    s = pf.strip()
                    if s in ("0", "Normal", "Normal (0)"):
                        filters['prediction_filter_db'] = "Normal"
                    elif s in ("1", "Arıza", "Arıza (1)", "Ar�za", "Ar�za (1)", "Ar��za", "Ar��za (1)"):
                        filters['prediction_filter_db'] = "Arıza"
                bf = filters.get('blockchain_filter_db')
                if isinstance(bf, str):
                    b = bf.strip()
                    if b in ("Tümü", "T�m�", ""):
                        filters['blockchain_filter_db'] = None
                    elif b in ("Başarılı", "Ba�ar�l�", "Ba�Yar��l��"):
                        filters['blockchain_filter_db'] = "Başarılı"
                    elif b in ("Başarısız", "Ba�ar�s�z", "Ba�Yar��s��z"):
                        filters['blockchain_filter_db'] = "Başarısız"
            except Exception:
                pass
            records = self.db_manager.get_sensor_data(
                limit=filters['limit'],
                prediction_filter=filters['prediction_filter_db'],
                machine_type_filter=filters['machine_type_filter_db'],
                blockchain_filter=filters['blockchain_filter_db'],
                start_date=filters['start_date_db'],
                end_date=filters['end_date_db']
            )
            # Filtre modunda: en eskiden yeniye (ilk tahminden itibaren)
            records = list(reversed(records))
            self._load_data(records)
            
        except Exception as e:
            messagebox.showerror("Hata", f"Filtreleme hatası: {e}")
            self.status_label.config(text="❌ Filtreleme hatası")
    
    def clear_filters(self):
        """Filtreleri temizle ve tüm verileri göster"""
        try:
            # Filtre değerlerini sıfırla
            self.prediction_var.set("Tümü")
            self.machine_type_var.set("Tümü")
            self.blockchain_var.set("Tümü")
            self.start_date_var.set("")
            self.end_date_var.set("")
            # Kayıt limiti varsayılan değere dönsün
            try:
                self.limit_var.set(50)
            except Exception:
                pass
            # Date widget'larını resetle
            try:
                # DateEntry ise delete ile temizle
                if hasattr(self, 'start_date_widget') and hasattr(self.start_date_widget, 'set_date'):
                    self.start_date_widget.set_date('')
                if hasattr(self, 'end_date_widget') and hasattr(self.end_date_widget, 'set_date'):
                    self.end_date_widget.set_date('')
            except Exception:
                pass
            
            # Verileri yenile (varsayÄ±lan: en yeni → en eski)
            self.refresh_data()
            
            self.status_label.config(text="✅ Filtreler temizlendi")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Filtre temizleme hatası: {e}")
            self.status_label.config(text="❌ Filtre temizleme hatası")
    
    def _populate_tree(self, records: List[Dict]):
        """
        Treeview'i verilen kayıt listesi ile doldurur
        
        Args:
            records: Veritabanından gelen kayıt listesi
        """
        for record in records:
            # Veriyi formatla (database_manager.format_record)
            formatted = self._get_formatted_record_values(record)
            
            # Treeview için değerleri hazırla
            values = (
                formatted['id'], formatted['time_str'], formatted['data_hash_short'], formatted['air_temp'],
                formatted['process_temp'], formatted['rotation_speed'], formatted['torque'],
                formatted['tool_wear'], formatted['machine_type'], formatted['pred_text'],
                formatted['prob_text'], formatted['reason_short'], formatted['analysis_text'],
                formatted['bc_text']
            )
            
            # Renk kodlama ile ekle
            if formatted['prediction'] == 1:
                self.tree.insert('', 'end', values=values, tags=('failure',))
            elif formatted['prediction'] == 0:
                self.tree.insert('', 'end', values=values, tags=('normal',))
            else:
                self.tree.insert('', 'end', values=values)
        
        # Tag renklerini yapılandır
        self.tree.tag_configure('failure', background='#ffcdd2')
        self.tree.tag_configure('normal', background='#e8f5e8')
    
    def _start_loading(self, message: str):
        """Durum çubuğunda yükleme göstergesini başlatır."""
        try:
            self.status_label.config(text=self._fix_text(message))
            if not self.loading_var.get():
                self.loading_var.set(True)
                self.progressbar.start(12)
        except Exception:
            pass

    def _stop_loading(self, final_message: str):
        """Yükleme göstergesini durdurur ve mesajı günceller."""
        try:
            self.loading_var.set(False)
            self.progressbar.stop()
            self.status_label.config(text=self._fix_text(final_message))
        except Exception:
            pass

    def _on_limit_change(self):
        """(Kullanılmıyor) Limit değişikliğinde otomatik yenilemeyi devre dışı bıraktık."""
        pass

    def _populate_tree_async(self, records: List[Dict], chunk_size: int = 200):
        """Büyük veri setlerini GUI'yi kilitlemeden parça parça ekler."""
        # Önce tüm satırları temizle
        for item in self.tree.get_children():
            self.tree.delete(item)

        total = len(records)

        def insert_chunk(start_idx: int):
            end_idx = min(start_idx + chunk_size, total)
            for i in range(start_idx, end_idx):
                record = records[i]
                formatted = self._get_formatted_record_values(record)
                # Blockchain durum simgesi (✓/✗)
                try:
                    bc_text = '✓' if bool(record.get('blockchain_success', False)) else '✗'
                except Exception:
                    bc_text = formatted.get('bc_text') if isinstance(formatted, dict) else None
                values = (
                    formatted['id'], formatted['time_str'], formatted['data_hash_short'], formatted['air_temp'],
                    formatted['process_temp'], formatted['rotation_speed'], formatted['torque'],
                    formatted['tool_wear'], formatted['machine_type'], formatted['pred_text'],
                    formatted['prob_text'], formatted['reason_short'], formatted['analysis_text'],
                    bc_text if bc_text is not None else formatted['bc_text']
                )
                if formatted['prediction'] == 1:
                    self.tree.insert('', 'end', values=values, tags=('failure',))
                elif formatted['prediction'] == 0:
                    self.tree.insert('', 'end', values=values, tags=('normal',))
                else:
                    self.tree.insert('', 'end', values=values)

            if end_idx < total:
                # Sonraki chunk'ı planla
                self.root.after(1, lambda: insert_chunk(end_idx))
            else:
                # Tamamlandı
                self.update_column_headers()
                self._stop_loading(f"✅ {total} kayıt yüklendi")

        # Başlat
        if total == 0:
            self._stop_loading("⚠️ Kayıt bulunamadı")
            return
        self.root.after(1, lambda: insert_chunk(0))

    # ----- ORTAK FİLTRE OKUMA & DATA YÜKLEME -----
    def _get_active_filters(self) -> Dict:
        """GUI'deki aktif filtreleri okur, doğrular ve DB formatına çevirir."""
        limit = self.limit_var.get()
        prediction_filter = self._fix_text(self.prediction_var.get())
        machine_type_filter = self._fix_text(self.machine_type_var.get())
        blockchain_filter = self._fix_text(self.blockchain_var.get())
        start_date = self.start_date_var.get()
        end_date = self.end_date_var.get()

        prediction_filter_db = None
        if prediction_filter == "Normal (0)":
            prediction_filter_db = "Normal"
        elif prediction_filter == "Arıza (1)":
            prediction_filter_db = "Arıza"

        machine_type_filter_db = None if machine_type_filter == "Tümü" else machine_type_filter
        blockchain_filter_db = None if blockchain_filter == "Tümü" else blockchain_filter

        start_date_db = None
        end_date_db = None
        if start_date and start_date != "YYYY-MM-DD":
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                start_date_db = start_date
            except ValueError:
                messagebox.showerror("Hata", "Başlangıç tarihi formatı hatalı! (YYYY-MM-DD)")
                raise

        if end_date and end_date != "YYYY-MM-DD":
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
                end_date_db = end_date
            except ValueError:
                messagebox.showerror("Hata", "Bitiş tarihi formatı hatalı! (YYYY-MM-DD)")
                raise

        filter_info = []
        if prediction_filter != "Tümü":
            filter_info.append(f"Tahmin: {prediction_filter}")
        if machine_type_filter != "Tümü":
            filter_info.append(f"Makine: {machine_type_filter}")
        if blockchain_filter != "Tümü":
            filter_info.append(f"Blockchain: {blockchain_filter}")
        if start_date_db:
            filter_info.append(f"Başlangıç: {start_date_db}")
        if end_date_db:
            filter_info.append(f"Bitiş: {end_date_db}")

        return {
            'limit': limit,
            'prediction_filter_db': prediction_filter_db,
            'machine_type_filter_db': machine_type_filter_db,
            'blockchain_filter_db': blockchain_filter_db,
            'start_date_db': start_date_db,
            'end_date_db': end_date_db,
            'filter_info': filter_info
        }

    def _load_data(self, records: List[Dict]):
        """Listeyi non-blocking şekilde tabloya yükler ve başlıkları günceller."""
        self._populate_tree_async(records)
        self.update_column_headers()

    # ----- ENCODING YARDIMCILARI -----
    def _fix_text(self, s: str) -> str:
        """UTF-8 mojibake metinleri düzeltmeye çalışır (Ã, Ä, Å, ❌ kalıpları).
        Örn: 'Veri Kanıtı' -> 'Veri Kanıtı'. Başarısız olursa orijinali döner.
        """
        try:
            if isinstance(s, str) and any(ch in s for ch in ('Ã', 'Ä', 'Å', '❌')):
                return s.encode('latin1').decode('utf-8')
        except Exception:
            pass
        return s

    def _fix_text_enhanced(self, s: str) -> str:
        """Gelişmiş metin düzeltici: latin1->utf8 denemesi + bilinen Türkçe bozulmaları temizler."""
        try:
            if not isinstance(s, str):
                return s
            t = s
            # Olası latin1->utf8 tersine çevirme
            try:
                if any(ch in t for ch in ('�', '�', '�', '?')):
                    t = t.encode('latin1', errors='ignore').decode('utf-8', errors='ignore') or t
            except Exception:
                pass
            # Bilinen bozuk yazımlar
            repl = {
                'T�m�': 'Tümü', 'T?m?': 'Tümü', 'Kay�t': 'Kayıt', 'Ba�lang��': 'Başlangıç', 'Biti�': 'Bitiş',
                'Ba�ar�l�': 'Başarılı', 'Ba�ar�s�z': 'Başarısız', 'Ar�za': 'Arıza', 'Sens�r': 'Sensör',
                'Veritaban�': 'Veritabanı', 'G�ster': 'Göster', 'A�': 'Aç', 'S�re': 'Süre',
                'Veri Kan�t�': 'Veri Kanıtı', 'Hava S�c.': 'Hava Sıc.', '��lem S�c.': 'İşlem Sıc.',
                'D�n�� H�z�': 'Dönüş Hızı', 'A��nma': 'Aşınma', '�statistik': 'İstatistik',
                'Bulunamad�': 'Bulunamadı', 'Detay�': 'Detayı', 'Zaman�': 'Zamanı',
            }
            for k, v in repl.items():
                if k in t:
                    t = t.replace(k, v)
            return t
        except Exception:
            return s

    def _normalize_widget_texts(self, widget=None):
        try:
            if widget is None:
                widget = self.root
            for child in widget.winfo_children():
                try:
                    txt = child.cget('text')
                    fixed = self._fix_text(txt)
                    if fixed != txt:
                        child.config(text=fixed)
                except Exception:
                    pass
                # Recursive
                self._normalize_widget_texts(child)
        except Exception:
            pass

    def update_column_headers(self):
        """Treeview kolonu başlıklarını mojibake'ten arındır."""
        try:
            cols = self.tree['columns']
            for col in cols:
                current = self.tree.heading(col, 'text') or col
                self.tree.heading(col, text=self._fix_text(current))
        except Exception:
            pass
    
    def sort_by_column(self, col):
        """Sütuna göre sıralama yap"""
        try:
            # Mevcut verileri al
            data = []
            for item in self.tree.get_children():
                values = self.tree.item(item)['values']
                data.append(values)
            
            if not data:
                return
            
            # Sıralama mantığı
            if self.sort_column == col:
                # Aynı sütuna tekrar tıklandı
                if self.sort_reverse:
                    # 3. tıklama: Normal sıralama (orijinal)
                    self.sort_column = None
                    self.sort_reverse = False
                    # Orijinal verileri yeniden yükle
                    self.refresh_data()
                    return
                else:
                    # 2. tıklama: Ters sıralama
                    self.sort_reverse = True
            else:
                # 1. tıklama: Artan sıralama
                self.sort_column = col
                self.sort_reverse = False
            
            # Sütun indeksini dinamik olarak bul
            columns = tuple(self.tree['columns'])
            col_index = columns.index(col)
            
            # Sıralama fonksiyonu
            def sort_key(item):
                value = item[col_index]
                # Sayısal sütunlar: ID(0), Hava(3), İşlem(4), Hız(5), Tork(6), Aşınma(7), Analiz(12)
                numeric_idx = {0, 3, 4, 5, 6, 7, 12}
                if col_index in numeric_idx:
                    try:
                        # Sayısal değeri çıkar
                        if isinstance(value, str):
                            # "298.5K" -> 298.5
                            if 'K' in value:
                                return float(value.replace('K', ''))
                            # "42.8 Nm" -> 42.8
                            elif ' Nm' in value:
                                return float(value.replace(' Nm', ''))
                            # "1500 rpm" -> 1500
                            elif ' rpm' in value:
                                return float(value.replace(' rpm', ''))
                            # "100 min" -> 100
                            elif ' min' in value:
                                return float(value.replace(' min', ''))
                            # "0.1500s" -> 0.1500
                            elif 's' in value:
                                return float(value.replace('s', ''))
                            else:
                                return float(value)
                        else:
                            return float(value)
                    except (ValueError, TypeError):
                        return 0
                
                # Tarih için: Zaman sütunu (1)
                elif col_index == 1:
                    try:
                        from datetime import datetime, timezone
                        # "14.02.2025 17:10:20" formatını parse et
                        return datetime.strptime(value, '%d.%m.%Y %H:%M:%S')
                    except (ValueError, TypeError):
                        return datetime.min
                
                # Olasılık için: yüzde metni (10)
                elif col_index == 10:
                    try:
                        # "85.00%" -> 85.00
                        if isinstance(value, str) and '%' in value:
                            return float(value.replace('%', ''))
                        else:
                            return float(value)
                    except (ValueError, TypeError):
                        return 0
                
                # Diğer metin değerleri için
                else:
                    return str(value).lower()
            
            # Sırala
            data.sort(key=sort_key, reverse=self.sort_reverse)
            
            # Treeview'i temizle ve yeniden doldur
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            for values in data:
                # Orijinal tag'leri koru - Tahmin sütunu 8. indekste
                if len(values) > 8:  # Tahmin sütunu varsa
                    prediction = values[8]  # Tahmin sütunu
                    if prediction == 1 or prediction == "Arıza":
                        self.tree.insert('', 'end', values=values, tags=('failure',))
                    elif prediction == 0 or prediction == "Normal":
                        self.tree.insert('', 'end', values=values, tags=('normal',))
                    else:
                        self.tree.insert('', 'end', values=values)
                else:
                    self.tree.insert('', 'end', values=values)
            
            # Başlık güncelleme
            self.update_column_headers()
            
        except Exception as e:
            print(f"Sıralama hatası: {e}")
    
    def update_column_headers(self):
        """Sütun başlıklarını sıralama durumuna göre güncelle ve encoding düzelt."""
        try:
            columns = tuple(self.tree['columns'])
            for col in columns:
                label = col
                if col == self.sort_column:
                    arrow = '↓' if self.sort_reverse else '↑'
                    label = f"{col} {arrow}"
                self.tree.heading(col, text=self._fix_text(label))
        except Exception:
            pass
    
    def _clear_placeholder(self, event, placeholder):
        """Placeholder metnini temizle"""
        if event.widget.get() == placeholder:
            event.widget.delete(0, tk.END)
            event.widget.config(fg='black')
    
    def _restore_placeholder(self, event, placeholder):
        """Placeholder metnini geri yükle"""
        if not event.widget.get():
            event.widget.insert(0, placeholder)
            event.widget.config(fg='gray')
    
    def _set_quick_date(self, days):
        """Hızlı tarih aralığı ayarla"""
        from datetime import datetime, timezone, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        self.end_date_var.set(end_date.strftime('%Y-%m-%d'))
        self.start_date_var.set(start_date.strftime('%Y-%m-%d'))
        # Hızlı seçimden sonra filtreleri hemen uygula
        try:
            self.apply_filters()
        except Exception:
            pass
    
    def show_statistics(self):
        """İstatistikleri göster"""
        try:
            # Zaten açıksa sadece odağı ver ve geri dön
            try:
                if self.stats_window is not None and int(self.stats_window.winfo_exists()) == 1:
                    self.stats_window.deiconify()
                    self.stats_window.lift()
                    self.stats_window.focus_force()
                    return
            except Exception:
                pass

            stats = self.db_manager.get_statistics()
            
            self.stats_window = tk.Toplevel(self.root)
            self.stats_window.title("Database İstatistikleri")
            try:
                # Başlığı normalize et
                self.stats_window.title(self._fix_text(self.stats_window.title()))
            except Exception:
                pass
            self.stats_window.geometry("800x520")
            self.stats_window.configure(bg='#f0f0f0')

            def _on_close_stats():
                try:
                    if self.stats_window is not None:
                        self.stats_window.destroy()
                finally:
                    self.stats_window = None
            self.stats_window.protocol('WM_DELETE_WINDOW', _on_close_stats)
            
            # İstatistik metni
            top_frame = tk.Frame(self.stats_window, bg='#f0f0f0')
            top_frame.pack(fill='x', padx=10, pady=10)
            stats_text = tk.Text(top_frame, height=10, font=('Consolas', 10), 
                               bg='white', wrap='word')
            stats_text.pack(fill='x', expand=False)
            
            # İstatistikleri formatla
            content = f"""PdM Database İstatistikleri
{'='*40}

📊 Toplam Kayıt: {stats.get('total_records', 0)}

📊 Tahmin Dağılımı:
"""
            pred_dist = stats.get('prediction_distribution', {})
            for pred, count in pred_dist.items():
                pred_name = 'Normal' if pred == '0' else 'Arıza' if pred == '1' else f'Diğer ({pred})'
                content += f"   {pred_name}: {count}\n"
            
            content += f"\n📊 Makine Tipi Dağılımı:\n"
            machine_dist = stats.get('machine_type_distribution', {})
            for machine_type, count in machine_dist.items():
                content += f"   {machine_type}: {count}\n"
            
            content += f"\n📊 Son Kayıt: {stats.get('last_record_time', 'Belirtilmemiş')}"
            
            stats_text.insert('1.0', self._fix_text(content))
            # İçeriği düzgün Türkçe ile yeniden yaz (normalize)
            try:
                stats_text.config(state='normal')
                stats_text.delete('1.0', 'end')
                stats_text.insert('1.0', self._build_stats_content(stats))
            except Exception:
                pass
            stats_text.config(state='disabled')
            
            # Grafikler (matplotlib mevcutsa)
            if HAS_MPL:
                charts_frame = tk.Frame(self.stats_window, bg='#f0f0f0')
                charts_frame.pack(fill='both', expand=True, padx=10, pady=(0,10))

                # 1) Tahmin Dağılımı
                try:
                    fig1, ax1 = plt.subplots(figsize=(3.8, 2.6), dpi=100)
                    pred_dist = stats.get('prediction_distribution', {}) or {}
                    labels = []
                    values = []
                    for k, v in pred_dist.items():
                        label = 'Normal' if str(k) in ('0', 'Normal') else 'Arıza' if str(k) in ('1', 'Arıza') else str(k)
                        labels.append(label)
                        values.append(v)
                    if not labels:
                        labels, values = ['Veri yok'], [0]
                    ax1.bar(labels, values, color=['#2ecc71', '#e74c3c'][:len(labels)])
                    ax1.set_title('Tahmin Dağılımı')
                    ax1.set_ylabel('Adet')
                    ax1.grid(axis='y', alpha=0.2)
                    canvas1 = FigureCanvasTkAgg(fig1, master=charts_frame)
                    canvas1.draw()
                    canvas1.get_tk_widget().pack(side='left', fill='both', expand=True, padx=5)
                except Exception:
                    pass

                # 2) Makine Tipi Dağılımı
                try:
                    fig2, ax2 = plt.subplots(figsize=(3.8, 2.6), dpi=100)
                    machine_dist = stats.get('machine_type_distribution', {}) or {}
                    m_labels = list(machine_dist.keys()) or ['Veri yok']
                    m_values = list(machine_dist.values()) or [0]
                    ax2.bar(m_labels, m_values, color='#3498db')
                    ax2.set_title('Makine Tipleri')
                    ax2.set_ylabel('Adet')
                    ax2.grid(axis='y', alpha=0.2)
                    canvas2 = FigureCanvasTkAgg(fig2, master=charts_frame)
                    canvas2.draw()
                    canvas2.get_tk_widget().pack(side='left', fill='both', expand=True, padx=5)
                except Exception:
                    pass
            else:
                info = tk.Label(self.stats_window, text='Matplotlib bulunamadı. Grafikler için:\n pip install matplotlib', bg='#f0f0f0', fg='#7f8c8d')
                info.pack(pady=10)

        except Exception as e:
            messagebox.showerror("Hata", f"İstatistik hatası: {e}")
    
    def search_failures(self):
        """Arızaları ara"""
        try:
            # Zaten açıksa öne getir
            try:
                if self.search_window is not None and int(self.search_window.winfo_exists()) == 1:
                    self.search_window.deiconify()
                    self.search_window.lift()
                    self.search_window.focus_force()
                    return
            except Exception:
                pass

            failure_records = self.db_manager.search_by_prediction(1, limit=100)
            
            self.search_window = tk.Toplevel(self.root)
            self.search_window.title("📊 Arıza Kayıtları")
            self.search_window.geometry("800x600")

            def _on_close_search():
                try:
                    if self.search_window is not None:
                        self.search_window.destroy()
                finally:
                    self.search_window = None
            self.search_window.protocol('WM_DELETE_WINDOW', _on_close_search)
            
            # Sonuç tablosu
            columns = ('ID', 'Zaman', 'Tip', 'Olasılık', 'Neden')
            tree = ttk.Treeview(self.search_window, columns=columns, show='headings')
            
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)
            
            for record in failure_records:
                created_at = record.get('created_at', '')
                time_str = created_at[:16] if created_at else 'N/A'
                
                prob = record.get('prediction_probability')
                prob_text = 'N/A'
                
                # Kapsamlı tip kontrolü
                if prob is not None:
                    try:
                        if isinstance(prob, (int, float)):
                            prob_text = f"{prob:.2%}"
                        elif isinstance(prob, str):
                            prob_text = f"{float(prob):.2%}"
                        elif isinstance(prob, bytes):
                            import struct
                            if len(prob) == 8:  # double
                                prob_float = struct.unpack('d', prob)[0]
                                prob_text = f"{prob_float:.2%}"
                            elif len(prob) == 4:  # float
                                prob_float = struct.unpack('f', prob)[0]
                                prob_text = f"{prob_float:.2%}"
                    except (ValueError, struct.error):
                        prob_text = f"Raw: {str(prob)[:10]}"
                
                values = (
                    record.get('id', ''),
                    time_str,
                    record.get('machine_type', ''),
                    prob_text,
                    record.get('prediction_reason', '')[:30]
                )
                tree.insert('', 'end', values=values)
            
            tree.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Bilgi etiketi
            info_label = tk.Label(self.search_window, 
                                text=f"📊 {len(failure_records)} arıza kaydı bulundu",
                                font=('Arial', 10, 'bold'))
            info_label.pack(pady=5)
            
        except Exception as e:
            messagebox.showerror("Hata", f"Arama hatası: {e}")

    def open_search(self):
        """Genel arama giriş noktası (şimdilik arıza aramasını açar)."""
        try:
            return self.search_failures()
        except Exception as e:
            try:
                messagebox.showerror("Hata", f"Arama penceresi açılamadı: {e}")
            except Exception:
                pass

    # Gelişmiş arama ve local DB desteği kaldırıldı (sade: PdM DB)
    
    def export_data(self):
        """Filtrelenmiş verileri CSV dosyasına export et"""
        try:
            # Aktif filtreleri al
            filters = self._get_active_filters()
            
            # Verileri getir (limit olmadan tüm filtrelenmiş veriler)
            records = self.db_manager.get_sensor_data(
                limit=10000,
                prediction_filter=filters['prediction_filter_db'],
                machine_type_filter=filters['machine_type_filter_db'],
                blockchain_filter=filters['blockchain_filter_db'],
                start_date=filters['start_date_db'],
                end_date=filters['end_date_db']
            )
            # Export'ta da filtre sırası: ilk kayıttan itibaren
            records = list(reversed(records))
            
            if not records:
                messagebox.showwarning("Uyarı", "Export edilecek veri bulunamadı!")
                return
            
            # Dosya kaydetme dialogu
            filename = filedialog.asksaveasfilename(
                title="CSV Dosyasını Kaydet",
                defaultextension=".csv",
                filetypes=[("CSV dosyaları", "*.csv"), ("Tüm dosyalar", "*.*")],
                initialfile=f"pdm_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            
            if not filename:
                return  # Kullanıcı iptal etti
            
            # CSV dosyasını yaz
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                # CSV başlıkları
                fieldnames = [
                    'ID', 'Machine ID', 'Zaman', 'Timestamp', 'Off-Chain Veri Kanıtı',
                    'Hava Sıcaklığı (K)', 'İşlem Sıcaklığı (K)', 'Dönüş Hızı (rpm)', 
                    'Tork (Nm)', 'Aşınma (min)', 'Makine Tipi',
                    'Tahmin', 'Olasılık', 'Neden', 'Analiz Süresi (s)',
                    'Blockchain Başarılı', 'Blockchain TX Hash'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # Verileri yaz
                for record in records:
                    # Veriyi formatla
                    formatted = self._get_formatted_record_values(record)
                    
                    # CSV için temiz veri hazırla
                    csv_row = {
                        'ID': record.get('id', ''),
                        'Machine ID': record.get('machine_id', ''),
                        'Zaman': formatted['time_str'],
                        'Timestamp': record.get('timestamp', ''),
                        'Off-Chain Veri Kanıtı': record.get('offchain_data_hash', ''),
                        'Hava Sıcaklığı (K)': record.get('air_temp', 0),
                        'İşlem Sıcaklığı (K)': record.get('process_temp', 0),
                        'Dönüş Hızı (rpm)': record.get('rotation_speed', 0),
                        'Tork (Nm)': record.get('torque', 0),
                        'Aşınma (min)': record.get('tool_wear', 0),
                        'Makine Tipi': record.get('machine_type', ''),
                        'Tahmin': formatted['pred_text'],
                        'Olasılık': formatted['prob_text'],
                        'Neden': record.get('prediction_reason', ''),
                        'Analiz Süresi (s)': record.get('analysis_time', 0),
                        'Blockchain Başarılı': 'Evet' if record.get('blockchain_success', False) else 'Hayır',
                        'Blockchain TX Hash': record.get('blockchain_tx_hash', '') or 'Henüz gönderilmedi'
                    }
                    
                    writer.writerow(csv_row)
            
            # Başarı mesajı
            filter_info = filters['filter_info']
            
            filter_text = f" ({', '.join(filter_info)})" if filter_info else " (Tüm veriler)"
            
            messagebox.showinfo(
                "Export Başarılı", 
                f"✅ {len(records)} kayıt başarıyla export edildi!\n\n"
                f"📊 Dosya: {filename}\n"
                f"📊 Filtreler: {filter_text}"
            )
            
            self.status_label.config(text=f"✅ {len(records)} kayıt export edildi")
            
        except Exception as e:
            messagebox.showerror("Export Hatası", f"CSV export hatası: {e}")
            self.status_label.config(text="📊 Export hatası")
    
    def _get_formatted_record_values(self, record: dict) -> dict:
        """Veritabanı kaydını, GUI'de gösterilecek formatlanmış string'lere çevirir."""
        
        # Zaman formatı
        time_str = 'N/A'
        try:
            ts_val = record.get('timestamp')
            if ts_val is not None:
                dt_local = datetime.fromtimestamp(int(ts_val))
                time_str = dt_local.strftime('%d.%m.%Y %H:%M:%S')
            else:
                created_at = record.get('created_at', '')
                if created_at:
                    dt_utc = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                    dt_local = dt_utc.astimezone()
                    time_str = dt_local.strftime('%d.%m.%Y %H:%M:%S')
        except Exception:
            created_at = record.get('created_at', '')
            time_str = created_at or 'N/A'
        # Tahmin metni
        prediction = record.get('prediction')
        pred_text = 'Arıza' if prediction == 1 else 'Normal' if prediction == 0 else 'N/A'

        # Olasılık formatı - daha kapsamlı kontrol
        prob = record.get('prediction_probability')
        prob_text = 'N/A'
        
        if prob is not None:
            try:
                if isinstance(prob, (int, float)):
                    prob_text = f"{prob:.2%}"
                elif isinstance(prob, str):
                    prob_text = f"{float(prob):.2%}"
                elif isinstance(prob, bytes):
                    # Binary data'yı float olarak yorumla
                    import struct
                    if len(prob) == 8:  # double (8 bytes)
                        prob_float = struct.unpack('d', prob)[0]
                        prob_text = f"{prob_float:.2%}"
                    elif len(prob) == 4:  # float (4 bytes)
                        prob_float = struct.unpack('f', prob)[0]
                        prob_text = f"{prob_float:.2%}"
                    else:
                        prob_text = f"Binary({len(prob)} bytes)"
            except (ValueError, struct.error):
                prob_text = f"Raw: {prob}"

        # Neden (kÄ±salt)
        reason = record.get('prediction_reason', '') or ''
        reason_short = (reason[:20] + '...') if len(reason) > 20 else reason
        
        # Analiz sÃ¼resi formatı
        analysis_time = record.get('analysis_time')
        analysis_text = f"{analysis_time:.4f}s" if isinstance(analysis_time, (int, float)) else 'N/A'

        # Blockchain durumu
        bc_success = record.get('blockchain_success', False)
        bc_text = '✅' if bc_success else '❌'

        # Off-chain veri kanıtı (data_hash) formatı
        data_hash = record.get('offchain_data_hash', '') or ''
        if data_hash and len(data_hash) > 20:
            data_hash_short = f"{data_hash[:10]}...{data_hash[-10:]}"
        else:
            data_hash_short = data_hash or 'N/A'

        return {
            'id': record.get('id', ''),
            'time_str': time_str,
            'air_temp': f"{record.get('air_temp', 0):.1f}K",
            'process_temp': f"{record.get('process_temp', 0):.1f}K",
            'rotation_speed': f"{record.get('rotation_speed', 0)} rpm",
            'torque': f"{record.get('torque', 0):.1f} Nm",
            'tool_wear': f"{record.get('tool_wear', 0)} min",
            'machine_type': record.get('machine_type', ''),
            'pred_text': pred_text,
            'prob_text': prob_text,
            'reason_short': reason_short,
            'analysis_text': analysis_text,
            'bc_text': bc_text,
            'data_hash_short': data_hash_short,
            'prediction': prediction 
        }

    def _build_stats_content(self, stats: Dict) -> str:
        try:
            total = stats.get('total_records', 0)
            pred_dist = stats.get('prediction_distribution', {}) or {}
            machine_dist = stats.get('machine_type_distribution', {}) or {}
            last_time = stats.get('last_record_time', 'Belirtilmemiş')
            content = (
                "PdM Database İstatistikleri\n"
                + "="*40 + "\n\n"
                + f"• Toplam Kayıt: {total}\n\n"
                + "• Tahmin Dağılımı:\n"
            )
            for k, v in pred_dist.items():
                label = 'Normal' if str(k) in ('0', 'Normal') else 'Arıza' if str(k) in ('1', 'Arıza') else str(k)
                content += f"   {label}: {v}\n"
            content += "\n• Makine Tipleri:\n"
            for m, c in machine_dist.items():
                content += f"   {m}: {c}\n"
            content += f"\n• Son Kayıt: {last_time}"
            return content
        except Exception:
            return "İstatistikler hazırlanırken bir sorun oluştu."

    def _build_detail_content(self, record: Dict, formatted: Dict) -> str:
        try:
            reason_text = record.get('prediction_reason') or 'Belirtilmemiş'
            if str(reason_text).strip() in ['None', 'none', 'N/A', 'NA', '']:
                reason_text = 'Belirtilmemiş'
            bc_ok = bool(record.get('blockchain_success') or formatted.get('bc_success'))
            content = f"""Sensör Verisi Detayı
{'='*40}

• ID: {record.get('id')}
• Machine ID: {record.get('machine_id')}
• Zaman: {formatted['time_str']}
• Timestamp: {record.get('timestamp')}

• Sensör Verileri:
   Hava Sıcaklığı: {formatted['air_temp']}
   İşlem Sıcaklığı: {formatted['process_temp']}
   Dönüş Hızı: {formatted['rotation_speed']}
   Tork: {formatted['torque']}
   Aşınma: {formatted['tool_wear']}
   Makine Tipi: {formatted['machine_type']}

• Tahmin Sonuçları:
   Tahmin: {'Arıza' if formatted['prediction'] == 1 else 'Normal' if formatted['prediction'] == 0 else 'Belirtilmemiş'}
   Olasılık: {formatted['prob_text']}
   Neden: {reason_text}
   Analiz Süresi: {formatted['analysis_text']}

• Blockchain:
   Off-Chain Veri Kanıtı: {record.get('offchain_data_hash') or 'Belirtilmemiş'}
   Başarılı: {'Evet' if bc_ok else 'Hayır'}
   TX Hash: {self._format_tx_hash(record.get('blockchain_tx_hash'))}
"""
            return content
        except Exception:
            return "Detay hazırlanırken bir sorun oluştu."

    def on_item_double_click(self, event):
        """Kayıt detaylarını tekil pencerede göster"""
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0])
        record_id = item['values'][0]

        try:
            result = self.db_manager.get_sensor_data(record_id=record_id)
            if not result:
                messagebox.showwarning("Bulunamadı", f"ID'si {record_id} olan kayıt veritabanında bulunamadı.")
                return

            record = {}
            if isinstance(result, list) and len(result) > 0:
                record = result[0]
            elif isinstance(result, dict):
                record = result
            else:
                messagebox.showerror("Hata", "Veritabanından beklenmedik formatta veri döndü.")
                return

            formatted = self._get_formatted_record_values(record)

            # Detay penceresi tekil: mevcutsa içeriği yenile, yoksa oluştur
            if self.detail_window is None or int(self.detail_window.winfo_exists()) != 1:
                self.detail_window = tk.Toplevel(self.root)
                self.detail_window.geometry("500x600")
                self.detail_window.configure(bg='#f0f0f0')
                def _on_close_detail():
                    try:
                        if self.detail_window is not None:
                            self.detail_window.destroy()
                    finally:
                        self.detail_window = None
                self.detail_window.protocol('WM_DELETE_WINDOW', _on_close_detail)
            else:
                # Mevcut pencereyi temizle
                for w in self.detail_window.winfo_children():
                    w.destroy()

            self.detail_window.title(f"📋 Kayıt Detayı - ID: {record_id}")

            detail_text = tk.Text(self.detail_window, font=('Consolas', 9), bg='white', wrap='word')
            detail_text.pack(fill='both', expand=True, padx=10, pady=10)
            try:
                # Başlığı normalize et
                self.detail_window.title(self._fix_text(self.detail_window.title()))
            except Exception:
                pass

            reason_text = record.get('prediction_reason') or 'Belirtilmemiş'
            if str(reason_text).strip() in ['None', 'none', 'N/A', 'NA', '']:
                reason_text = 'Belirtilmemiş'

            content = f"""📋 Sensör Verisi Detayı
{'='*40}

📊 ID: {record.get('id')}
🤖 Machine ID: {record.get('machine_id')}
📊 Zaman: {formatted['time_str']}
📊 Timestamp: {record.get('timestamp')}

🌡️ Sensör Verileri:
   Hava Sıcaklığı: {formatted['air_temp']}
   İşlem Sıcaklığı: {formatted['process_temp']}
   Dönüş Hızı: {formatted['rotation_speed']}
   Tork: {formatted['torque']}
   Aşınma: {formatted['tool_wear']}
   Makine Tipi: {formatted['machine_type']}

📊 Tahmin Sonuçları:
   Tahmin: {'Arıza' if formatted['prediction'] == 1 else 'Normal' if formatted['prediction'] == 0 else 'Belirtilmemiş'}
   Olasılık: {formatted['prob_text']}
   Neden: {reason_text}
   Analiz Süresi: {formatted['analysis_text']}

🔗 Blockchain:
   Off-Chain Veri Kanıtı: {record.get('offchain_data_hash') or 'Belirtilmemiş'}
   Başarılı: {'Evet' if formatted['bc_text'] == '✅' else 'Hayır'}
   TX Hash: {self._format_tx_hash(record.get('blockchain_tx_hash'))}
"""
            detail_text.insert('1.0', content)
            # İçeriği düzgün Türkçe ile yeniden yaz (normalize)
            try:
                detail_text.config(state='normal')
                detail_text.delete('1.0', 'end')
                detail_text.insert('1.0', self._build_detail_content(record, formatted))
            except Exception:
                pass
            detail_text.config(state='disabled')

            full_tx_hash = record.get('blockchain_tx_hash')
            if full_tx_hash and isinstance(full_tx_hash, (str, bytes)):
                btn_frame = tk.Frame(self.detail_window, bg='#f0f0f0')
                btn_frame.pack(fill='x', padx=10, pady=(0,10))
                open_btn = tk.Button(btn_frame, text="🔗 Explorer'da Aç",
                                     command=lambda h=full_tx_hash: self._open_explorer_full(h),
                                     bg='#3498db', fg='white')
                open_btn.pack(anchor='w')
                try:
                    open_btn.config(text=self._fix_text(open_btn.cget('text')))
                except Exception:
                    pass

            # Odağı mevcut pencereye getir
            try:
                self._normalize_widget_texts(self.detail_window)
            except Exception:
                pass
            self.detail_window.deiconify()
            self.detail_window.lift()
            self.detail_window.focus_force()

        except Exception as e:
            messagebox.showerror("Hata", f"Detay hatası: {e}")
    
    def _format_tx_hash(self, tx_hash):
        """TX Hash'i formatla"""
        if not tx_hash or tx_hash in ['', 'None', None]:
            return 'Henüz blockchain\'e gönderilmedi'
        
        # Eğer bytes ise decode et
        if isinstance(tx_hash, bytes):
            try:
                tx_hash = tx_hash.decode('utf-8')
            except UnicodeDecodeError:
                return f'Binary data ({len(tx_hash)} bytes)'
        
        # Hash formatını kontrol et
        tx_hash_str = str(tx_hash).strip()
        # Normalize et: 0x yoksa ekle, gereksiz karakterleri temizle
        import re
        # İçinden 64 haneli hex yakala
        m = re.search(r'(0x)?([0-9a-fA-F]{64})', tx_hash_str)
        if m:
            tx_hash_str = '0x' + m.group(2).lower()
        # Tam hash/adresi göster (kısaltma yok)
        if tx_hash_str.startswith('0x') and (len(tx_hash_str) in (66, 42)):
            return tx_hash_str
        if len(tx_hash_str) in (64, 40):
            return '0x' + tx_hash_str
        return tx_hash_str

    # ----- Sağ tık işlemleri -----
    def _on_tree_right_click(self, event):
        try:
            row_id = self.tree.identify_row(event.y)
            if row_id:
                self.tree.selection_set(row_id)
            self.tree_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.tree_menu.grab_release()

    def _get_selected_record_id(self) -> int:
        selection = self.tree.selection()
        if not selection:
            return None
        item = self.tree.item(selection[0])
        return item['values'][0] if item['values'] else None

    def _ctx_show_detail(self):
        # Double-click davranışını tetikle
        self.on_item_double_click(None)

    def _ctx_export_selected(self):
        rec_id = self._get_selected_record_id()
        if not rec_id:
            return
        try:
            record = self.db_manager.get_sensor_data(record_id=rec_id)
            if not record:
                return
            # Tek kaydı CSV'ye kaydet
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                title="CSV Kaydet",
                defaultextension=".csv",
                filetypes=[("CSV dosyaları", "*.csv")],
                initialfile=f"record_{rec_id}.csv"
            )
            if not filename:
                return
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=list(record[0].keys()))
                writer.writeheader()
                writer.writerow(record[0])
            self.status_label.config(text=f"✅ Kayıt CSV'ye aktarıldı (ID: {rec_id})")
        except Exception as e:
            messagebox.showerror("Hata", f"CSV export hatası: {e}")

    def _ctx_copy_tx_hash(self):
        rec_id = self._get_selected_record_id()
        if not rec_id:
            return
        recs = self.db_manager.get_sensor_data(record_id=rec_id)
        if not recs:
            return
        tx = recs[0].get('blockchain_tx_hash')
        if isinstance(tx, bytes):
            try:
                tx = tx.decode('utf-8')
            except Exception:
                tx = None
        if tx:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(tx))
            self.status_label.config(text="✅ TX hash panoya kopyalandı")
        else:
            self.status_label.config(text="⚠️ Bu kayıtta TX hash yok")

    def _normalize_hex(self, value: str) -> str:
        """Serbest formatlı girişten 0x+64 hex (tx) ya da 0x+40 hex (adres) çıkarır."""
        import re
        s = value.strip()
        # Önce 64 haneli (tx) ara
        m = re.search(r'(0x)?([0-9a-fA-F]{64})', s)
        if m:
            return '0x' + m.group(2).lower()
        # Sonra 40 haneli (adres) ara
        m = re.search(r'(0x)?([0-9a-fA-F]{40})', s)
        if m:
            return '0x' + m.group(2).lower()
        return ''

    def _open_explorer_full(self, tx_or_addr):
        try:
            s = tx_or_addr.decode('utf-8') if isinstance(tx_or_addr, bytes) else str(tx_or_addr)
            s = self._normalize_hex(s)
            if len(s) == 66 and s.startswith('0x'):
                url = f"https://sepolia.explorer.zksync.io/tx/{s}"
            elif len(s) == 42 and s.startswith('0x'):
                url = f"https://sepolia.explorer.zksync.io/address/{s}"
            else:
                messagebox.showwarning("Uyarı", "Geçerli bir TX hash/adres bulunamadı")
                return
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Hata", f"Explorer açılırken hata: {e}")

    def _ctx_open_explorer(self):
        rec_id = self._get_selected_record_id()
        if not rec_id:
            return
        recs = self.db_manager.get_sensor_data(record_id=rec_id)
        if not recs:
            return
        tx = recs[0].get('blockchain_tx_hash')
        if tx:
            self._open_explorer_full(tx)
        else:
            messagebox.showinfo("Bilgi", "Bu kayıtta TX hash bulunmuyor")

def _dv_create_widgets(self):
    """DatabaseViewer icin GUI bilesenlerini olustur (module-level)."""
    # Baslik
    title_frame = tk.Frame(self.root, bg='#2c3e50', height=60)
    title_frame.pack(fill='x', pady=(0, 10))
    title_frame.pack_propagate(False)
    tk.Label(title_frame, text="PdM Database Viewer", font=('Arial', 18, 'bold'), bg='#2c3e50', fg='white').pack(expand=True)

    # Ust kontrol butonlari
    control_frame = tk.Frame(self.root, bg='#f0f0f0')
    control_frame.pack(fill='x', padx=10, pady=5)
    tk.Button(control_frame, text="Yenile", command=self.refresh_data, font=('Arial', 10, 'bold'), bg='#3498db', fg='white', width=12).pack(side='left', padx=5)
    tk.Button(control_frame, text="İstatistikler", command=self.show_statistics, font=('Arial', 10, 'bold'), bg='#27ae60', fg='white', width=12).pack(side='left', padx=5)
    tk.Button(control_frame, text="Arıza Ara", command=self.search_failures, font=('Arial', 10, 'bold'), bg='#e74c3c', fg='white', width=12).pack(side='left', padx=5)
    tk.Button(control_frame, text="Export", command=self.export_data, font=('Arial', 10, 'bold'), bg='#9b59b6', fg='white', width=12).pack(side='left', padx=5)

    # Filtre bolumu
    filter_frame = tk.LabelFrame(self.root, text="Filtreler", font=('Arial', 10, 'bold'), bg='#f0f0f0', padx=10, pady=5)
    filter_frame.pack(fill='x', padx=10, pady=5)

    # Limit
    tk.Label(filter_frame, text="Kayıt:", bg='#f0f0f0').pack(side='left')
    self.limit_var = tk.IntVar(value=50)
    limit_spin = tk.Spinbox(filter_frame, from_=10, to=1000, textvariable=self.limit_var, width=8)
    limit_spin.pack(side='left', padx=5)
    limit_spin.bind('<Return>', lambda e: self.apply_filters())
    limit_spin.bind('<KP_Enter>', lambda e: self.apply_filters())

    # Tahmin filtresi
    tk.Label(filter_frame, text="Tahmin:", bg='#f0f0f0').pack(side='left', padx=(15,5))
    self.prediction_var = tk.StringVar(value="Tümü")
    prediction_combo = ttk.Combobox(filter_frame, textvariable=self.prediction_var, values=["Tümü", "Normal (0)", "Arıza (1)"], width=12)
    prediction_combo.pack(side='left', padx=5)
    prediction_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())
    prediction_combo.bind('<Return>', lambda e: self.apply_filters())
    prediction_combo.bind('<KP_Enter>', lambda e: self.apply_filters())

    # Makine tipi filtresi
    tk.Label(filter_frame, text="Makine:", bg='#f0f0f0').pack(side='left', padx=(15,5))
    self.machine_type_var = tk.StringVar(value="Tümü")
    machine_combo = ttk.Combobox(filter_frame, textvariable=self.machine_type_var, values=["Tümü", "L", "M", "H"], width=6)
    machine_combo.pack(side='left', padx=5)
    machine_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())
    machine_combo.bind('<Return>', lambda e: self.apply_filters())
    machine_combo.bind('<KP_Enter>', lambda e: self.apply_filters())

    # Blockchain filtresi
    tk.Label(filter_frame, text="Blockchain:", bg='#f0f0f0').pack(side='left', padx=(15,5))
    self.blockchain_var = tk.StringVar(value="Tümü")
    bc_combo = ttk.Combobox(filter_frame, textvariable=self.blockchain_var, values=["Tümü", "Başarılı", "Başarısız"], width=10)
    bc_combo.pack(side='left', padx=5)
    bc_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())
    bc_combo.bind('<Return>', lambda e: self.apply_filters())
    bc_combo.bind('<KP_Enter>', lambda e: self.apply_filters())

    # Filtre uygula/temizle
    tk.Button(filter_frame, text="Filtrele", command=self.apply_filters, font=('Arial', 8, 'bold'), bg='#f39c12', fg='white', width=8).pack(side='left', padx=8)
    tk.Button(filter_frame, text="Temizle", command=self.clear_filters, font=('Arial', 8, 'bold'), bg='#95a5a6', fg='white', width=8).pack(side='left', padx=5)

    # Tarih araligi
    date_frame = tk.Frame(filter_frame, bg='#f0f0f0')
    date_frame.pack(fill='x', pady=(10, 0))
    tk.Label(date_frame, text="Başlangıç:", bg='#f0f0f0').pack(side='left')
    self.start_date_var = tk.StringVar()
    self.end_date_var = tk.StringVar()
    self.start_date_widget = tk.Entry(date_frame, textvariable=self.start_date_var, width=12)
    self.start_date_widget.pack(side='left', padx=5)
    self.start_date_widget.insert(0, "YYYY-MM-DD")
    self.start_date_widget.bind('<FocusIn>', lambda e: self._clear_placeholder(e, "YYYY-MM-DD"))
    self.start_date_widget.bind('<FocusOut>', lambda e: self._restore_placeholder(e, "YYYY-MM-DD"))
    self.start_date_widget.bind('<Return>', lambda e: self.apply_filters())
    self.start_date_widget.bind('<KP_Enter>', lambda e: self.apply_filters())
    tk.Label(date_frame, text="Bitiş:", bg='#f0f0f0').pack(side='left', padx=(15,5))
    self.end_date_widget = tk.Entry(date_frame, textvariable=self.end_date_var, width=12)
    self.end_date_widget.pack(side='left', padx=5)
    self.end_date_widget.insert(0, "YYYY-MM-DD")
    self.end_date_widget.bind('<FocusIn>', lambda e: self._clear_placeholder(e, "YYYY-MM-DD"))
    self.end_date_widget.bind('<FocusOut>', lambda e: self._restore_placeholder(e, "YYYY-MM-DD"))
    self.end_date_widget.bind('<Return>', lambda e: self.apply_filters())
    self.end_date_widget.bind('<KP_Enter>', lambda e: self.apply_filters())

    # Ana tablo
    table_frame = tk.Frame(self.root)
    table_frame.pack(fill='both', expand=True, padx=10, pady=5)
    columns = ('ID', 'Zaman', 'Veri Kanıtı', 'Hava Sıc.', 'İşlem Sıc.', 'Dönüş Hızı', 'Tork', 'Aşınma', 'Tip', 'Tahmin', 'Olasılık', 'Neden', 'Analiz S.', 'Blockchain')
    self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
    widths = [50, 120, 180, 80, 80, 90, 70, 70, 50, 70, 80, 150, 80, 100]
    for col, w in zip(columns, widths):
        self.tree.heading(col, text=col, command=lambda c=col: self.sort_by_column(c))
        self.tree.column(col, width=w, anchor='center')
    vscroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
    self.tree.configure(yscrollcommand=vscroll.set)
    self.tree.pack(side='left', fill='both', expand=True)
    vscroll.pack(side='right', fill='y')
    self.tree.tag_configure('failure', background='#ffcdd2')
    self.tree.tag_configure('normal', background='#e8f5e8')
    self.tree.bind('<Double-1>', self.on_item_double_click)
    self.tree.bind('<Button-3>', self._on_tree_right_click)

    # Sağ tık menüsü
    self.tree_menu = tk.Menu(self.root, tearoff=0)
    try:
        self.tree_menu.add_command(label="Detay Göster", command=self._ctx_show_detail)
        self.tree_menu.add_command(label="CSV'ye Aktar (Seçili)", command=self._ctx_export_selected)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="TX Hash'i Kopyala", command=self._ctx_copy_tx_hash)
        self.tree_menu.add_command(label="Explorer'da Aç", command=self._ctx_open_explorer)
    except Exception:
        # Encoding sorununda basit menü yine oluşsun
        self.tree_menu.add_command(label="Detay", command=self._ctx_show_detail)

    # Durum çubuğu
    status_frame = tk.Frame(self.root, bg='#34495e', height=30)
    status_frame.pack(fill='x', side='bottom')
    status_frame.pack_propagate(False)
    self.status_label = tk.Label(status_frame, text="Hazır", bg='#34495e', fg='white', font=('Arial', 9))
    self.status_label.pack(side='left', padx=10, pady=5)
    self.loading_var = tk.BooleanVar(value=False)
    self.progressbar = ttk.Progressbar(status_frame, mode='indeterminate', length=150)
    self.progressbar.pack(side='right', padx=10)
    self.progressbar.stop()

    # UI metinlerini normalize et (mojibake azaltma)
    try:
        self._normalize_widget_texts()
    except Exception:
        pass

def main():
    """Database viewer uygulamasını başlat"""
    root = tk.Tk()
    app = DatabaseViewer(root)
    root.mainloop()

if __name__ == "__main__":
    main()


