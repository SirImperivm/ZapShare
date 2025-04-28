import socket
import json
import os
import threading
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

class Receiver:
    def __init__(self):
        self.host = socket.gethostname()
        
        # Ottieni specificamente un indirizzo IP sulla rete 192.168.1.x
        self.ip = self.get_lan_ip()
        
        self.port = 9999
        self.buffer_size = 4096
        self.config_file = "zapshare_config.json" 
        self.devices_file = "zapshare_devices.json"
        self.config = self.load_config()
        self.running = False
        self.transfer_callbacks = []
        
        print(f"Inizializzato Receiver con indirizzo IP: {self.ip}")
    
    def get_lan_ip(self):
        """Ottiene specificamente un indirizzo IP sulla rete 192.168.1.x"""
        # Prova a trovare l'indirizzo specifico per la rete 192.168.1.x
        try:
            # Metodo 1: socket temporaneo
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # Non ha bisogno di essere raggiungibile
                s.connect(('10.255.255.255', 1))
                ip = s.getsockname()[0]
                # Controlla se l'IP è nella rete 192.168.1.x
                if ip.startswith('192.168.1.'):
                    return ip
            except Exception:
                pass
            finally:
                s.close()
            
            # Metodo 2: ottieni tutti gli IP
            hostname = socket.gethostname()
            ip_list = socket.gethostbyname_ex(hostname)[2]
            
            # Filtra per trovare un indirizzo 192.168.1.x
            for ip in ip_list:
                if ip.startswith('192.168.1.'):
                    return ip
            
            # Se non troviamo un IP specifico 192.168.1.x, proviamo a prendere qualsiasi IP nella classe 192.168
            for ip in ip_list:
                if ip.startswith('192.168.'):
                    print(f"Attenzione: non trovato IP nella rete 192.168.1.x, utilizzo {ip}")
                    return ip
            
            # Ultima risorsa: usa qualsiasi IP non locale
            for ip in ip_list:
                if not ip.startswith('127.') and not ip.startswith('169.254.'):
                    print(f"Attenzione: utilizzo IP alternativo: {ip}")
                    return ip
            
            # Se tutto fallisce, usa l'IP generico
            return socket.gethostbyname(hostname)
            
        except Exception as e:
            print(f"Errore nell'ottenere l'IP LAN: {e}")
            # Fallback: IP generico
            return socket.gethostbyname(socket.gethostname())
    
    def load_config(self):
        # Caricamento configurazione
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        else:
            # Configurazione di default
            default_config = {
                "receive_directory": str(Path.home() / "Downloads"),
                "start_with_windows": False,
                "computer_name": socket.gethostname()
            }
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            return default_config
    
    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)
    
    def register_device(self):
        # Aggiunge questo dispositivo al file devices.json
        if os.path.exists(self.devices_file):
            with open(self.devices_file, 'r') as f:
                devices = json.load(f)
        else:
            devices = {"devices": []}
        
        # Verifica se questo dispositivo è già registrato
        device_exists = False
        for device in devices["devices"]:
            if device["ip"] == self.ip:
                device_exists = True
                device["name"] = self.config["computer_name"]
                break
        
        if not device_exists:
            devices["devices"].append({
                "name": self.config["computer_name"],
                "ip": self.ip,
                "port": self.port
            })
        
        with open(self.devices_file, 'w') as f:
            json.dump(devices, f, indent=4)
    
    def add_transfer_callback(self, callback):
        """Aggiunge una funzione di callback da chiamare quando un file viene ricevuto"""
        self.transfer_callbacks.append(callback)
    
    def start_discovery_service(self):
        discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            discovery_socket.bind(('', 9998))
            
            print(f"Servizio di discovery avviato. In ascolto sulla porta 9998")
            
            while self.running:
                try:
                    data, addr = discovery_socket.recvfrom(1024)
                    sender_ip = addr[0]
                    
                    # Verifica se l'IP del mittente è nella rete 192.168.1.x
                    if not sender_ip.startswith('192.168.1.'):
                        print(f"Ignorata richiesta di discovery da rete non 192.168.1.x: {sender_ip}")
                        continue
                    
                    if data == b'DISCOVERY_REQUEST':
                        print(f"Richiesta di discovery ricevuta da {sender_ip}")
                        
                        # Risponde con informazioni sul dispositivo
                        response = json.dumps({
                            "name": self.config["computer_name"],
                            "ip": self.ip,
                            "port": self.port
                        }).encode()
                        discovery_socket.sendto(response, addr)
                except Exception as e:
                    if self.running:
                        print(f"Errore nel servizio di discovery: {e}")
        except Exception as e:
            print(f"Impossibile avviare il servizio di discovery: {e}")
        finally:
            discovery_socket.close()
    
    def receive_file(self, client_socket, client_address):
        try:
            # Verifica se l'IP del mittente è nella rete 192.168.1.x
            sender_ip = client_address[0]
            if not sender_ip.startswith('192.168.1.'):
                print(f"Ignorata connessione da rete non 192.168.1.x: {sender_ip}")
                client_socket.close()
                return
            
            # Riceve le informazioni sul file
            file_info = client_socket.recv(self.buffer_size).decode()
            file_info = json.loads(file_info)
            
            # Invia conferma di ricezione
            client_socket.send("OK".encode())
            
            # Crea il percorso di destinazione
            save_path = os.path.join(self.config["receive_directory"], file_info["filename"])
            
            # Riceve il file
            with open(save_path, 'wb') as f:
                bytes_received = 0
                while bytes_received < file_info["filesize"]:
                    data = client_socket.recv(self.buffer_size)
                    if not data:
                        break
                    f.write(data)
                    bytes_received += len(data)
            
            print(f"File ricevuto: {file_info['filename']} da {sender_ip}")
            
            # Notifica tramite callback
            transfer_info = {
                "filename": file_info["filename"],
                "filesize": file_info["filesize"],
                "sender_ip": sender_ip,
                "save_path": save_path
            }
            
            for callback in self.transfer_callbacks:
                try:
                    callback(transfer_info)
                except Exception as e:
                    print(f"Errore nella callback: {e}")
            
        except Exception as e:
            print(f"Errore durante la ricezione del file: {e}")
        finally:
            client_socket.close()
    
    def start(self):
        self.running = True
        self.register_device()
        
        # Avvia il thread per il servizio di discovery
        discovery_thread = threading.Thread(target=self.start_discovery_service)
        discovery_thread.daemon = True
        discovery_thread.start()
        
        # Crea il socket principale per la ricezione dei file
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind(('', self.port))
            server_socket.listen(5)
            print(f"Receiver avviato su {self.ip}:{self.port}")
            print(f"Nome computer: {self.config['computer_name']}")
            print(f"Cartella di ricezione: {self.config['receive_directory']}")
            print(f"Configurato per la rete 192.168.1.x")
            
            while self.running:
                try:
                    client_socket, client_address = server_socket.accept()
                    # Avvia un thread per gestire la ricezione del file
                    client_thread = threading.Thread(
                        target=self.receive_file,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except Exception as e:
                    if self.running:
                        print(f"Errore nella connessione: {e}")
        except Exception as e:
            print(f"Errore nell'avvio del server: {e}")
        finally:
            server_socket.close()
    
    def stop(self):
        self.running = False
        print("Receiver arrestato")

if __name__ == "__main__":
    receiver = Receiver()
    receiver.start()
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
                              "Alcune impostazioni richiedono il riavvio del servizio di ricezione. "+
                              "ZapShare verrà riavviato.")
            
            # Ferma il receiver attuale
            self.receiver.stop()
            
            # Avvia un nuovo receiver con le nuove impostazioni
            self.receiver = None
            self.start_receiver()
    
    messagebox.showinfo("Impostazioni", "Impostazioni salvate con successo")
    
    # Aggiorna l'interfaccia utente
    self.connection_status.config(text=f"Stato: In ascolto su {self.receiver.ip}")