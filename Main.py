import os
import sys
import json
import socket
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import winreg
from datetime import datetime
from pathlib import Path
from PIL import Image
import pystray

from Sender import Sender
from Receiver import Receiver

class ZapShareApp:
    def __init__(self, root=None):
        self.config_file = "zapshare_config.json"
        self.config = self.load_config()
        
        # Inizializza sender e receiver
        self.sender = Sender()
        self.receiver = None
        
        # Registro del trasferimento
        self.transfer_history = []
        
        # Finestra principale
        if root:
            self.root = root
        else:
            self.root = tk.Tk()
            self.root.title("ZapShare")
            self.root.geometry("800x600")
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
            
            # Icona dell'applicazione (se disponibile)
            try:
                self.root.iconbitmap("zapshare_icon.ico")
            except:
                pass
        
        self.setup_ui()
        
        # Se è la prima esecuzione, mostra la finestra di configurazione
        if not os.path.exists(self.config_file) or "first_run" not in self.config:
            self.show_first_time_setup()
        else:
            # Avvia il receiver in background
            self.start_receiver()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        else:
            # Configurazione di default
            default_config = {
                "receive_directory": str(Path.home() / "Downloads"),
                "start_with_windows": False,
                "computer_name": socket.gethostname(),
                "first_run": True
            }
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config

    def save_config(self):
        """Salva la configurazione su file"""
        self.config["first_run"] = False
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def setup_ui(self):
        # Menu principale
        self.create_menu()
        
        # Frame principale
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Notebook per tab
        self.tabs = ttk.Notebook(main_frame)
        self.tabs.pack(fill="both", expand=True)
        
        # Tab invio file
        self.send_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.send_tab, text="Invia File")
        
        # Tab dispositivi
        self.devices_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.devices_tab, text="Dispositivi")
        
        # Tab cronologia
        self.history_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.history_tab, text="Cronologia")
        
        # Tab impostazioni
        self.settings_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.settings_tab, text="Impostazioni")
        
        # Popola i tab
        self.setup_send_tab()
        self.setup_devices_tab()
        self.setup_history_tab()
        self.setup_settings_tab()
        
        # Barra di stato
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill="x", side="bottom", padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="Pronto")
        status_label = ttk.Label(self.status_bar, textvariable=self.status_var, anchor="w")
        status_label.pack(side="left")
        
        self.connection_status = ttk.Label(self.status_bar, text="Stato: Disconnesso", anchor="e")
        self.connection_status.pack(side="right")

    def create_menu(self):
        menubar = tk.Menu(self.root)
        
        # Menu File
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Invia file", command=self.show_send_tab)
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Menu Dispositivi
        device_menu = tk.Menu(menubar, tearoff=0)
        device_menu.add_command(label="Cerca dispositivi", command=self.discover_devices)
        device_menu.add_command(label="Visualizza dispositivi", command=self.show_devices_tab)
        menubar.add_cascade(label="Dispositivi", menu=device_menu)
        
        # Menu Visualizza
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Cronologia trasferimenti", command=self.show_history_tab)
        menubar.add_cascade(label="Visualizza", menu=view_menu)
        
        # Menu Strumenti
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Impostazioni", command=self.show_settings_tab)
        menubar.add_cascade(label="Strumenti", menu=tools_menu)
        
        # Menu Aiuto
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Guida", command=self.show_help)
        help_menu.add_separator()
        help_menu.add_command(label="Info su", command=self.show_about)
        menubar.add_cascade(label="Aiuto", menu=help_menu)
        
        self.root.config(menu=menubar)

    def setup_send_tab(self):
        # Frame contenitore per la parte superiore
        top_frame = ttk.Frame(self.send_tab)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        # Selezione file
        file_frame = ttk.LabelFrame(top_frame, text="File da inviare")
        file_frame.pack(fill="x", padx=5, pady=5)
        
        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, width=50)
        file_entry.pack(side="left", fill="x", expand=True, padx=5, pady=10)
        
        browse_btn = ttk.Button(file_frame, text="Sfoglia...", command=self.browse_file)
        browse_btn.pack(side="right", padx=5, pady=10)
        
        # Selezione dispositivo
        device_frame = ttk.LabelFrame(top_frame, text="Dispositivo di destinazione")
        device_frame.pack(fill="x", padx=5, pady=10)
        
        self.device_listbox = tk.Listbox(device_frame, height=8)
        self.device_listbox.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(device_frame, orient="vertical", command=self.device_listbox.yview)
        scrollbar.pack(side="right", fill="y", pady=5)
        self.device_listbox.config(yscrollcommand=scrollbar.set)
        
        # Bottoni
        button_frame = ttk.Frame(device_frame)
        button_frame.pack(side="bottom", fill="x", padx=5, pady=5)
        
        refresh_btn = ttk.Button(button_frame, text="Cerca dispositivi", command=self.discover_devices)
        refresh_btn.pack(side="left", padx=5, pady=5)
        
        # Progresso
        progress_frame = ttk.LabelFrame(self.send_tab, text="Progresso trasferimento")
        progress_frame.pack(fill="x", padx=15, pady=10)
        
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, length=300, mode="determinate")
        self.progress_bar.pack(fill="x", padx=5, pady=10)
        
        self.progress_label = ttk.Label(progress_frame, text="Pronto")
        self.progress_label.pack(anchor="center", pady=5)
        
        # Pulsante invio
        send_btn = ttk.Button(self.send_tab, text="Invia file", command=self.send_file)
        send_btn.pack(pady=20)
        
        # Popola la lista dei dispositivi
        self.update_device_list()

    def setup_devices_tab(self):
        # Frame superiore
        top_frame = ttk.Frame(self.devices_tab)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        scan_btn = ttk.Button(top_frame, text="Cerca dispositivi", command=self.discover_devices)
        scan_btn.pack(side="left", padx=5)
        
        self.device_status_var = tk.StringVar(value="Nessun dispositivo trovato")
        status_label = ttk.Label(top_frame, textvariable=self.device_status_var)
        status_label.pack(side="right", padx=5)
        
        # Tabella dispositivi
        columns = ("name", "ip", "status")
        self.device_tree = ttk.Treeview(self.devices_tab, columns=columns, show="headings")
        
        # Intestazioni
        self.device_tree.heading("name", text="Nome dispositivo")
        self.device_tree.heading("ip", text="Indirizzo IP")
        self.device_tree.heading("status", text="Stato")
        
        # Colonne
        self.device_tree.column("name", width=200)
        self.device_tree.column("ip", width=120)
        self.device_tree.column("status", width=80)
        
        self.device_tree.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.devices_tab, orient="vertical", command=self.device_tree.yview)
        scrollbar.place(relx=1, rely=0, relheight=1, anchor="ne")
        self.device_tree.configure(yscrollcommand=scrollbar.set)

    def setup_history_tab(self):
        # Tabella cronologia
        columns = ("time", "type", "filename", "size", "peer", "status")
        self.history_tree = ttk.Treeview(self.history_tab, columns=columns, show="headings")
        
        # Intestazioni
        self.history_tree.heading("time", text="Orario")
        self.history_tree.heading("type", text="Tipo")
        self.history_tree.heading("filename", text="Nome file")
        self.history_tree.heading("size", text="Dimensione")
        self.history_tree.heading("peer", text="Dispositivo")
        self.history_tree.heading("status", text="Stato")
        
        # Colonne
        self.history_tree.column("time", width=120)
        self.history_tree.column("type", width=80)
        self.history_tree.column("filename", width=200)
        self.history_tree.column("size", width=80)
        self.history_tree.column("peer", width=150)
        self.history_tree.column("status", width=80)
        
        self.history_tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.history_tab, orient="vertical", command=self.history_tree.yview)
        scrollbar.place(relx=1, rely=0, relheight=1, anchor="ne")
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pulsanti
        btn_frame = ttk.Frame(self.history_tab)
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        clear_btn = ttk.Button(btn_frame, text="Cancella cronologia", command=self.clear_history)
        clear_btn.pack(side="right", padx=5, pady=5)

    def setup_settings_tab(self):
        settings_frame = ttk.LabelFrame(self.settings_tab, text="Impostazioni applicazione")
        settings_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Nome computer
        name_frame = ttk.Frame(settings_frame)
        name_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(name_frame, text="Nome computer:").pack(side="left", padx=5)
        
        self.computer_name_var = tk.StringVar(value=self.config["computer_name"])
        ttk.Entry(name_frame, textvariable=self.computer_name_var, width=30).pack(side="left", padx=5, fill="x", expand=True)
        
        # Cartella ricezione
        dir_frame = ttk.Frame(settings_frame)
        dir_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(dir_frame, text="Cartella ricezione:").pack(side="left", padx=5)
        
        self.receive_dir_var = tk.StringVar(value=self.config["receive_directory"])
        ttk.Entry(dir_frame, textvariable=self.receive_dir_var, width=30).pack(side="left", padx=5, fill="x", expand=True)
        
        browse_dir_btn = ttk.Button(dir_frame, text="Sfoglia...", command=self.browse_directory)
        browse_dir_btn.pack(side="right", padx=5)
        
        # Avvio automatico
        startup_frame = ttk.Frame(settings_frame)
        startup_frame.pack(fill="x", padx=10, pady=5)
        
        self.startup_var = tk.BooleanVar(value=self.config["start_with_windows"])
        ttk.Checkbutton(startup_frame, text="Avvia all'avvio di Windows", variable=self.startup_var).pack(anchor="w", padx=5)
        
        # Bottoni
        btn_frame = ttk.Frame(settings_frame)
        btn_frame.pack(fill="x", padx=10, pady=15)
        
        save_btn = ttk.Button(btn_frame, text="Salva impostazioni", command=self.save_settings)
        save_btn.pack(side="right", padx=5)

    def show_first_time_setup(self):
        # Crea una finestra modale per la configurazione iniziale
        setup_window = tk.Toplevel(self.root)
        setup_window.title("Benvenuto in ZapShare")
        setup_window.geometry("500x350")
        setup_window.resizable(False, False)
        setup_window.transient(self.root)
        setup_window.grab_set()
        
        # Rendi la finestra modale
        setup_window.focus_set()
        
        # Titolo
        title_label = ttk.Label(setup_window, text="Benvenuto in ZapShare", font=("Arial", 14, "bold"))
        title_label.pack(pady=15)
        
        info_label = ttk.Label(setup_window, text="Configura le impostazioni di base per iniziare", wraplength=450)
        info_label.pack(pady=5)
        
        # Frame per le impostazioni
        settings_frame = ttk.Frame(setup_window)
        settings_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Nome computer
        ttk.Label(settings_frame, text="Nome del computer (visibile agli altri dispositivi):").pack(anchor="w", pady=(10, 5))
        
        computer_name_var = tk.StringVar(value=self.config["computer_name"])
        ttk.Entry(settings_frame, textvariable=computer_name_var, width=40).pack(fill="x", pady=5)
        
        # Cartella di ricezione
        ttk.Label(settings_frame, text="Cartella per la ricezione dei file:").pack(anchor="w", pady=(10, 5))
        
        receive_dir_frame = ttk.Frame(settings_frame)
        receive_dir_frame.pack(fill="x", pady=5)
        
        receive_dir_var = tk.StringVar(value=self.config["receive_directory"])
        ttk.Entry(receive_dir_frame, textvariable=receive_dir_var, width=40).pack(side="left", fill="x", expand=True)
        
        def select_directory():
            dir_path = filedialog.askdirectory(initialdir=receive_dir_var.get())
            if dir_path:
                receive_dir_var.set(dir_path)
        
        ttk.Button(receive_dir_frame, text="Sfoglia...", command=select_directory).pack(side="right", padx=5)
        
        # Avvio con Windows
        startup_var = tk.BooleanVar(value=self.config["start_with_windows"])
        ttk.Checkbutton(settings_frame, text="Avvia all'avvio di Windows", variable=startup_var).pack(anchor="w", pady=10)
        
        # Bottoni
        btn_frame = ttk.Frame(setup_window)
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        def save_settings():
            self.config["computer_name"] = computer_name_var.get()
            self.config["receive_directory"] = receive_dir_var.get()
            
            # Crea la directory di destinazione se non esiste
            if not os.path.exists(receive_dir_var.get()):
                try:
                    os.makedirs(receive_dir_var.get())
                except Exception as e:
                    messagebox.showerror("Errore", f"Impossibile creare la directory: {e}")
                    return
            
            # Imposta l'avvio automatico
            self.set_startup(startup_var.get())
            
            self.save_config()
            
            # Avvia il receiver
            self.start_receiver()
            
            # Chiude la finestra di configurazione
            setup_window.destroy()
        
        ttk.Button(btn_frame, text="Salva e inizia", command=save_settings, width=20).pack(side="right", padx=5)

    def set_startup(self, enable):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "ZapShare"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            
            if enable:
                # Aggiunge l'applicazione all'avvio di Windows
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, sys.executable)
                self.config["start_with_windows"] = True
            else:
                # Rimuove l'applicazione dall'avvio di Windows
                try:
                    winreg.DeleteValue(key, app_name)
                except:
                    pass
                self.config["start_with_windows"] = False
            
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Errore nell'impostazione dell'avvio automatico: {e}")
            return False

    def restart_receiver(self):
        """Ferma e riavvia il receiver con le nuove impostazioni"""
        if self.receiver and self.receiver.running:
            self.receiver.stop()
            self.receiver = None
        
        self.start_receiver()
        self.status_var.set("Servizio riavviato con le nuove impostazioni")

    def start_receiver(self):
        # Avvia il receiver in un thread separato
        if not self.receiver:
            self.receiver = Receiver()
            self.receiver.config = self.config.copy()
            
            # Aggiungi una callback per la ricezione dei file
            self.receiver.add_transfer_callback(self.on_file_received)
            
            receiver_thread = threading.Thread(target=self.receiver.start)
            receiver_thread.daemon = True
            receiver_thread.start()
            
            # Aggiorna stato
            self.connection_status.config(text=f"Stato: In ascolto su {self.receiver.ip}")

    def show_send_tab(self):
        self.tabs.select(self.send_tab)

    def show_devices_tab(self):
        self.tabs.select(self.devices_tab)

    def show_history_tab(self):
        self.tabs.select(self.history_tab)

    def show_settings_tab(self):
        self.tabs.select(self.settings_tab)

    def browse_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.file_path_var.set(file_path)

    def browse_directory(self):
        dir_path = filedialog.askdirectory(initialdir=self.receive_dir_var.get())
        if dir_path:
            self.receive_dir_var.set(dir_path)

    def discover_devices(self):
        self.status_var.set("Ricerca dispositivi in corso...")
        
        def update_device_found(device_info):
            # Aggiorna la UI con il dispositivo trovato
            self.update_device_list()
            self.update_device_tree()
            self.root.update_idletasks()
        
        # Avvia la ricerca in un thread separato
        def search_thread():
            discovered = self.sender.discover_devices(callback=update_device_found)
            
            # Aggiorna l'interfaccia alla fine
            self.root.after(0, lambda: self.update_device_list())
            self.root.after(0, lambda: self.update_device_tree())
            self.root.after(0, lambda: self.status_var.set(f"Trovati {len(discovered)} dispositivi"))
            self.root.after(0, lambda: self.device_status_var.set(f"Dispositivi disponibili: {len(self.sender.devices['devices'])}"))
        
        thread = threading.Thread(target=search_thread)
        thread.daemon = True
        thread.start()

    def update_device_list(self):
        self.device_listbox.delete(0, tk.END)
        for device in self.sender.devices["devices"]:
            self.device_listbox.insert(tk.END, f"{device['name']} ({device['ip']})")

    def update_device_tree(self):
        # Cancella la tabella
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        
        # Aggiunge i dispositivi
        for device in self.sender.devices["devices"]:
            self.device_tree.insert("", "end", values=(
                device["name"],
                device["ip"],
                "Online"  # Si potrebbe verificare lo stato reale
            ))

    def update_ui_from_config(self):
        """Aggiorna l'interfaccia utente in base alla configurazione attuale"""
        # Aggiorna le variabili di interfaccia
        self.computer_name_var.set(self.config["computer_name"])
        self.receive_dir_var.set(self.config["receive_directory"])
        self.startup_var.set(self.config["start_with_windows"])
        
        # Aggiorna la barra di stato
        if self.receiver and self.receiver.running:
            self.connection_status.config(text=f"Stato: In ascolto su {self.receiver.ip}")
        else:
            self.connection_status.config(text="Stato: Disconnesso")

    def send_file(self):
        file_path = self.file_path_var.get()
        if not file_path:
            messagebox.showwarning("Errore", "Seleziona un file da inviare")
            return
        
        selected = self.device_listbox.curselection()
        if not selected:
            messagebox.showwarning("Errore", "Seleziona un dispositivo di destinazione")
            return
        
        device_index = selected[0]
        device = self.sender.devices["devices"][device_index]
        
        # Prepara l'interfaccia per l'invio
        self.progress_var.set(0)
        self.progress_label.config(text=f"Invio a {device['name']}...")
        
        # Callback per l'aggiornamento del progresso
        def progress_callback(progress):
            self.progress_var.set(progress)
            self.progress_label.config(text=f"Invio in corso: {progress}%")
            self.root.update_idletasks()
        
        # Callback quando il trasferimento è completato
        def transfer_completed(info):
            self.add_to_history({
                "time": datetime.now().strftime("%H:%M:%S"),
                "type": "Invio",
                "filename": os.path.basename(file_path),
                "size": self.format_size(os.path.getsize(file_path)),
                "peer": device["name"],
                "status": "Completato" if info["status"] == "completed" else "Fallito"
            })
        
        # Aggiungi la callback al sender
        self.sender.add_transfer_callback(transfer_completed)
        
        # Avvia l'invio in un thread separato
        def send_thread():
            success = self.sender.send_file(file_path, device_index, progress_callback)
            
            # Aggiorna l'interfaccia al termine
            self.root.after(0, lambda: self.progress_label.config(
                text="Invio completato con successo" if success else "Errore durante l'invio"
            ))
            
            if success:
                self.status_var.set(f"File inviato con successo a {device['name']}")
            else:
                self.status_var.set("Errore durante l'invio del file")
        
        thread = threading.Thread(target=send_thread)
        thread.daemon = True
        thread.start()

    def on_file_received(self, transfer_info):
        """Callback chiamato quando un file viene ricevuto"""
        # Ottieni il nome del mittente (se disponibile)
        sender_name = transfer_info["sender_ip"]
        for device in self.sender.devices["devices"]:
            if device["ip"] == transfer_info["sender_ip"]:
                sender_name = device["name"]
                break
        
        # Mostra una notifica
        self.root.after(0, lambda: messagebox.showinfo("File ricevuto", 
                                                     f"Ricevuto file {transfer_info['filename']} da {sender_name}"))
        
        # Aggiorna lo stato
        self.root.after(0, lambda: self.status_var.set(f"File ricevuto: {transfer_info['filename']}"))
        
        # Aggiungi alla cronologia
        self.add_to_history({
            "time": datetime.now().strftime("%H:%M:%S"),
            "type": "Ricezione",
            "filename": transfer_info["filename"],
            "size": self.format_size(transfer_info["filesize"]),
            "peer": sender_name,
            "status": "Completato"
        })

    def save_settings(self):
        # Salva le impostazioni
        self.config["computer_name"] = self.computer_name_var.get()
        self.config["receive_directory"] = self.receive_dir_var.get()
        
        # Crea la directory di destinazione se non esiste
        receive_dir = self.receive_dir_var.get()
        if not os.path.exists(receive_dir):
            try:
                os.makedirs(receive_dir)
                print(f"Creata la directory: {receive_dir}")
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile creare la directory: {e}")
                return
        
        # Salva le modifiche nel file di configurazione
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)
        
        # Imposta l'avvio automatico
        if self.startup_var.get() != self.config["start_with_windows"]:
            self.set_startup(self.startup_var.get())
        
        # Aggiorna le impostazioni del receiver
        if self.receiver:
            # Aggiorna la configurazione nel receiver
            self.receiver.config.update(self.config)
            self.receiver.save_config()
            
            # Importante: registra di nuovo il dispositivo con il nuovo nome
            self.receiver.register_device()
            
            # Se il receiver è in esecuzione, riavvialo per applicare le modifiche
            if self.receiver.running:
                messagebox.showinfo("Riavvio Necessario", 
                                  "Alcune impostazioni richiedono il riavvio del servizio di ricezione. " + 
                                  "ZapShare verrà riavviato.")
                
                # Ferma il receiver attuale
                self.receiver.stop()
                
                # Avvia un nuovo receiver con le nuove impostazioni
                self.receiver = None
                self.start_receiver()
        
        messagebox.showinfo("Impostazioni", "Impostazioni salvate con successo")
        
        # Aggiorna l'interfaccia utente
        if self.receiver:
            self.connection_status.config(text=f"Stato: In ascolto su {self.receiver.ip}")

    def add_to_history(self, transfer):
        """Aggiunge un trasferimento alla cronologia"""
        self.transfer_history.append(transfer)
        
        # Aggiunge alla vista
        self.history_tree.insert("", 0, values=(
            transfer["time"],
            transfer["type"],
            transfer["filename"],
            transfer["size"],
            transfer["peer"],
            transfer["status"]
        ))

    def clear_history(self):
        """Cancella la cronologia dei trasferimenti"""
        if messagebox.askyesno("Cancella cronologia", "Sei sicuro di voler cancellare la cronologia?"):
            self.transfer_history = []
            
            # Cancella la vista
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)

    def format_size(self, size_bytes):
        """Formatta la dimensione in bytes in un formato leggibile"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    def show_help(self):
        messagebox.showinfo("Guida", 
                           "ZapShare\n\n"
                           "Questa applicazione permette di inviare e ricevere file tra dispositivi "
                           "sulla stessa rete.\n\n"
                           "1. Usa la scheda 'Invia File' per selezionare e inviare file\n"
                           "2. La scheda 'Dispositivi' mostra i dispositivi disponibili\n"
                           "3. La scheda 'Cronologia' mostra i trasferimenti recenti\n"
                           "4. Usa 'Impostazioni' per configurare l'app")

    def show_about(self):
        messagebox.showinfo("Info", 
                           "ZapShare v1.0\n\n"
                           "Un'applicazione per l'invio e la ricezione di file su rete locale.")

    def create_tray_icon(self):
        """Crea un'icona nella system tray"""
        # Per semplicità, creiamo un'immagine come icona
        icon_image = Image.new('RGB', (64, 64), color = (0, 120, 215))
        
        menu = (
            pystray.MenuItem('Mostra ZapShare', self.show_window),
            pystray.MenuItem('Invia File', self.show_window_send),
            pystray.MenuItem('Cerca dispositivi', self.discover_devices_tray),
            pystray.MenuItem('Esci', self.quit_app)
        )

        self.tray_icon = pystray.Icon("ZapShare", icon_image, "ZapShare", menu)
        self.tray_icon.run_detached()

    def show_window(self, icon=None, item=None):
        """Mostra la finestra principale dalla system tray"""
        self.root.deiconify()

    def show_window_send(self, icon=None, item=None):
        """Mostra la scheda di invio file dalla system tray"""
        self.root.deiconify()
        self.show_send_tab()

    def discover_devices_tray(self, icon=None, item=None):
        """Avvia la ricerca dispositivi dalla system tray"""
        self.discover_devices()

    def on_close(self):
        """Gestisce la chiusura della finestra principale"""
        # Nascondi la finestra invece di chiuderla
        self.root.withdraw()

        # Crea l'icona nella system tray
        self.create_tray_icon()

    def quit_app(self, icon=None, item=None):
        """Esce completamente dall'applicazione"""
        print("Chiusura completa dell'applicazione in corso...")

        # Ferma il receiver se è attivo
        if self.receiver and self.receiver.running:
            self.receiver.stop()
            self.receiver = None

        # Rimuovi l'icona dalla system tray se esiste
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.stop()
            except:
                pass

        # Termina tutti i thread non-daemon
        import threading
        for thread in threading.enumerate():
            if thread is not threading.current_thread() and not thread.daemon:
                try:
                    thread.join(0.1)  # Dai un breve tempo per chiudersi
                except:
                    pass

        # Distruggi la finestra principale
        if hasattr(self, 'root') and self.root:
            try:
                self.root.quit()  # Termina il mainloop
                self.root.destroy()  # Distruggi la finestra
            except:
                pass

        # Termina completamente il processo
        import os
        os._exit(0)  # Più drastico di sys.exit(), termina immediatamente

# Avvio dell'applicazione
if __name__ == "__main__":
    app = ZapShareApp()
    app.root.mainloop()
