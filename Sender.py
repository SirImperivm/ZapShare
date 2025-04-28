import socket
import json
import os
import sys
import time
import re
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

class Sender:
    def __init__(self):
        self.host = socket.gethostname()
        
        # Ottieni specificamente un indirizzo IP sulla rete 192.168.1.x
        self.ip = self.get_lan_ip()
        
        self.buffer_size = 4096
        self.devices_file = "zapshare_devices.json"
        self.devices = self.load_devices()
        self.transfer_callbacks = []
        
        print(f"Sender inizializzato con IP: {self.ip}")
    
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
    
    def get_network_interfaces(self):
        """Ottiene informazioni sulle interfacce di rete, con priorità per la rete 192.168.1.x"""
        interfaces = []
        
        try:
            # Su Windows
            if sys.platform == 'win32':
                # Ottieni tutti gli indirizzi IP associati all'hostname
                hostname = socket.gethostname()
                ip_list = socket.gethostbyname_ex(hostname)[2]
                
                # Filtra per prioritizzare 192.168.1.x
                primary_ips = [ip for ip in ip_list if ip.startswith('192.168.1.')]
                
                # Se non troviamo IP nella rete 192.168.1.x, prendi qualsiasi nella 192.168.x.x
                if not primary_ips:
                    primary_ips = [ip for ip in ip_list if ip.startswith('192.168.')]
                
                # Se ancora non troviamo, prendi qualsiasi IP non locale
                if not primary_ips:
                    primary_ips = [ip for ip in ip_list if not ip.startswith('127.') and not ip.startswith('169.254.')]
                
                # Se abbiamo trovato almeno un IP valido
                if primary_ips:
                    for ip in primary_ips:
                        # Calcola l'indirizzo broadcast
                        ip_parts = ip.split('.')
                        broadcast = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
                        
                        interfaces.append({
                            "name": f"interface-{len(interfaces)+1}",
                            "ip": ip,
                            "netmask": "255.255.255.0",
                            "broadcast": broadcast
                        })
                        
                        print(f"Trovata interfaccia: {ip} (broadcast: {broadcast})")
                else:
                    # Ultima risorsa, crea un socket specifico
                    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        temp_socket.connect(('10.255.255.255', 1))
                        ip = temp_socket.getsockname()[0]
                        
                        # Ottieni il broadcast address
                        ip_parts = ip.split('.')
                        broadcast = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
                        
                        interfaces.append({
                            "name": "default",
                            "ip": ip,
                            "netmask": "255.255.255.0",
                            "broadcast": broadcast
                        })
                        
                        print(f"Interfaccia di fallback: {ip} (broadcast: {broadcast})")
                    except Exception as e:
                        print(f"Errore nella connessione di test: {e}")
                    finally:
                        temp_socket.close()
            
            # Per sistemi Unix
            else:
                try:
                    import netifaces
                    
                    for interface in netifaces.interfaces():
                        addrs = netifaces.ifaddresses(interface)
                        
                        if netifaces.AF_INET in addrs:
                            for addr in addrs[netifaces.AF_INET]:
                                if 'addr' in addr and 'netmask' in addr:
                                    ip = addr['addr']
                                    netmask = addr['netmask']
                                    
                                    # Ignora localhost e link-local, priorità alla rete 192.168.1.x
                                    if ip.startswith('127.') or ip.startswith('169.254.'):
                                        continue
                                    
                                    # Priorità alta per 192.168.1.x
                                    priority = 1 if ip.startswith('192.168.1.') else 2
                                    
                                    # Calcola broadcast se non esiste
                                    broadcast = addr.get('broadcast')
                                    if not broadcast:
                                        ip_parts = [int(part) for part in ip.split('.')]
                                        mask_parts = [int(part) for part in netmask.split('.')]
                                        broadcast_parts = []
                                        
                                        for i in range(4):
                                            broadcast_part = (ip_parts[i] & mask_parts[i]) | (~mask_parts[i] & 255)
                                            broadcast_parts.append(str(broadcast_part))
                                        
                                        broadcast = '.'.join(broadcast_parts)
                                    
                                    interfaces.append({
                                        "name": interface,
                                        "ip": ip,
                                        "netmask": netmask,
                                        "broadcast": broadcast,
                                        "priority": priority
                                    })
                    
                    # Ordina le interfacce per priorità (192.168.1.x prima)
                    if interfaces:
                        interfaces.sort(key=lambda x: x.get("priority", 99))
                        # Rimuovi la chiave priority dopo l'ordinamento
                        for interface in interfaces:
                            if "priority" in interface:
                                del interface["priority"]
                
                except ImportError:
                    print("Il modulo netifaces non è installato. Utilizzo del metodo alternativo.")
                    # Metodo alternativo semplificato per Unix
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        s.connect(('10.255.255.255', 1))
                        ip = s.getsockname()[0]
                        
                        # Priorità alla rete 192.168.1.x
                        if not ip.startswith('192.168.1.'):
                            # Prova a trovare interfacce specifiche
                            try:
                                import subprocess
                                output = subprocess.check_output("ip addr show", shell=True).decode('utf-8')
                                for line in output.split('\n'):
                                    if '192.168.1.' in line:
                                        match = re.search(r'inet (192\.168\.1\.[0-9]+)', line)
                                        if match:
                                            ip = match.group(1)
                                            break
                            except Exception:
                                pass
                        
                        interfaces.append({
                            "name": "default",
                            "ip": ip,
                            "netmask": "255.255.255.0",
                            "broadcast": ip.rsplit('.', 1)[0] + '.255'
                        })
                    except Exception:
                        pass
                    finally:
                        s.close()
        
        except Exception as e:
            print(f"Errore nel recupero delle interfacce di rete: {e}")
        
        # Filtra le interfacce per prioritizzare 192.168.1.x
        filtered_interfaces = [i for i in interfaces if i["ip"].startswith('192.168.1.')]
        
        # Se non abbiamo trovato interfacce nella sottorete 192.168.1.x, usa tutte le interfacce disponibili
        if not filtered_interfaces:
            print("Attenzione: nessuna interfaccia trovata nella sottorete 192.168.1.x")
            return interfaces
        
        return filtered_interfaces
    
    # Il resto del codice rimane invariato
    def discover_devices(self, callback=None):
        # Cerca dispositivi sulla rete
        print("Ricerca dispositivi in corso...")
        
        # Ottieni informazioni sulle interfacce di rete
        interfaces = self.get_network_interfaces()
        if not interfaces:
            print("Nessuna interfaccia di rete valida trovata")
            return []
        
        discovered = []
        
        # Per ogni interfaccia valida
        for interface in interfaces:
            network_ip = interface["ip"]
            network_broadcast = interface["broadcast"]
            
            print(f"Scansione sulla rete: {network_ip} (broadcast: {network_broadcast})")
            
            # Crea un socket per il discovery
            discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            discovery_socket.settimeout(3)  # Timeout di 3 secondi
            
            try:
                # Invia richiesta di discovery all'indirizzo broadcast specifico
                discovery_socket.sendto(b'DISCOVERY_REQUEST', (network_broadcast, 9998))
                
                # Raccoglie le risposte
                start_time = time.time()
                
                while time.time() - start_time < 3:  # Aspetta risposte per 3 secondi
                    try:
                        data, addr = discovery_socket.recvfrom(1024)
                        device_info = json.loads(data.decode())
                        
                        # Verifica che il dispositivo sia nella rete 192.168.1.x
                        if not device_info["ip"].startswith('192.168.1.'):
                            print(f"Ignorato dispositivo non nella rete 192.168.1.x: {device_info['ip']}")
                            continue
                        
                        # Verifica se il dispositivo è già nell'elenco
                        already_exists = False
                        for device in discovered:
                            if device["ip"] == device_info["ip"]:
                                already_exists = True
                                break
                        
                        if not already_exists and device_info["ip"] != network_ip:
                            discovered.append(device_info)
                            print(f"Trovato: {device_info['name']} ({device_info['ip']})")
                            
                            # Chiamata di callback per aggiornamento in tempo reale
                            if callback:
                                callback(device_info)
                    except socket.timeout:
                        pass
                    except Exception as e:
                        print(f"Errore durante la scoperta: {e}")
            
            except Exception as e:
                print(f"Errore durante la ricerca sulla rete {network_ip}: {e}")
            finally:
                discovery_socket.close()
        
        # Aggiorna il file dei dispositivi
        existing_ips = [d["ip"] for d in self.devices["devices"]]
        for device in discovered:
            if device["ip"] not in existing_ips:
                self.devices["devices"].append(device)
                existing_ips.append(device["ip"])
            else:
                # Aggiorna il nome del dispositivo se è cambiato
                for d in self.devices["devices"]:
                    if d["ip"] == device["ip"]:
                        d["name"] = device["name"]
        
        self.save_devices()
        return discovered
    
    # Resto del codice rimane uguale
    def load_devices(self):
        """Carica la lista dei dispositivi conosciuti"""
        if os.path.exists(self.devices_file):
            try:
                with open(self.devices_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Errore nel caricamento dei dispositivi: {e}")
        
        # Se il file non esiste o c'è un errore, crea una lista vuota
        return {"devices": []}
    
    def save_devices(self):
        """Salva la lista dei dispositivi conosciuti"""
        with open(self.devices_file, 'w') as f:
            json.dump(self.devices, f, indent=4)
    
    def add_transfer_callback(self, callback):
        """Aggiunge una funzione di callback da chiamare quando un trasferimento è completato"""
        if callable(callback) and callback not in self.transfer_callbacks:
            self.transfer_callbacks.append(callback)
        return self
    
    def list_devices(self):
        """Stampa la lista dei dispositivi conosciuti"""
        devices = self.devices["devices"]
        
        if not devices:
            print("Nessun dispositivo conosciuto")
            return
        
        print("\nDispositivi conosciuti:")
        for i, device in enumerate(devices):
            print(f"{i+1}. {device['name']} ({device['ip']})")
        
        print()
    
    def send_file(self, file_path, device_index, progress_callback=None):
        """Invia un file al dispositivo specificato"""
        if not os.path.exists(file_path):
            print(f"Il file {file_path} non esiste")
            return False
        
        if device_index < 0 or device_index >= len(self.devices["devices"]):
            print("Indice dispositivo non valido")
            return False
        
        device = self.devices["devices"][device_index]
        
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        
        print(f"Invio di {file_name} ({file_size} bytes) a {device['name']} ({device['ip']})...")
        
        # Creazione socket
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(10)  # Timeout di 10 secondi
        
        try:
            # Connessione al dispositivo
            client_socket.connect((device["ip"], device.get("port", 9999)))
            
            # Invio informazioni sul file
            file_info = {
                "filename": file_name,
                "filesize": file_size
            }
            
            client_socket.send(json.dumps(file_info).encode())
            
            # Attesa conferma
            response = client_socket.recv(self.buffer_size).decode()
            if response != "OK":
                print(f"Errore nella conferma: {response}")
                return False
            
            # Invio del file
            bytes_sent = 0
            with open(file_path, 'rb') as f:
                while bytes_sent < file_size:
                    # Leggi un chunk di dati
                    chunk = f.read(self.buffer_size)
                    if not chunk:
                        break
                    
                    # Invia il chunk
                    client_socket.send(chunk)
                    bytes_sent += len(chunk)
                    
                    # Aggiorna il progresso
                    progress = int((bytes_sent / file_size) * 100)
                    if progress_callback:
                        progress_callback(progress)
                    
                    # Aggiorna il terminale
                    print(f"\rInvio in corso: {progress}%", end="")
            
            print("\nInvio completato con successo!")
            
            # Chiama le callback
            for callback in self.transfer_callbacks:
                try:
                    callback({
                        "status": "completed",
                        "filename": file_name,
                        "filesize": file_size,
                        "recipient": device["name"],
                        "recipient_ip": device["ip"]
                    })
                except Exception as e:
                    print(f"Errore nella callback: {e}")
            
            return True
            
        except ConnectionRefusedError:
            print(f"Connessione rifiutata da {device['ip']}. Assicurati che il dispositivo sia in ascolto.")
        except socket.timeout:
            print(f"Timeout durante la connessione a {device['ip']}.")
        except Exception as e:
            print(f"Errore durante l'invio del file: {e}")
        
        # Se arriviamo qui, c'è stato un errore
        for callback in self.transfer_callbacks:
            try:
                callback({
                    "status": "failed",
                    "filename": file_name,
                    "recipient": device["name"],
                    "recipient_ip": device["ip"],
                    "error": str(e) if 'e' in locals() else "Unknown error"
                })
            except Exception as e:
                print(f"Errore nella callback: {e}")
        
        return False