#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
import warnings
import os
import sys
import logging

# --- CONFIGURATION IMPORT ---
import config
from config import (
    FilePaths, ModelConfig, TrainingConfig, GUIConfig, 
    BlockchainConfig, VisualizationConfig, FailureAnalysisConfig,
    LogConfig, ConfigUtils, EnvConfig
)

# --- TensorFlow WARNING'LERİNİ BASTIR (Import öncesi) ---
LogConfig.suppress_all_tf_warnings()


# Windows/Python UTF-8 konsol çıktısı (Türkçe karakterler için)
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# --- MODULAR FUNCTIONS ---
import training_utils
import reporting

# Konfigürasyondan warning ayarlarını al
for warning_type in LogConfig.SUPPRESS_WARNINGS:
    if warning_type == 'ignore':
        warnings.filterwarnings('ignore')
    else:
        warnings.filterwarnings('ignore', category=eval(warning_type))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import time
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, roc_curve, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Conv1D, MaxPooling1D, LSTM, GRU 
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.optimizers import Adam
import tkinter as tk
from tkinter import ttk, messagebox, font
from dotenv import load_dotenv  
import os
import webbrowser
import queue  

# Blockchain entegrasyonu
try:
    from web3 import Web3
    import threading
    from hybrid_blockchain_handler import HybridBlockchainHandler
    BLOCKCHAIN_AVAILABLE = True
    print("🔐 Hibrit Blockchain modülü yüklendi")
except ImportError as e:
    BLOCKCHAIN_AVAILABLE = False
    print(f"⚠️ Hibrit Blockchain modülü yüklenemedi: {e}")
    print("ℹ️ Gerekli kütüphaneler: pip install web3")

# TensorFlow warning'lerini bastır
LogConfig.suppress_tf_after_import()

# --- GLOBAL VARIABLES & CONFIGURATION ---

# Ağ konfigürasyonu (zkSync Era only)
ACTIVE_NETWORK = "ZKSYNC_ERA"
PRIVATE_KEY = EnvConfig.get_PRIVATE_KEY()

# Aktif ağa göre RPC URL ve deployment dosyası seç
CURRENT_RPC_URL = ConfigUtils.get_current_rpc_url()
DEPLOYMENT_INFO_PATH = ConfigUtils.get_deployment_info_path()
network_config = ConfigUtils.get_network_config()
NETWORK_NAME = network_config['name'] if network_config else "Unknown"
EXPLORER_BASE_URL = network_config['explorer'] if network_config else ""

# Dosya yolları
MODEL_PATH = FilePaths.MODEL_PATH
SCALER_PATH = FilePaths.SCALER_PATH

# Contract artifacts paths
PDM_ARTIFACTS_PATH = FilePaths.PDM_ARTIFACTS_PATH
FAILURE_VERIFIER_ARTIFACTS_PATH = FilePaths.FAILURE_VERIFIER_ARTIFACTS_PATH

# Global Değişkenler
model = None
scaler = None
feature_names = None
optimal_threshold = TrainingConfig.DEFAULT_THRESHOLD
zk_pdm = None  # ZK Blockchain instance
pdm_contract = None  # Contract instance
web3 = None  # Web3 instance
admin_account = None  # Admin account address

# --- BLOCKCHAIN HANDLER CLASS ---

class BlockchainHandler:
    """🔗 Blockchain işlemlerini yöneten ayrı sınıf"""
    
    def __init__(self):
        self.web3 = None
        self.pdm_contract = None
        self.admin_account = None
        self.private_key = PRIVATE_KEY
        self.rpc_url = CURRENT_RPC_URL
        self.network_name = NETWORK_NAME
        self.explorer_base_url = EXPLORER_BASE_URL
        self.deployment_info = None
        
    def initialize(self):
        """Blockchain bağlantısını kurar ve rolleri ayarlar"""
        if not BLOCKCHAIN_AVAILABLE:
            return False

        if not all([self.rpc_url, self.private_key]):
            print(f"❌ .env dosyasında RPC_URL veya Private_Key eksik!")
            return False

        try:
            print(f"🔗 {self.network_name} bağlantısı test ediliyor...")
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if not self.web3.is_connected():
                print(f"❌ {self.network_name} ağına bağlanılamadı!")
                return False

            account = self.web3.eth.account.from_key(self.private_key)
            self.admin_account = account.address
            balance = self.web3.from_wei(self.web3.eth.get_balance(self.admin_account), 'ether')

            print(f"✅ {self.network_name} bağlantısı başarılı!")
            print(f"👤 Admin Account: {self.admin_account}")
            print(f"💰 Bakiye: {balance:.4f} ETH")

            # Kontratları yükle
            contracts_loaded = self._load_contracts()

            # Eğer kontratlar başarıyla yüklendiyse, rolleri kontrol et/ayarla
            if contracts_loaded and self.is_ready():
                print("🔧 Roller kontrol ediliyor ve ayarlanıyor...")
                self.setup_admin_roles()
            return contracts_loaded
        except Exception as e:
            print(f"❌ {self.network_name} blockchain bağlantı hatası: {e}")
            return False
    
    def _load_contracts(self):
        """Contract'ları yükler (hata durumunda False döner)."""
        try:
            if not DEPLOYMENT_INFO_PATH.exists():
                print(f"⚠️ {DEPLOYMENT_INFO_PATH} bulunamadı - contract'lar yüklenmedi")
                return False

            with open(DEPLOYMENT_INFO_PATH, encoding='utf-8') as f:
                self.deployment_info = json.load(f)

            if not PDM_ARTIFACTS_PATH.exists():
                print("⚠️ Contract artifacts bulunamadı")
                return False

            with open(PDM_ARTIFACTS_PATH, encoding='utf-8') as f:
                pdm_artifact = json.load(f)

            pdm_address = None
            if isinstance(self.deployment_info, dict):
                contracts = self.deployment_info.get('contracts', {})
                if 'PdMSystemIntegrated' in contracts:
                    pdm_address = (contracts.get('PdMSystemIntegrated') or {}).get('address')
                if not pdm_address:
                    pdm_address = (
                        self.deployment_info.get('pdm_system_integrated_address') or
                        self.deployment_info.get('pdm_system_address')
                    )

            if not pdm_address:
                print("⚠️ Deployment dosyasında kontrat adresi bulunamadı.")
                try:
                    print(f"   ✅ Dosya anahtarları: {list((self.deployment_info or {}).keys())}")
                    if isinstance(self.deployment_info, dict) and 'contracts' in self.deployment_info:
                        print(f"   ✅ Contracts: {list(self.deployment_info['contracts'].keys())}")
                except Exception:
                    pass
                return False

            # Sözleşme örneğini oluştur
            self.pdm_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(pdm_address),
                abi=pdm_artifact['abi']
            )

            print(f"✅ PDM Contract Yüklendi: {pdm_address}")
            print(f"🎯 {self.network_name} blockchain sistemi tamamen hazır!")
            return True

        except Exception as e:
            print(f"❌ PDM Contract yükleme hatası: {e}")
            return False

        except FileNotFoundError as file_e:
            print(f"⚠️ Dosya bulunamadı: {file_e}")
            return False
        except json.JSONDecodeError as json_e:
            print(f"⚠️ JSON parse hatası: {json_e}")
            return False
        except Exception as contract_e:
            print(f"⚠️ Contract yükleme hatası: {contract_e}")
            return False


    def is_ready(self):
        """Blockchain sistemi işlem yapmaya hazır mı?"""
        return all([self.web3, self.admin_account, self.pdm_contract])
    
    def _get_gas_price(self):
        """zkSync Era için dinamik gas price hesaplar"""
        try:
            # zkSync Era için çok düşük gas price
            current_gas_price = self.web3.eth.gas_price
            min_gas_price = self.web3.to_wei(BlockchainConfig.SENSOR_DATA_GAS_PRICE_GWEI, 'gwei')
            return max(current_gas_price, min_gas_price)
        except Exception:
            # Fallback
            return self.web3.to_wei(BlockchainConfig.SENSOR_DATA_GAS_PRICE_GWEI, 'gwei')
    
    def _estimate_gas_with_buffer(self, transaction, multiplier=1.2):
        """Gas estimation with buffer for zkSync Era compatibility"""
        try:
            estimated_gas = self.web3.eth.estimate_gas(transaction)
            return int(estimated_gas * multiplier)
        except Exception:
            # Fallback to default gas limits
            return BlockchainConfig.SENSOR_DATA_GAS_LIMIT
    
    def get_network_info(self):
        """Network bilgilerini döndürür"""
        if not self.web3:
            return None
        
        try:
            balance = self.web3.from_wei(self.web3.eth.get_balance(self.admin_account), 'ether')
            currency = "ETH"  # zkSync Era always uses ETH
            
            return {
                'network_name': self.network_name,
                'chain_id': self.web3.eth.chain_id,
                'block_number': self.web3.eth.block_number,
                'admin_account': self.admin_account,
                'balance': balance,
                'currency': currency,
                'explorer_base_url': self.explorer_base_url
            }
        except Exception as e:
            print(f"❌ Network bilgisi alınamadı: {e}")
            return None
    
    def setup_admin_roles(self):
        """Admin account'a gerekli rolleri ekler"""
        if not self.is_ready():
            return False
            
        try:
            print("🔧 Admin account rolleri kontrol ediliyor...")
            
            # Gerekli roller
            engineer_role = self.pdm_contract.functions.ENGINEER_ROLE().call()
            worker_role = self.pdm_contract.functions.WORKER_ROLE().call()
            
            # Mevcut roller kontrol et
            has_engineer = self.pdm_contract.functions.hasRole(engineer_role, self.admin_account).call()
            has_worker = self.pdm_contract.functions.hasRole(worker_role, self.admin_account).call()
            
            roles_to_grant = []
            if not has_engineer:
                roles_to_grant.append(('ENGINEER_ROLE', engineer_role))
            if not has_worker:
                roles_to_grant.append(('WORKER_ROLE', worker_role))
                
            if not roles_to_grant:
                print("✅ Admin account'da tüm gerekli roller mevcut")
                return True
                
            print(f"🔧 {len(roles_to_grant)} rol eklenecek: {[role[0] for role in roles_to_grant]}")
            
            # Rolleri ekle
            for role_name, role_hash in roles_to_grant:
                nonce = self.web3.eth.get_transaction_count(self.admin_account)
                
                grant_role_tx = self.pdm_contract.functions.grantRole(
                    role_hash, 
                    self.admin_account
                ).build_transaction({
                    'from': self.admin_account,
                    'nonce': nonce,
                    'gas': 200000,
                    'gasPrice': self._get_gas_price()
                })
                
                signed_tx = self.web3.eth.account.sign_transaction(grant_role_tx, private_key=self.private_key)
                tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                
                print(f"📤 {role_name} ekleniyor... Tx: {tx_hash.hex()}")
                
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                if receipt.status == 1:
                    print(f"✅ {role_name} başarıyla eklendi!")
                else:
                    print(f"❌ {role_name} eklenirken hata: Status {receipt.status}")
                    return False
                    
            return True
            
        except Exception as e:
            print(f"❌ Role setup hatası: {e}")
            return False

    def get_contract_info(self):
        """Contract bilgilerini, güncel JSON yapısını okuyarak döndürür."""
        if not self.deployment_info:
            return None
    
        # Yeni, iç içe geçmiş JSON yapısından verileri güvenli bir şekilde al
        contracts = self.deployment_info.get('contracts', {})
    
        pdm_contract_data = contracts.get('PdMSystemIntegrated', {})
        verifier_contract_data = contracts.get('UnifiedGroth16Verifier', {}) or contracts.get('OptimizedGroth16Verifier', {})
    
        # Anahtar isimleri JSON dosyasıyla eşleşiyor
        pdm_address = pdm_contract_data.get('address')
        verifier_address = verifier_contract_data.get('address')
    
        # Eğer adreslerden biri bile bulunamazsa, bilgiyi eksik kabul et
        if not pdm_address:
            return None
        
        return {
            'pdm_address': pdm_address,
            'verifier_address': verifier_address,
            'deployment_time': self.deployment_info.get('deployment_time', 'Bilinmiyor'),
            'system_type': self.deployment_info.get('system_type', 'hybrid'),
            'admin_account': self.admin_account,
            'deployment_status': 'Başarılı' # Dosya varsa başarılıdır 
        }
    
    def store_prediction_to_blockchain(self, prediction_data):
        """Tahmin verilerini blockchain'e kaydeder"""
        if not self.is_ready():
            return {'success': False, 'error': 'Blockchain sistemi hazır değil!'}
        
        try:
            # Blockchain işlemleri
            machine_id = int(time.time()) % 10000
            
            # Prediction hash'lerini oluştur
            data_commitment = self.web3.keccak(text=f"sensor_data_{machine_id}_{prediction_data['timestamp']}")
            metadata_hash = self.web3.keccak(text=f"metadata_{prediction_data['air_temp']}_{prediction_data['process_temp']}")
            
            # Sensör verisi kaydet
            sensor_result = self._submit_sensor_data(machine_id, data_commitment, metadata_hash, prediction_data)
            if not sensor_result['success']:
                return sensor_result
            
            # Prediction kaydet
            prediction_result = self._store_prediction(machine_id, prediction_data, sensor_result['data_id'])
            if not prediction_result['success']:
                return prediction_result
            
            return {
            'success': True,
            'machine_id': machine_id,
            'sensor_tx_hash': sensor_result['tx_hash'],
            'sensor_block_number': sensor_result['block_number'], 
            'prediction_tx_hash': prediction_result['tx_hash'],
            'prediction_block_number': prediction_result['block_number'], 
            'data_id': sensor_result['data_id']
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}


    def _submit_sensor_data(self, machine_id, data_commitment, metadata_hash, prediction_data):
        """Sensör verilerini blockchain'e kaydeder (Sadeleştirilmiş Versiyon)"""
        try:
            
            engineer_role = self.pdm_contract.functions.ENGINEER_ROLE().call()

            print(f"✅ Yetki kontrolü: Admin account'un rolleri mevcut.")
        
            nonce = self.web3.eth.get_transaction_count(self.admin_account)

            # Gerekli veri dönüşümlerini yap
            air_temp_int = int(prediction_data['air_temp'] * 100)
            process_temp_int = int(prediction_data['process_temp'] * 100)
            rotation_speed_int = int(prediction_data['rotation_speed'])
            torque_int = int(prediction_data['torque'] * 100)
            tool_wear_int = int(prediction_data['tool_wear'])
        
            machine_type_str = prediction_data.get('machine_type', 'M')
            machine_type_enum_map = {'L': 1, 'M': 2, 'H': 3}
            machine_type_enum = machine_type_enum_map.get(machine_type_str, 2)
        
            # Transaction oluştur
            submit_data_tx = self.pdm_contract.functions.submitSensorData(
                machine_id, 
                data_commitment, 
                metadata_hash,
                air_temp_int, 
                process_temp_int, 
                rotation_speed_int,
                torque_int, 
                tool_wear_int, 
                machine_type_enum,
                engineer_role

            ).build_transaction({
                'from': self.admin_account,
                'nonce': nonce,
                'gas': BlockchainConfig.SENSOR_DATA_GAS_LIMIT,
                'gasPrice': self._get_gas_price()
            })
        
            signed_data_tx = self.web3.eth.account.sign_transaction(submit_data_tx, private_key=self.private_key)
            data_tx_hash = self.web3.eth.send_raw_transaction(signed_data_tx.raw_transaction)
            data_receipt = self.web3.eth.wait_for_transaction_receipt(data_tx_hash, timeout=BlockchainConfig.TRANSACTION_TIMEOUT)
        
            if data_receipt.status == 1:
                data_id = self.pdm_contract.functions.dataCounter().call() - 1
                sensor_tx_hash_str = data_tx_hash.hex()
                
                # TX hash format doğrulaması
                print(f"🔗 Sensor TX Hash oluşturuldu: {sensor_tx_hash_str} (uzunluk: {len(sensor_tx_hash_str)})")
                if len(sensor_tx_hash_str) != 66 or not sensor_tx_hash_str.startswith('0x'):
                    print(f"⚠️ Geçersiz Sensor TX hash formatı! Beklenen: 66 karakter, 0x ile başlamalı!")
                    print(f"   Alınan: {sensor_tx_hash_str}")
                
                return {
                    'success': True,
                    'tx_hash': sensor_tx_hash_str,
                    'data_id': data_id,
                    'block_number': data_receipt.blockNumber
                }
            else:
                print(f"❌ Sensör verisi gönderme işlemi başarısız oldu! Status: {data_receipt.status}")
                return {'success': False, 'error': f'Sensör transaction başarısız, Status: {data_receipt.status}'}
            
        except Exception as e:
            return {'success': False, 'error': f'Sensör verisi hatası: {str(e)}'}
   
    def _store_prediction(self, machine_id, prediction_data, data_id):
        """Prediction'ı blockchain'e kaydeder"""
        try:
            nonce = self.web3.eth.get_transaction_count(self.admin_account)
            
            # Prediction ve probability değerlerini uygun formata çevir
            prediction_int = int(prediction_data['prediction'])  # 0 veya 1 zaten
            probability_int = int(prediction_data['probability'] * 10000)  # 0.7234 → 7234 (x10000 precision)
            
            print(f"🔢 Prediction dönüşüm: {prediction_data['prediction']} → {prediction_int}, "
                  f"Probability {prediction_data['probability']:.4f} → {probability_int}")
            
            prediction_tx = self.pdm_contract.functions.storePrediction(
                machine_id,
                prediction_int,
                probability_int,
                data_id
            ).build_transaction({
                'from': self.admin_account,
                'nonce': nonce,
                'gas': BlockchainConfig.PREDICTION_GAS_LIMIT,
                'gasPrice': self._get_gas_price()
            })
            
            signed_pred_tx = self.web3.eth.account.sign_transaction(prediction_tx, private_key=self.private_key)
            pred_tx_hash = self.web3.eth.send_raw_transaction(signed_pred_tx.raw_transaction)
            
            pred_receipt = self.web3.eth.wait_for_transaction_receipt(pred_tx_hash, timeout=BlockchainConfig.TRANSACTION_TIMEOUT)
            
            if pred_receipt.status == 1:
                # Debug bilgisi
                pred_tx_hash_str = pred_tx_hash.hex()
                print(f"🔗 Prediction Tx Hash oluşturuldu: {pred_tx_hash_str} (uzunluk: {len(pred_tx_hash_str)})")
                
                # TX hash format doğrulaması
                if len(pred_tx_hash_str) != 66 or not pred_tx_hash_str.startswith('0x'):
                    print(f"⚠️ Geçersiz Tx hash formatı! Beklenen: 66 karakter, 0x ile başlamalı!")
                    print(f"   Alınan: {pred_tx_hash_str}")
                
                return {
                    'success': True,
                    'tx_hash': pred_tx_hash_str,
                    'block_number': pred_receipt.blockNumber
                }
            else:
                # Detaylı hata bilgisi
                print(f"❌ Prediction Transaction FAILED!")
                print(f"   • Transaction Hash: {pred_tx_hash.hex()}")
                print(f"   • Block Number: {pred_receipt.blockNumber}")
                print(f"   • Gas Used: {pred_receipt.gasUsed}")
                print(f"   • Status: {pred_receipt.status}")
                
                return {'success': False, 'error': f'Prediction transaction başarısız, Status: {pred_receipt.status}, Gas: {pred_receipt.gasUsed}'}
                
        except Exception as e:
            return {'success': False, 'error': f'Prediction hatası: {str(e)}'}

# Global hibrit blockchain handler instance
from database_manager import PdMDatabaseManager
if BLOCKCHAIN_AVAILABLE:
    from hybrid_blockchain_handler import HybridBlockchainHandler
else:
    class _DummyHybridHandler:
        def is_ready(self):
            return False

pdm_db = PdMDatabaseManager()
hybrid_blockchain_handler = (
    HybridBlockchainHandler(db_manager=pdm_db) if BLOCKCHAIN_AVAILABLE else _DummyHybridHandler()
)


def setup_blockchain():
    """Global hibrit blockchain handler'ı başlatır"""
    if hybrid_blockchain_handler.is_ready():
        print("✅ Blockchain sistemi hazır!")
        return True
    else:
        print("⚠️ Blockchain sistemi hazır değil, sadece local storage aktif")
        return False

def train_model():
    """AI4I2020 dataset ile LSTM-CNN model eğitim pipeline'ını çalıştırır.

    ModelTrainer sınıfını kullanarak tam eğitim sürecini gerçekleştirir:
    veri yükleme, cross validation, final model eğitimi ve sonuç raporlama.
    Eğitilen model ve scaler global değişkenlerde saklanır.

    Global Variables Modified:
        model (tf.keras.Model): Eğitilen LSTM-CNN modeli
        scaler (StandardScaler): Fit edilmiş feature scaler
        feature_names (list): Özellik isimleri listesi  
        optimal_threshold (float): Bulunan optimal eşik değeri

    Returns:
        bool: Eğitim başarılı olursa True, aksi halde False.

    Raises:
        Exception: Dataset yükleme veya model eğitimi hatası oluşursa.

    Note:
        Bu fonksiyon training_utils.ModelTrainer sınıfını kullanır ve
        reporting modülü ile sonuçları görselleştirir.

    Example:
        >>> success = train_model()
        🔄 LSTM-CNN Model Eğitimi Başlıyor...
        📁 Veri yükleme ve ön işleme başlıyor...
        🔄 5-Fold Cross Validation başlıyor...
        ✅ LSTM-CNN Model Eğitimi Tamamlandı!
    """
    global model, scaler, feature_names, optimal_threshold
    
    print("🔄 LSTM-CNN Model Eğitimi Başlıyor...")
    print("="*80)
    
    # ModelTrainer sınıfını başlat
    trainer = training_utils.ModelTrainer()
    
    # Tam eğitim pipeline'ını çalıştır
    print("🚀 ModelTrainer pipeline başlatılıyor...")
    model, scaler, results = trainer.run_training_pipeline()
    
    # Sınıftan durumları al
    feature_names = trainer.feature_names
    optimal_threshold = trainer.optimal_threshold
    
    # Sonuçları raporla (reporting.py)
    print("\n📊 Eğitim sonuçları raporlanıyor...")
    test_results = results['test_results']
    
    # Artık sadece klasik CV sonuçları (Genetik algoritma kaldırıldı)
    cv_scores = results['cv_results']
    reporting.print_cv_results(cv_scores)
    reporting.print_test_results(test_results, cv_scores)
    reporting.plot_all_results(cv_scores, test_results)
    
    print(f"✅ LSTM-CNN Model Eğitimi Tamamlandı!")
    print(f"🎯 Final Performans: F1={test_results['optimal_threshold_results']['f1']:.4f}")
    print(f"🖥️ GUI arayüzü başlatılıyor...")
    print(f"{'='*80}")
    
    return True

# PredictiveMaintenance sınıfı ve diğer GUI kodları buraya eklenecek...
# (Şu anda sadece temel yapıyı oluşturuyoruz)

class PredictiveMaintenance:
    """LSTM-CNN tabanlı Predictive Maintenance GUI uygulaması.

    Sensör verilerini kullanarak makine arıza tahmini yapan Tkinter tabanlı
    grafik arayüz sınıfı. AI4I2020 dataset formatında 5 sensör girişi alır
    ve LSTM-CNN modeli ile arıza analizi yapar.

    Attributes:
        root (tk.Tk): Ana Tkinter penceresi
        sensor_vars (dict): Sensör input değişkenleri dict'i
        machine_type (tk.StringVar): Makine tipi değişkeni
        result_queue (queue.Queue): Threading için sonuç queue'su
        is_processing (bool): İşlem durumu flag'i

    Example:
        >>> root = tk.Tk()
        >>> app = PredictiveMaintenance(root)
        >>> root.mainloop()
    """
    
    def __init__(self, root):
        """GUI uygulamasını başlatır ve arayüz bileşenlerini oluşturur.

        Args:
            root (tk.Tk): Ana Tkinter penceresi.

        Note:
            Bu fonksiyon çağrıldığında tüm GUI bileşenleri otomatik olarak
            oluşturulur ve varsayılan sensör değerleri ayarlanır.
        """
        self.root = root
        self.root.title(f"🔧 LSTM-CNN Arıza Tespit Sistemi - {NETWORK_NAME}")
        self.root.geometry("1000x700")
        self.root.configure(bg='#f0f0f0')
        
        self.title_font = font.Font(family="Arial", size=16, weight="bold")
        self.label_font = font.Font(family="Arial", size=10)
        self.button_font = font.Font(family="Arial", size=12, weight="bold")
        
        self.result_queue = queue.Queue()
        self.is_processing = False
        self.predict_button = None
        self.progress_label = None
        self.time_label = None
        self.start_time = None
        
        self.create_widgets()
        self.check_queue()
        print("🖥️ GUI sistemi hazırlandı")
        
    def create_widgets(self):
        # Ana başlık
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=80)
        title_frame.pack(fill='x', padx=0, pady=0)
        title_frame.pack_propagate(False)
        title_label = tk.Label(title_frame, text="ARIZA TESPİT SİSTEMİ", font=self.title_font, bg='#2c3e50', fg='white')
        title_label.pack(expand=True)
        
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        left_frame = tk.LabelFrame(main_frame, text="SENSÖR VERİLERİ", font=self.label_font, bg='#ecf0f1', padx=10, pady=10)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_sensor_inputs(left_frame)
        
        right_frame = tk.LabelFrame(main_frame, text="ARIZA TESPİT SONUÇLARI", font=self.label_font, bg='#ecf0f1', padx=10, pady=10)
        right_frame.pack(side='right', fill='both', expand=True, padx=(10, 0))
        self.create_result_area(right_frame)
        
    def create_sensor_inputs(self, parent):
        # Sensör girişleri için ana frame
        main_input_frame = tk.Frame(parent, bg='#ecf0f1')
        main_input_frame.pack(fill='both', expand=True, padx=10, pady=5)  # pady: 10 -> 5
        
        self.sensor_vars = {}
        
        # 5 sensör yan yana
        sensors_row = tk.Frame(main_input_frame, bg='#ecf0f1')
        sensors_row.pack(fill='x', pady=5)
        
        sensors_configs = [
            ("Hava Sıcaklığı [K]", "Air temperature [K]", GUIConfig.DEFAULT_AIR_TEMP, (GUIConfig.MIN_AIR_TEMP, GUIConfig.MAX_AIR_TEMP)),
            ("İşlem Sıcaklığı [K]", "Process temperature [K]", GUIConfig.DEFAULT_PROCESS_TEMP, (GUIConfig.MIN_PROCESS_TEMP, GUIConfig.MAX_PROCESS_TEMP)),
            ("Dönme Hızı [rpm]", "Rotational speed [rpm]", GUIConfig.DEFAULT_ROTATION_SPEED, (GUIConfig.MIN_ROTATION_SPEED, GUIConfig.MAX_ROTATION_SPEED)),
            ("Tork [Nm]", "Torque [Nm]", GUIConfig.DEFAULT_TORQUE, (GUIConfig.MIN_TORQUE, GUIConfig.MAX_TORQUE)),
            ("Takım Aşınması [dk]", "Tool wear [min]", GUIConfig.DEFAULT_TOOL_WEAR, (GUIConfig.MIN_TOOL_WEAR, GUIConfig.MAX_TOOL_WEAR))
        ]
        
        # Ortadaki (3.) sütunu işaretle
        sensor_columns = []
        for i, (display_name, var_name, default_val, range_val) in enumerate(sensors_configs):
            col_frame = tk.Frame(sensors_row, bg='#ecf0f1')
            col_frame.pack(side='left', fill='both', expand=True, padx=3)
            tk.Label(col_frame, text=display_name, font=self.label_font, bg='#ecf0f1').pack()
            var = tk.DoubleVar(value=default_val)
            self.sensor_vars[var_name] = var
            tk.Entry(col_frame, textvariable=var, font=self.label_font, width=10, justify='center').pack(pady=2)
            tk.Label(col_frame, text=f"({range_val[0]}-{range_val[1]})", font=('Arial', 7), bg='#ecf0f1', fg='#7f8c8d').pack()
            
            # Ortadaki sütunu kaydet (Dönme Hızı - index 2)
            if i == 2:
                sensor_columns.append(col_frame)
        
        # Makine Tipi - Ortadaki sütunun (Dönme Hızı) altına
        machine_type_row = tk.Frame(main_input_frame, bg='#ecf0f1')
        machine_type_row.pack(fill='x', pady=10)
        
        # Ortadaki sütunu hizalamak için boş frame'ler ekle
        for i in range(5):
            spacer = tk.Frame(machine_type_row, bg='#ecf0f1')
            spacer.pack(side='left', fill='both', expand=True, padx=3)
            
            # Ortadaki (3.) sütuna Makine Tipi ekle
            if i == 2:
                tk.Label(spacer, text="🏭 Makine Tipi", font=self.label_font, bg='#ecf0f1').pack()
                self.machine_type = tk.StringVar(value="M")
                type_combo = ttk.Combobox(spacer, textvariable=self.machine_type, values=["L (Low - %50)", "M (Medium - %30)", "H (High - %20)"], state="readonly", width=12, justify='center')
                type_combo.pack(pady=2)
        
        button_frame = tk.Frame(main_input_frame, bg='#ecf0f1')
        button_frame.pack(fill='x', pady=10)  # 20 -> 10
        
        button_configs = [
            ("ARIZA ANALİZİ YAP", self.predict_failure, '#3498db', self.button_font),
            ("RASTGELE VERİ", self.set_random_data, '#95a5a6', self.label_font),
            ("SIFIRLA", self.reset_data, '#e74c3c', self.label_font),
            ("BLOCKCHAIN", self.show_blockchain_stats, '#9C27B0', self.label_font),
            ("RELOAD", self.reload_contracts, '#FF9800', self.label_font)
        ]

        for i, (text, command, bg, font) in enumerate(button_configs):
            button = tk.Button(button_frame, text=text, command=command, font=font, bg=bg, fg='white', height=2)
            button.pack(side='left', fill='both', expand=True, padx=1)  # 2 -> 1
            if i == 0: self.predict_button = button

        separator = tk.Frame(main_input_frame, height=2, bg='#bdc3c7')
        separator.pack(fill='x', pady=5)  # 10 -> 5
        
        analysis_frame = tk.LabelFrame(main_input_frame, text="ARIZA TİPİ ANALİZİ & HESAPLANAN DEĞERLER", font=('Arial', 11, 'bold'), bg='#ecf0f1')
        analysis_frame.pack(fill='both', expand=True, pady=(5, 0))  # Üstte 5, altta 0 boşluk
        self.analysis_result_frame = tk.Frame(analysis_frame, bg='#ecf0f1')
        self.analysis_result_frame.pack(fill='both', expand=True, padx=10, pady=5)  # 10 -> 5
        tk.Label(self.analysis_result_frame, text="📊 Arıza analizi yaptıktan sonra burada detaylı bilgiler görünecek", font=('Arial', 12, 'normal'), bg='#ecf0f1', fg='#7f8c8d').pack(expand=True)
        
    def check_queue(self):
        """Queue'dan gelen sonuçları kontrol eder"""
        try:
            while True:
                result = self.result_queue.get_nowait()
                if result['type'] == 'progress': self.update_progress(result['message'])
                elif result['type'] == 'result': self.handle_prediction_result(result)
                elif result['type'] == 'error': self.handle_prediction_error(result['error'])
                
        except queue.Empty: pass
        except Exception as e:
            print(f"⚠️ Queue işleme hatası: {e}")
            self.is_processing = False
            if self.predict_button: self.predict_button.config(state='normal', text="ARIZA ANALİZİ YAP")
            self.progress_label = self.time_label = None
        finally:
            try:
                self.root.after(GUIConfig.QUEUE_CHECK_INTERVAL, self.check_queue)
            except:
                pass
    
    def update_progress(self, message):
        """Progress mesajını ve süreyi günceller"""
        try:
            if self.progress_label and self.progress_label.winfo_exists(): self.progress_label.config(text=message)
            if self.time_label and self.time_label.winfo_exists() and self.start_time:
                self.time_label.config(text=f"⏱️ Geçen Süre: {time.time() - self.start_time:.1f} saniye")
        except tk.TclError: self.progress_label = self.time_label = None
    
    def show_progress(self):
        """Progress gösterimini başlatır"""
        for widget in self.result_frame.winfo_children(): widget.destroy()
        progress_frame = tk.Frame(self.result_frame, bg='#ecf0f1')
        progress_frame.pack(fill='both', expand=True)
        tk.Label(progress_frame, text="ARIZA ANALİZİ YAPILIYOR...", font=('Arial', 16, 'bold'), bg='#ecf0f1', fg='#3498db').pack(pady=30)
        self.progress_label = tk.Label(progress_frame, text="Sistem başlatılıyor...", font=('Arial', 12), bg='#ecf0f1', fg='#7f8c8d')
        self.progress_label.pack(pady=10)
        self.time_label = tk.Label(progress_frame, text="Geçen Süre: 0.0 saniye", font=('Arial', 11, 'bold'), bg='#ecf0f1', fg='#3498db')
        self.time_label.pack(pady=5)
        progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        progress_bar.pack(pady=20, padx=50, fill='x')
        progress_bar.start()
        tk.Button(progress_frame, text="❌ İPTAL", command=self.cancel_prediction, font=('Arial', 10, 'bold'), bg='#e74c3c', fg='white').pack(pady=10)
    
    def cancel_prediction(self):
        """İşlemi iptal eder"""
        self.is_processing = False
        if self.predict_button: self.predict_button.config(state='normal', text="🔍 ARIZA ANALİZİ YAP")
        self.progress_label = self.time_label = self.start_time = None
        for widget in self.result_frame.winfo_children(): widget.destroy()
        tk.Label(self.result_frame, text="❌ İşlem iptal edildi\n\nYeniden denemek için 'ARIZA ANALİZİ YAP' butonuna tıklayın", font=self.label_font, bg='#ecf0f1', fg='#e74c3c', justify='center').pack(expand=True)
    
    def handle_prediction_result(self, result):
        """Prediction sonucunu işler (Değişken adı hatası düzeltildi)"""
        self.is_processing = False
        if self.predict_button:
            self.predict_button.config(state='normal', text="🔍 ARIZA ANALİZİ YAP")
        
        self.progress_label = self.time_label = None
        
        if self.start_time:
            result['total_time'] = time.time() - self.start_time
            print(f"✅ Toplam işlem süresi: {result['total_time']:.2f} saniye")
            self.start_time = None
        
        # 'result_data' yerine doğru değişken adı olan 'result' kullanılıyor.
        self.show_prediction_result(result)
        
        # 'user_data' anahtarının varlığını kontrol ederek daha güvenli hale getirelim
        if 'user_data' in result:
            self.show_failure_analysis(result['user_data'])
        else:
            print(f"⚠️ Warning: 'user_data' key missing in result: {list(result.keys())}")
    
    
    def handle_prediction_error(self, error_data):
        """Prediction hatasını işler"""
        self.is_processing = False

        if self.predict_button:
            self.predict_button.config(state='normal', text="ARIZA ANALİZİ YAP")
        self.progress_label = self.time_label = self.start_time = None

        for widget in self.result_frame.winfo_children():
            widget.destroy()
        
        error_message = error_data.get('error', 'Bilinmeyen bir hata oluştu.')
        error_text = f"❌ HATA OLUŞTU:\n\n{error_message}\n\nTekrar deneyin veya sistem yöneticisine başvurun"
        tk.Label(self.result_frame, text=error_text, font=self.label_font, bg='#ecf0f1', fg='#e74c3c', justify='center', wraplength=400).pack(expand=True)
        messagebox.showerror("Hata", f"Tahmin hatası: {error_message}")

        if 'user_data' in error_data:
            self.show_failure_analysis(error_data['user_data'])
        else:
            # Eğer user_data yoksa, paneli temizle.
            for widget in self.analysis_result_frame.winfo_children():
                widget.destroy()
            tk.Label(self.analysis_result_frame, text="Hata nedeniyle analiz yapılamadı.", font=('Arial', 12, 'normal'), bg='#ecf0f1', fg='#e74c3c').pack(expand=True)
        
    def create_result_area(self, parent):
        # Sonuç gösterimi
        self.result_frame = tk.Frame(parent, bg='#ecf0f1')
        self.result_frame.pack(fill='both', expand=True)
        tk.Label(self.result_frame, text="👋 Arıza tespiti için sensör verilerini girin ve\n'ARIZA ANALİZİ YAP' butonuna tıklayın", font=self.label_font, bg='#ecf0f1', fg='#7f8c8d', justify='center').pack(expand=True)
        
          
    def generate_random_data(self):
        """AI4I2020 dataset aralıklarından rastgele sensör verileri üretir"""
        import random
        
        # AI4I2020 dataset'inin gerçek aralıklarından rastgele değerler
        random_air_temp = round(random.uniform(295.0, 305.0), 1)
        random_process_temp = round(random.uniform(305.0, 315.0), 1)
        random_rotation_speed = random.randint(1000, 3000)
        random_torque = round(random.uniform(3.0, 77.0), 1)
        random_tool_wear = random.randint(0, 300)
        
        # Değerleri input alanlarına yerleştir
        self.air_temp_var.set(str(random_air_temp))
        self.process_temp_var.set(str(random_process_temp))
        self.rotation_speed_var.set(str(random_rotation_speed))
        self.torque_var.set(str(random_torque))
        self.tool_wear_var.set(str(random_tool_wear))
        
        # Bilgi mesajı
        messagebox.showinfo(
            "Rastgele Veri Üretildi", 
            f"Yeni rastgele değerler:\n"
            f"Hava Sıcaklığı: {random_air_temp}K\n"
            f"İşlem Sıcaklığı: {random_process_temp}K\n"
            f"Dönüş Hızı: {random_rotation_speed} rpm\n"
            f"Tork: {random_torque} Nm\n"
            f"Takım Aşınması: {random_tool_wear} dk"
        )
        
        print(f"🎲 Rastgele veri üretildi: Hava={random_air_temp}K, İşlem={random_process_temp}K, "
              f"Hız={random_rotation_speed}rpm, Tork={random_torque}Nm, Aşınma={random_tool_wear}dk")

    def show_blockchain_info(self):
        """Blockchain bilgi penceresini açar"""
        
        # Yeni pencere oluştur
        info_window = tk.Toplevel(self.root)
        info_window.title("🔗 Blockchain Bilgileri")
        info_window.geometry("500x600")
        info_window.configure(bg='#f8f9fa')
        info_window.resizable(False, False)
        
        # Ana çerçeve
        main_frame = tk.Frame(info_window, bg='#f8f9fa', padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Başlık
        title_label = tk.Label(
            main_frame,
            text="🔗 zkSync Era Sepolia Blockchain",
            font=font.Font(family="Arial", size=16, weight="bold"),
            bg='#f8f9fa',
            fg='#2c3e50'
        )
        title_label.pack(pady=(0, 20))
        
        # Network bilgileri (Hybrid handler'dan türetilir)
        network_info = self._get_hybrid_network_info()
        if network_info:
            try:
                live_block = int(hybrid_blockchain_handler.web3.eth.block_number)
            except Exception:
                live_block = network_info.get('block_number')
            self.create_info_section(main_frame, "Network Bilgileri", [
                f"Network: {network_info['network_name']}",
                f"Chain ID: {network_info['chain_id']}",
                f"Block Number: #{live_block:,}",
                f"Admin Account: {network_info['admin_account']}",
                f"Bakiye: {network_info['balance']:.4f} {network_info['currency']}"
            ])
        else:
            self.create_info_section(main_frame, "Network Bilgileri", [
                "❌ Blockchain bağlantısı yok!",
                "Web3 modülü veya RPC bağlantısı kontrol edilmeli!"
            ])
        
        # Contract bilgileri (Hybrid handler deployment bilgisinden)
        contract_info = self._get_hybrid_contract_info()
        if contract_info and contract_info.get('pdm_address'):
            # Verifier adı belirle
            try:
                dep = getattr(hybrid_blockchain_handler, 'deployment_info', {}) or {}
                contracts = dep.get('contracts', {}) if isinstance(dep, dict) else {}
                verifier_name = 'UnifiedGroth16Verifier' if 'UnifiedGroth16Verifier' in contracts else 'OptimizedGroth16Verifier'
            except Exception:
                verifier_name = 'Groth16Verifier'
            contract_data = [
                f"PdMSystemHybrid: {contract_info['pdm_address']}",
                f"{verifier_name}: {contract_info['verifier_address']}",
                f"AccessControlRegistry: {contract_info.get('access_control_address', 'N/A')}",
                f"Deploy Zamanı: {contract_info['deployment_time']}",
                f"Durum: {contract_info['deployment_status']}"
            ]
            self.create_info_section(main_frame, "Contract Adresleri", contract_data)
            
            # Explorer linkleri
            self.create_explorer_links(main_frame, contract_info, network_info)
        else:
            self.create_info_section(main_frame, "Contract Bilgileri", [
                "⚠️ Contract'lar henüz deploy edilmemiş!",
                "Deploy scripti çalıştırılması gerekli!"
            ])
        
        # Sistem durumu
        status_data = []
        if BLOCKCHAIN_AVAILABLE:
            status_data.append("✅ Web3 modülü yüklü")
        else:
            status_data.append("❌ Web3 modülü yüklü değil!")
            
        if hybrid_blockchain_handler.web3:
            status_data.append("✅ RPC bağlantısı aktif")
        else:
            status_data.append("❌ RPC bağlantısı yok!")
            
        if hybrid_blockchain_handler.is_ready():
            status_data.append("✅ Contract'lar hazır")
        else:
            status_data.append("⚠️ Contract'lar yüklenmemiş!")
            
        self.create_info_section(main_frame, "Sistem Durumu", status_data)
        
        # Kapat butonu
        close_btn = tk.Button(
            main_frame,
            text="❌ Kapat",
            command=info_window.destroy,
            font=font.Font(family="Arial", size=10),
            bg='#e74c3c',
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        )
        close_btn.pack(pady=(20, 0))

    def create_info_section(self, parent, title, data_list):
        """Bilgi bölümü oluşturur"""
        
        # Bölüm çerçevesi
        section_frame = tk.Frame(parent, bg='white', relief='solid', bd=1)
        section_frame.pack(fill='x', pady=(0, 15))
        
        # Başlık
        title_label = tk.Label(
            section_frame,
            text=title,
            font=font.Font(family="Arial", size=12, weight="bold"),
            bg='#3498db',
            fg='white',
            pady=8
        )
        title_label.pack(fill='x')
        
        # Veri
        for item in data_list:
            data_label = tk.Label(
                section_frame,
                text=f"  {item}",
                font=font.Font(family="Arial", size=9),
                bg='white',
                fg='#2c3e50',
                anchor='w',
                pady=3
            )
            data_label.pack(fill='x')

    def create_explorer_links(self, parent, contract_info, network_info):
        """Explorer linkleri bölümü"""
        
        # Explorer bölümü
        explorer_frame = tk.Frame(parent, bg='white', relief='solid', bd=1)
        explorer_frame.pack(fill='x', pady=(0, 15))
        
        # Başlık
        title_label = tk.Label(
            explorer_frame,
            text="zkSync Explorer Linkleri",
            font=font.Font(family="Arial", size=12, weight="bold"),
            bg='#f39c12',
            fg='white',
            pady=8
        )
        title_label.pack(fill='x')
        
        # Buton çerçevesi
        button_frame = tk.Frame(explorer_frame, bg='white')
        button_frame.pack(fill='x', pady=10)
        
        # PDM Contract butonu
        if contract_info.get('pdm_address'):
            pdm_btn = tk.Button(
                button_frame,
                text="PDM Contract",
                command=lambda addr=contract_info['pdm_address']: self.open_explorer(addr),
                font=font.Font(family="Arial", size=9),
                bg='#3498db',
                fg='white',
                relief='flat',
                padx=10,
                pady=5,
                cursor='hand2'
            )
            pdm_btn.pack(fill='x', pady=2)
        
        # Verifier Contract butonu
        if contract_info.get('verifier_address'):
            verifier_btn = tk.Button(
                button_frame,
                text="Verifier Contract",
                command=lambda addr=contract_info['verifier_address']: self.open_explorer(addr),
                font=font.Font(family="Arial", size=9),
                bg='#9b59b6',
                fg='white',
                relief='flat',
                padx=10,
                pady=5,
                cursor='hand2'
            )
            verifier_btn.pack(fill='x', pady=2)
        
        # Admin Account butonu
        if network_info and network_info.get('admin_account'):
            account_btn = tk.Button(
                button_frame,
                text="Admin Account",
                command=lambda addr=network_info['admin_account']: self.open_explorer(addr),
                font=font.Font(family="Arial", size=9),
                bg='#27ae60',
                fg='white',
                relief='flat',
                padx=10,
                pady=5,
                cursor='hand2'
            )
            account_btn.pack(fill='x', pady=2)

    def open_explorer(self, address_or_hash):
        """Explorer'da adresi veya transaction hash'i açar"""
        if not address_or_hash or address_or_hash == 'Bulunamadı!':
            messagebox.showerror("Hata", "Geçerli bir Transaction Hash bulunamadı!")
            return
        
        address_or_hash_str = str(address_or_hash)

        # Eğer hash'in başında '0x' yoksa ve 64 karakterse, biz ekleyelim.
        if len(address_or_hash_str) == 64 and not address_or_hash_str.startswith('0x'):
            address_or_hash_str = "0x" + address_or_hash_str
            print(f"Hash formatı düzeltildi: {address_or_hash_str}")
        
        # TX hash formatını doğrula
        if len(address_or_hash_str) == 66 and address_or_hash_str.startswith('0x'):
            url_type = "tx"
            print(f"Geçerli TX hash tespit edildi: {address_or_hash_str}")
        elif len(address_or_hash_str) == 42 and address_or_hash_str.startswith('0x'):
            url_type = "address"
            print(f"Geçerli adres tespit edildi: {address_or_hash_str}")
        else:
            print(f"Geçersiz hash/adres formatı: {address_or_hash_str} (uzunluk: {len(address_or_hash_str)})")
            messagebox.showerror("Hata", f"Geçersiz hash formatı!\n\nAlınan: {address_or_hash_str}\nUzunluk: {len(address_or_hash_str)}\n\nBeklenen: 66 karakter TX hash (0x ile başlamalı)")
            return
        
        # EXPLORER_BASE_URL global değişkenini kullanarak dinamik URL oluştur
        url = f"{EXPLORER_BASE_URL}/{url_type}/{address_or_hash_str}"
        print(f"Explorer açılıyor: {url}")
        webbrowser.open(url)
    
    def open_explorer(self, address_or_hash):
        """zkSync Era Explorer'da adresi veya transaction hash'i açar"""
        if not address_or_hash or address_or_hash == 'Bulunamadı':
            messagebox.showerror("Hata", "Geçerli bir adres bulunamadı!")
            return
        
        address_or_hash_str = str(address_or_hash)

        # Eğer hash'in başında '0x' yoksa ve 64 karakterse, biz ekleyelim.
        if len(address_or_hash_str) == 64 and not address_or_hash_str.startswith('0x'):
            address_or_hash_str = "0x" + address_or_hash_str
            print(f"Adres formatı düzeltildi: {address_or_hash_str}")
        
        # Adres formatını doğrula
        if len(address_or_hash_str) == 66 and address_or_hash_str.startswith('0x'):
            url_type = "tx"
            print(f"TX hash tespit edildi: {address_or_hash_str}")
        elif len(address_or_hash_str) == 42 and address_or_hash_str.startswith('0x'):
            url_type = "address"
            print(f"Contract adresi tespit edildi: {address_or_hash_str}")
        else:
            print(f"Geçersiz adres formatı: {address_or_hash_str} (uzunluk: {len(address_or_hash_str)})")
            messagebox.showerror("Hata", f"Geçersiz adres formatı!\n\nAlınan: {address_or_hash_str}\nUzunluk: {len(address_or_hash_str)}\n\nBeklenen: 42 karakter adres (0x ile başlamalı)")
            return
        
        # zkSync Era Sepolia Explorer URL'si
        if url_type == "address":
            url = f"https://sepolia.explorer.zksync.io/address/{address_or_hash_str}"
        else:
            url = f"https://sepolia.explorer.zksync.io/tx/{address_or_hash_str}"
        
        print(f"🔍 zkSync Era Explorer açılıyor: {url}")
        webbrowser.open(url)

    def _get_hybrid_network_info(self):
        """HybridBlockchainHandler'dan ağ bilgisini türetir (uyum katmanı)."""
        try:
            stats = hybrid_blockchain_handler.get_system_statistics()
            if not isinstance(stats, dict):
                return None
            bc = stats.get('blockchain') or {}
            if not bc.get('connected'):
                return None
            web3_obj = getattr(hybrid_blockchain_handler, 'web3', None)
            try:
                chain_id = int(web3_obj.eth.chain_id) if web3_obj else None
            except Exception:
                chain_id = None
            try:
                block_number = int(web3_obj.eth.block_number) if web3_obj else None
            except Exception:
                block_number = None
            return {
                'network_name': bc.get('network') or NETWORK_NAME,
                'chain_id': chain_id,
                'block_number': block_number,
                'admin_account': bc.get('admin_account'),
                'balance': bc.get('balance'),
                'currency': 'ETH',
            }
        except Exception:
            return None

    def _get_hybrid_contract_info(self):
        """HybridBlockchainHandler'ın deployment bilgisinden sözleşme adreslerini çıkarır."""
        try:
            dep = getattr(hybrid_blockchain_handler, 'deployment_info', None)
            pdm_address = None
            verifier_address = None
            access_control_address = None

            # PDM adresini pdm_contract'tan ya da deployment_info'dan al
            try:
                pdm = getattr(hybrid_blockchain_handler, 'pdm_contract', None)
                if pdm and hasattr(pdm, 'address'):
                    pdm_address = pdm.address
            except Exception:
                pass
            if not pdm_address and isinstance(dep, dict):
                contracts = dep.get('contracts', {})
                pdm_address = (contracts.get('PdMSystemHybrid', {}) or {}).get('address')
                if not pdm_address:
                    # Eski ad anahtarları
                    pdm_address = dep.get('pdm_system_hybrid_address') or dep.get('pdm_system_address')

            # Verifier ve AccessControl adresleri
            if isinstance(dep, dict):
                contracts = dep.get('contracts', {})
                verifier_address = (contracts.get('UnifiedGroth16Verifier', {}) or contracts.get('OptimizedGroth16Verifier', {}) or {}).get('address')
                access_control_address = (contracts.get('AccessControlRegistry', {}) or {}).get('address')
            if not verifier_address:
                get_v = getattr(hybrid_blockchain_handler, '_get_verifier_contract', None)
                if callable(get_v):
                    try:
                        vc = get_v()
                        if vc and hasattr(vc, 'address'):
                            verifier_address = vc.address
                    except Exception:
                        pass

            deployment_time = 'Bilinmiyor'
            if isinstance(dep, dict):
                deployment_time = dep.get('deployment_time', 'Bilinmiyor')

            return {
                'pdm_address': pdm_address,
                'verifier_address': verifier_address,
                'access_control_address': access_control_address,
                'deployment_time': deployment_time,
                'deployment_status': 'Başarılı' if pdm_address else 'Bilinmiyor',
            }
        except Exception:
            return None

    def predict_failure(self):
        """Tahmin işlemini threading ile başlatır"""
        if self.is_processing: return messagebox.showwarning("Uyarı", "Zaten bir arıza analizi devam ediyor.")
        if model is None or scaler is None: return messagebox.showerror("Hata", "Sistem hazır değil. Model yüklenmemiş.")
        
        try:
            user_data = [self.sensor_vars[f].get() for f in ['Air temperature [K]', 'Process temperature [K]', 'Rotational speed [rpm]', 'Torque [Nm]', 'Tool wear [min]']]
            machine_type = self.machine_type.get()[0]
            user_data.extend([1 if machine_type == 'H' else 0, 1 if machine_type == 'L' else 0, 1 if machine_type == 'M' else 0])
        except Exception as e: return messagebox.showerror("Hata", f"Veri toplama hatası: {str(e)}")
        
        self.is_processing = True
        self.start_time = time.time()
        self.predict_button.config(state='disabled', text="⏳ İŞLEM DEVAM EDİYOR...")
        self.show_progress()
        
        thread = threading.Thread(target=self._predict_failure_worker, args=(user_data,))
        thread.daemon = True
        thread.start()
    
    def _predict_failure_worker(self, user_data):
        """Worker thread'de çalışan tahmin işlemi"""
        try:
            # --- 1. Veri Hazırlama ---
            data_prep_start = time.time()
            user_data_array = np.array(user_data).reshape(1, -1)

            self.result_queue.put({'type': 'progress', 'message': '🔍 Veriler ölçeklendiriliyor...'})
            user_data_scaled = scaler.transform(user_data_array)
            user_data_reshaped = user_data_scaled.reshape(1, user_data_scaled.shape[1], 1)
            data_prep_time = time.time() - data_prep_start

            # --- 2. Model Tahmini ---
            model_start = time.time()
            self.result_queue.put({'type': 'progress', 'message': '🤖 Model tahmini yapılıyor...'})
            prediction_prob = model.predict(user_data_reshaped, verbose=0)[0][0]

            model_prediction_05 = 1 if prediction_prob > 0.5 else 0
            model_prediction_opt = 1 if prediction_prob > optimal_threshold else 0
            model_time = time.time() - model_start

            # --- 3. Arıza Analizi ---
            analysis_start = time.time()
            self.result_queue.put({'type': 'progress', 'message': '🔍 Arıza tipi analizi yapılıyor...'})
            _, _, _, _, has_definite_failure = self.analyze_failure_type(user_data_array[0])
            analysis_time = time.time() - analysis_start

            # --- 4. Nihai Tahmin ---
            if has_definite_failure:
                final_prediction = 1
                prediction_reason = "Arıza Tipi Kuralları"
            else:
                final_prediction = model_prediction_opt
                prediction_reason = f"LSTM-CNN Model (Optimal Eşik: {optimal_threshold:.2f})"

            # --- 5. Hibrit Blockchain İşlemleri ---
            blockchain_success = False
            blockchain_result = {}
            blockchain_result_data = None
            data_id_from_bc = "N/A"
            blockchain_total_time = 0

            blockchain_start = time.time()
            self.result_queue.put({'type': 'progress', 'message': '🔗 Hibrit sisteme kaydediliyor...'})

            prediction_data = {
                "prediction": final_prediction,
                "probability": float(prediction_prob),
                "timestamp": int(time.time()),
                "air_temp": float(user_data_array[0][0]),
                "process_temp": float(user_data_array[0][1]),
                "rotation_speed": float(user_data_array[0][2]),
                "torque": float(user_data_array[0][3]),
                "tool_wear": float(user_data_array[0][4]),
                "machine_type": self.machine_type.get()[0]
            }

            # Handler hazır değilse yeniden başlatmayı dene ve sonucu doğrula
            if not hybrid_blockchain_handler.is_ready():
                # Dummy handler ise _initialize_blockchain yok, skip et
                if hasattr(hybrid_blockchain_handler, '_initialize_blockchain'):
                    ok = hybrid_blockchain_handler._initialize_blockchain()
                    if not ok or not hybrid_blockchain_handler.is_ready():
                        print("⚠️ Blockchain hazır değil, local devam ediliyor")
                else:
                    print("⚠️ Blockchain dependencies missing, local mode")
                
            try:
                # Dummy handler ise submit metodunu çağırma
                if hasattr(hybrid_blockchain_handler, 'submit_sensor_data_hybrid'):
                    blockchain_result = hybrid_blockchain_handler.submit_sensor_data_hybrid(prediction_data)
                else:
                    blockchain_result = {'success': False, 'error': 'Blockchain not available'}
                if not isinstance(blockchain_result, dict):
                    print(f"⚠️ Beklenmedik dönüş tipi: {type(blockchain_result)}")
                    blockchain_result = {"success": False, "error": "Unexpected return type"}

            except Exception as e:
                print(f"❌ HybridBlockchainHandler çağrılırken kritik hata: {e}")
                blockchain_result = {"success": False, "error": str(e)}

            # --- 6. Blockchain Sonuçlarını İşle ---
            if blockchain_result.get('success'):
                blockchain_success = bool(blockchain_result.get('blockchain_submitted'))
                blockchain_result_data = blockchain_result
                data_id_from_bc = blockchain_result.get('local_data_id', "N/A")
                
                # PdMDatabase'e de kaydet (database_viewer için)
                try:
                    pdm_record_data = {
                        'machine_id': prediction_data.get('machine_id'),
                        'timestamp': prediction_data.get('timestamp'),
                        'air_temp': prediction_data.get('air_temp'),
                        'process_temp': prediction_data.get('process_temp'),
                        'rotation_speed': prediction_data.get('rotation_speed'),
                        'torque': prediction_data.get('torque'),
                        'tool_wear': prediction_data.get('tool_wear'),
                        'machine_type': prediction_data.get('machine_type'),
                        'prediction': final_prediction,
                        'prediction_probability': prediction_prob,
                        'prediction_reason': prediction_reason,
                        'analysis_time': model_time,
                        'blockchain_success': blockchain_success,
                        'blockchain_tx_hash': blockchain_result.get('tx_hash')
                    }
                    pdm_db_id = pdm_db.save_sensor_data(pdm_record_data)
                    print(f"💾 PdMDatabase ID: {pdm_db_id} (database_viewer'da görünecek)")
                    # Bu ID'yi blockchain_result'a ekle
                    blockchain_result['pdm_db_id'] = pdm_db_id
                except Exception as pdm_err:
                    print(f"⚠️ PdMDatabase kayıt hatası: {pdm_err}")
                    blockchain_result['pdm_db_id'] = "N/A"
                # ⚙️ OPSIYON: Prediction'ı Local DB'de tut (Sensor proof zincirde yeterli)
                # Not: Eğer prediction proof'u da zincire göndermek isterseniz,
                # önce prediction verifier key'i contract'a upload etmeniz gerekiyor.
                
                # Tahmin sonucunu PdM DB'ye kaydet
                try:
                    import sqlite3
                    dh = blockchain_result.get('data_hash')
                    if dh and hasattr(pdm_db, 'db_path'):
                        conn = sqlite3.connect(str(pdm_db.db_path))
                        cur = conn.cursor()
                        cur.execute(
                            'UPDATE sensor_data SET prediction=?, prediction_probability=?, prediction_reason=? WHERE data_hash=? OR offchain_data_hash=?',
                            (int(final_prediction), float(prediction_prob), 'LSTM-CNN Model', str(dh), str(dh))
                        )
                        conn.commit()
                        conn.close()
                        print('💾 Prediction saved to PdM DB.')
                        print(f'   🎯 Prediction: {final_prediction}, Probability: {prediction_prob:.4f}')
                        print(f'   📊 Sensor proof on-chain, Prediction off-chain (optimal hybrid)')
                except Exception as pe2:
                    print(f"❌ PdM DB prediction save error: {pe2}")

                if blockchain_success:
                    self.result_queue.put({'type': 'progress', 'message': '✅ Hibrit kayıt tamamlandı (Local DB + Blockchain)'})
                else:
                    self.result_queue.put({'type': 'progress', 'message': '📊 Local DB\'ye kaydedildi (Blockchain offline)'})

                print(f"✅ Hibrit sisteme başarıyla kaydedildi!")
                print(f"📊 Local Data ID: {data_id_from_bc}")
                print(f"🔗 Data Hash: {blockchain_result.get('data_hash', 'N/A')}")
                print(f"💾 Storage: {blockchain_result.get('storage_location', 'N/A')}")
                if blockchain_success:
                    print(f"🔗 Blockchain TX: {blockchain_result.get('tx_hash', 'N/A')}")
                    print(f"📦 Block Number: {blockchain_result.get('block_number', 'N/A')}")
            else:
                error_msg = blockchain_result.get('error', 'Bilinmeyen hata')
                print(f"❌ Hibrit sistem kaydı başarısız: {error_msg}")
                self.result_queue.put({'type': 'progress', 'message': '❌ Hibrit sistem kaydı başarısız!'})

            blockchain_total_time = time.time() - blockchain_start

            # --- 7. İşlem Süre Analizi ---
            total_process_time = data_prep_time + model_time + analysis_time
            print(f"📊 İşlem Süre Analizi:")
            print(f"   🔍 Veri hazırlama: {data_prep_time:.3f} saniye")
            print(f"   🤖 Model tahmini: {model_time:.3f} saniye")
            print(f"   📋 Arıza analizi: {analysis_time:.3f} saniye")
            if blockchain_total_time > 0:
                print(f"   🔗 Blockchain: {blockchain_total_time:.3f} saniye")
            print(f"   ⚡ Toplam: {total_process_time + blockchain_total_time:.3f} saniye")

            # --- 7.1 PdM DB'ye tahmin detaylarını yaz (her durumda) ---
            try:
                dh = None
                if isinstance(blockchain_result, dict):
                    dh = blockchain_result.get('data_hash')
                if not dh and isinstance(blockchain_result_data, dict):
                    dh = blockchain_result_data.get('data_hash')
                if dh:
                    import sqlite3
                    total_time_store = float(total_process_time + blockchain_total_time)
                    conn = sqlite3.connect(str(pdm_db.db_path))
                    cur = conn.cursor()
                    cur.execute(
                        'UPDATE sensor_data SET prediction=?, prediction_probability=?, prediction_reason=?, analysis_time=? WHERE data_hash=? OR offchain_data_hash=?',
                        (int(final_prediction), float(prediction_prob), str(prediction_reason), total_time_store, str(dh), str(dh))
                    )
                    conn.commit()
                    conn.close()
            except Exception as upd_err:
                print(f"⚠️ PdM DB prediction update error: {upd_err}")

            # --- 8. Ana Thread'e Sonuç Döndür ---
            result = {
                'type': 'result',
                'final_prediction': final_prediction,
                'prediction_prob': float(prediction_prob),
                'user_data': user_data_array[0],
                'prediction_reason': prediction_reason,
                'model_prediction_05': model_prediction_05,
                'model_prediction_opt': model_prediction_opt,
                'blockchain_success': blockchain_success,
                'blockchain_tx_hashes': blockchain_result_data,
                'data_id': data_id_from_bc,
                'timestamp': int(time.time())
            }
            self.result_queue.put(result)

        except Exception as e:
            import traceback
            print(f"❌ _predict_failure_worker içinde beklenmedik hata: {e}")
            traceback.print_exc()
            self.result_queue.put({
                'type': 'error',
                'error': str(e),
                'user_data': user_data if not isinstance(user_data, list) else user_data[0]
            })
            
    def initialize_system(self):
        """Hibrit blockchain sistemini başlatır."""
        try:
            print(f"🔗 Hibrit PDM sistemi başlatılıyor...")
            
            # Hibrit blockchain handler'ı kontrol et
            if hybrid_blockchain_handler.is_ready():
                print(f"✅ Hibrit blockchain sistemi başarıyla başlatıldı!")
                print("📊 Off-chain storage: Local SQLite Database")
                print("🔐 On-chain proofs: ZK-SNARK kanıtları")
            else:
                print(f"⚠️ Blockchain bağlantısı yok - sadece local storage aktif")
                print("📊 Veriler local DB'de saklanacak, blockchain kanıtları yok")
                
        except Exception as e:
            print(f"❌ Sistem başlatma hatası: {e}")
            print("⚠️ Sistem local-only modda çalışacak")
    
    def analyze_failure_type(self, input_data):
        """Girilen verilere göre potansiyel arıza tipini analiz eder"""
        air_temp = input_data[0]
        process_temp = input_data[1] 
        rotational_speed = input_data[2]
        torque = input_data[3]
        tool_wear = input_data[4]
        machine_type = self.machine_type.get()[0]
        
        failure_risks = []
        has_definite_failure = False  # Kesin arıza var mı?
        
        # TWF - Tool Wear Failure (200+ dakika kesin arıza)
        if tool_wear >= 200:
            failure_risks.append(f"🔧 TWF (Takım Aşınması): {tool_wear:.0f} dk - Kritik seviye aşıldı")
            has_definite_failure = True
        elif tool_wear >= 150:
            # 150-200 arası uyarı seviyesi ama arıza değil
            failure_risks.append(f"⚠️ TWF Riski: {tool_wear:.0f} dk - Yakın takip gerekli (200+ kritik)")
        
        # HDF - Heat Dissipation Failure  
        temp_diff = process_temp - air_temp
        if temp_diff < 8.6 and rotational_speed < 1380:
            failure_risks.append("🌡️ HDF (Isı Dağılımı): Sıcaklık farkı <8.6K ve hız <1380rpm")
            has_definite_failure = True
        
        # PWF - Power Failure
        power = torque * (rotational_speed * 2 * 3.14159 / 60)  # Watt hesabı
        if power < 3500 or power > 9000:
            failure_risks.append(f"⚡ PWF (Güç): Güç {power:.0f}W (3500-9000W dışında)")
            has_definite_failure = True
        
        # OSF - Overstrain Failure
        overstrain_product = tool_wear * torque
        overstrain_limits = {'L': 11000, 'M': 12000, 'H': 13000}
        limit = overstrain_limits.get(machine_type, 12000)
        if overstrain_product > limit:
            failure_risks.append(f"💪 OSF (Aşırı Yük): {overstrain_product:.0f} > {limit} minNm")
            has_definite_failure = True
        
        return failure_risks, power, temp_diff, overstrain_product, has_definite_failure
    
    def show_prediction_result(self, result_data):
        """Tahmin sonuçlarını gösterir"""
        for widget in self.result_frame.winfo_children(): widget.destroy()
        
        prediction = result_data['final_prediction']
        probability = result_data['prediction_prob']
        total_time = result_data.get('total_time', 0)
        blockchain_success = result_data.get('blockchain_success', False)
        
        # TX hash'leri her işlemde yeniden al
        blockchain_tx_hashes = result_data.get('blockchain_tx_hashes', None)
        current_timestamp = result_data.get('timestamp', int(time.time()))
        
        print(f"🔄 GUI Güncelleniyor - Timestamp: {current_timestamp}")

        result_container = tk.Frame(self.result_frame, bg='#ecf0f1')
        result_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        result_color, result_text, result_icon = ('#e74c3c', " ARIZA TESPİTİ!", "🚨") if prediction == 1 else ('#27ae60', "ARIZA YOK!", "✅")
        
        tk.Label(result_container, text=f"{result_icon}{result_text}", font=('Arial', 18, 'bold'), bg=result_color, fg='white', pady=20).pack(fill='x', pady=(0, 10))
        
        if total_time > 0:
            # İşlem süresinin yanına eşik ve (model tahmini ise) olasılık bilgisini ekle
            try:
                info_text = f"⏱️ İşlem Süresi: {total_time:.2f} saniye  |  ⚖️ Eşik: %{optimal_threshold*100:.1f}"
                # Sadece LSTM-CNN model tahmini kullanıldıysa olasılığı göster
                pred_reason = str(result_data.get('prediction_reason',''))
                if 'LSTM-CNN' in pred_reason or 'Model' in pred_reason or isinstance(probability, (int, float)):
                    info_text += f"  |  🎯 Olasılık: %{(probability*100):.1f}"
            except Exception:
                info_text = f"⏱️ İşlem Süresi: {total_time:.2f} saniye"
            tk.Label(
                result_container,
                text=info_text,
                font=('Arial', 12, 'bold'),
                bg='#ecf0f1',
                fg='#3498db'
            ).pack(pady=10)
        
        # Arıza durumuna göre farklı analiz
        if prediction == 0:  # ARIZA YOK - Yakınlık analizi göster
            # Arızaya yakınlık analizi
            proximity_frame = tk.Frame(result_container, bg='#ecf0f1')
            proximity_frame.pack(fill='x', pady=10)
            
            # Yakınlık yüzdesi
            proximity_percent = probability * 100
            
            proximity_title = tk.Label(proximity_frame, 
                                     text="📊 ARIZA YAKINLIK ANALİZİ", 
                                     font=('Arial', 14, 'bold'), 
                                     fg='#2980b9',
                                     bg='#ecf0f1')
            proximity_title.pack(pady=(0, 10))
            
            # Yakınlık bilgileri
            proximity_info = f"""🎯 Arızaya Yakınlık: %{proximity_percent:.1f}
⚖️ Arıza Eşiği: %{optimal_threshold*100:.1f}"""
            
            proximity_label = tk.Label(proximity_frame, 
                                     text=proximity_info, 
                                     font=('Arial', 12), 
                                     fg='#2c3e50',
                                     bg='#ecf0f1',
                                     justify='left')
            proximity_label.pack()
            
            # Yakınlık gösterge çubuğu
            proximity_bar = ttk.Progressbar(proximity_frame, length=300, mode='determinate')
            proximity_bar['value'] = proximity_percent
            proximity_bar.pack(pady=10)
        
        # Öneriler
        advice_frame = tk.LabelFrame(result_container, 
                                    text="💡 ÖNERİLER", 
                                    font=('Arial', 11, 'bold'), 
                                    bg='#ecf0f1')
        advice_frame.pack(fill='x', pady=20)
        
        # Öneriler arıza durumuna göre
        if prediction == 1:  # ARIZA TESPİT EDİLDİ - Kontrol odaklı öneriler
            advice_text = """
🔍 KONTROL SÜRECİ
🔧 Makineyi kontrol edin ve durumu belirleyin
📋 Kontrol sonrası uygun aksiyonu belirleyin
⚠️ Güvenlik protokollerini unutmayın
🛠️ Gerekirse teknik ekibi çağırın
📊 Kontrol sonuçlarını kaydedin
            """.strip()
        else:  # ARIZA YOK - Yakınlık odaklı öneriler
            proximity_percent = probability * 100
            if proximity_percent > 30:
                advice_text = """
⚠️ ÖNLEYİCİ BAKIM ÖNERİLİR
🔧 Planlı bakım zamanlaması yapın
📅 1-2 hafta içinde kontrol edin
🛠️ Yedek parça durumunu gözden geçirin
📊 Parametreleri daha sık izleyin
                """.strip()
            elif proximity_percent > 20:
                advice_text = """
👀 NORMAL İZLEME
📅 Haftalık rutin kontrolleri sürdürün
🔍 Trend analizini takip edin
📊 Veri kayıtlarını düzenli tutun
🛠️ Planlı bakım takvimini koruyun
                """.strip()
            else:
                advice_text = """
💚 MÜKEMMEL DURUM
✅ Normal operasyona devam edin
📅 Rutin bakım planını sürdürün
📊 Periyodik veri kontrolü yapın
🔄 Mevcut ayarları koruyun
                """.strip()
        
        advice_label = tk.Label(advice_frame, 
                               text=advice_text, 
                               font=('Arial', 12, 'normal'), 
                               bg='#ecf0f1', 
                               justify='left')
        advice_label.pack(anchor='w', padx=10, pady=10)
        
        # Blockchain durumu çerçevesi
        blockchain_frame = tk.LabelFrame(result_container, text="🔗 BLOCKCHAIN DURUMU", font=('Arial', 11, 'bold'), bg='#ecf0f1')
        blockchain_frame.pack(fill='x', pady=10)
    
        info_frame = tk.Frame(blockchain_frame, bg='#ecf0f1')
        info_frame.pack(padx=10, pady=10, fill='x')

        # Blockchain işlemi başarılıysa kanıtları göster
        if blockchain_success and blockchain_tx_hashes:
            # Başarı mesajı
            success_text = "✅ zkSync Era'ya başarıyla kaydedildi!"
            tk.Label(info_frame, text=success_text, font=('Arial', 12, 'bold'), bg='#ecf0f1', fg='#27ae60', justify='left').pack(anchor='w')

            # 1. Off-Chain Veri Kanıtı (Data Hash) - Clickable info
            data_hash = blockchain_tx_hashes.get('data_hash', 'Bulunamadı')
            formatted_data_hash = f"{data_hash[:10]}...{data_hash[-10:]}" if isinstance(data_hash, str) and len(data_hash) > 20 else data_hash
            
            data_row = tk.Frame(info_frame, bg='#ecf0f1')
            data_row.pack(anchor='w', pady=(5, 0), fill='x')
            tk.Label(data_row,
                     text="📊 Off-Chain Veri Kanıtı:",
                     font=('Arial', 12),
                     bg='#ecf0f1', fg='#2c3e50').pack(side='left')
            
            # Data hash'i clickable yap - detaylı bilgi göster
            if data_hash and data_hash != 'Bulunamadı':
                data_hash_label = tk.Label(data_row,
                                           text=f" {formatted_data_hash}",
                                           font=('Arial', 12, 'underline'),
                                           bg='#ecf0f1', fg='#3498db', cursor='hand2', justify='left')
                data_hash_label.pack(side='left')
                # Tıklandığında detaylı bilgi göster
                def show_data_hash_info():
                    # PdMDatabase ID'yi göster (database_viewer'daki ID)
                    pdm_id = blockchain_tx_hashes.get('pdm_db_id', 'N/A')
                    storage_location = blockchain_tx_hashes.get('storage_location', 'N/A')
                    messagebox.showinfo(
                        "📊 Off-Chain Veri Kanıtı Detayları", 
                        f"🔐 Data Hash:\n{data_hash}\n\n"
                        f"💾 ID: {pdm_id}\n\n"
                        f"ℹ️ Bu hash değeri off-chain doğrulaması için kullanılmaktadır!\n"
                        f"Sensör verileri off-chain, ZK kanıtları ise on-chain tutulmaktadır!"
                    )
                data_hash_label.bind("<Button-1>", lambda _: show_data_hash_info())
            else:
                tk.Label(data_row,
                         text=f" {formatted_data_hash}",
                         font=('Arial', 12),
                         bg='#ecf0f1', fg='#566573', justify='left').pack(side='left')

            # 2. On-Chain Kanıt Transaction'ı (Proof TX Hash)
            proof_tx_hash = blockchain_tx_hashes.get('tx_hash', 'Bulunamadı')
            block_number = blockchain_tx_hashes.get('block_number', 'N/A')
            
            # TX Hash'i arayüzde kısaltarak göster
            formatted_proof_hash = f"{proof_tx_hash[:10]}...{proof_tx_hash[-10:]}" if len(proof_tx_hash) > 20 else proof_tx_hash
            
            # Yazı boyutlarını diğerleriyle aynı yap (12pt) ve linki sadece hash için uygula
            proof_row = tk.Frame(info_frame, bg='#ecf0f1')
            proof_row.pack(anchor='w', pady=(2, 0), fill='x')
            tk.Label(proof_row,
                     text="🔗 On-Chain Kanıt TX:",
                     font=('Arial', 12),
                     bg='#ecf0f1', fg='#2c3e50').pack(side='left')
            proof_hash_label = tk.Label(proof_row,
                                        text=f" {formatted_proof_hash}",
                                        font=('Arial', 12, 'underline'),
                                        bg='#ecf0f1', fg='#3498db', cursor='hand2', justify='left')
            proof_hash_label.pack(side='left')
            proof_hash_label.bind("<Button-1>", lambda _, h=proof_tx_hash: self.open_explorer(h))
            tk.Label(proof_row,
                     text=f"  (Blok: #{block_number})",
                     font=('Arial', 12),
                     bg='#ecf0f1', fg='#566573').pack(side='left')

        else:
            # Blockchain işlemi başarısızsa veya yapılmadıysa uyarı göster
            bc_text = "⚠️ Blockchain kaydı yapılmadı!\n Sadece local tahmin gerçekleştirildi!"
            tk.Label(info_frame, text=bc_text, font=('Arial', 12, 'normal'), bg='#ecf0f1', fg='#f39c12', justify='left').pack(anchor='w')

    def _create_calculated_value_label(self, parent, name, formula_text, result_text, unit, normal_range, text_formula, is_critical):
        """Hesaplanan değerler için biçimlendirilmiş bir satır oluşturur"""
        # Ana çerçeve
        main_frame = tk.Frame(parent, bg='#ecf0f1')
        main_frame.pack(fill='x', anchor='w', pady=4)
        
        # 1. Satır: Hesaplama
        calc_frame = tk.Frame(main_frame, bg='#ecf0f1')
        calc_frame.pack(fill='x', anchor='w')
    
        # Başlık (ikon olmadan)
        title_text = f"{name}:"
        tk.Label(calc_frame, text=title_text, font=('Arial', 12, 'bold'), bg='#ecf0f1').pack(side='left', anchor='w')
        
        # Formül
        tk.Label(calc_frame, text=formula_text, font=('Arial', 12, 'italic'), bg='#ecf0f1', fg='#566573').pack(side='left', anchor='w', padx=5)
    
        # Eşittir ve Sonuç
        result_color = '#e74c3c' if is_critical else '#2c3e50'
        tk.Label(calc_frame, text="=", font=('Arial', 12, 'bold'), bg='#ecf0f1').pack(side='left', anchor='w', padx=5)
        tk.Label(calc_frame, text=result_text, font=('Arial', 12, 'bold'), bg='#ecf0f1', fg=result_color).pack(side='left', anchor='w')
    
        # Birim ve Normal Aralık
        tk.Label(calc_frame, text=f"{unit} {normal_range}", font=('Arial', 10, 'normal'), bg='#ecf0f1', fg='#2c3e50').pack(side='left', anchor='w', padx=5)
    
        # 2. Satır: Metinsel Formül
        formula_label_frame = tk.Frame(main_frame, bg='#ecf0f1')
        formula_label_frame.pack(fill='x', anchor='w')
        
        tk.Label(formula_label_frame, text=text_formula, font=('Arial', 9, 'italic'), bg='#ecf0f1', fg='#7f8c8d').pack(side='left', anchor='w', padx=28)
    
       
    def show_failure_analysis(self, input_data):
        """Sol panelde arıza tipi analizini gösterir"""
        # Önceki analiz sonuçlarını temizle
        for widget in self.analysis_result_frame.winfo_children(): 
            widget.destroy()
    
        failure_risks, power, temp_diff, overstrain_product, has_definite_failure = self.analyze_failure_type(input_data)
    
        air_temp = input_data[0]
        process_temp = input_data[1] 
        rotational_speed = input_data[2]
        torque = input_data[3]
        tool_wear = input_data[4]
    
        # Kesin arıza durumu kontrolü
        definite_failures = [risk for risk in failure_risks if "Kritik seviye aşıldı" in risk or "HDF" in risk or "PWF" in risk or "OSF" in risk]
    
        if len(definite_failures) > 0:
            risk_text = "⚠️ Tespit Edilen Arıza Tipi:\n\n" + "\n".join([f"• {risk}" for risk in definite_failures])
        else:
            risk_text = "✅ Belirgin arıza tipi tespit edilmedi."
    
        risk_label = tk.Label(self.analysis_result_frame, text=risk_text, font=('Arial', 12, 'normal'), bg='#ecf0f1', justify='left', wraplength=500)
        risk_label.pack(anchor='w', pady=(0, 15))
    
        # Hesaplanan değerler için başlık
        tk.Label(self.analysis_result_frame, text="Hesaplanan Değerler:", font=('Arial', 12, 'bold'), bg='#ecf0f1', justify='left').pack(anchor='w', pady=(10, 5))

         # Takım Aşınması (TWF) Değerini Göster
        is_twf_critical = tool_wear >= FailureAnalysisConfig.TWF_CRITICAL_THRESHOLD
        self._create_calculated_value_label(
            parent=self.analysis_result_frame,
            name="Takım Aşınması (TWF)",
            formula_text=f"", # TWF doğrudan bir ölçüm olduğu için sayısal formülü yok
            result_text=f"{tool_wear:.0f}",
            unit="dk",
            normal_range=f"(Kritik: >{FailureAnalysisConfig.TWF_CRITICAL_THRESHOLD} dk)",
            text_formula="(Doğrudan sensör ölçümü)",
            is_critical=is_twf_critical
        )

        # Güç (Power) Değerini Göster
        is_power_critical = not (FailureAnalysisConfig.PWF_MIN_POWER <= power <= FailureAnalysisConfig.PWF_MAX_POWER)
        self._create_calculated_value_label(
            parent=self.analysis_result_frame,
            name="Güç Arızası (PWF)", 
            formula_text=f"{torque:.1f} Nm × {rotational_speed:.0f} rpm*",
            result_text=f"{power:.0f}",
            unit="W",
            normal_range=f"(Normal: {FailureAnalysisConfig.PWF_MIN_POWER}-{FailureAnalysisConfig.PWF_MAX_POWER}W)",
            text_formula="(Formül: Tork × Dönme Hızı (rad/s), 9000W < PWF < 3500W)", 
            is_critical=is_power_critical
        )
    
        # Sıcaklık Farkı Değerini Göster
        is_temp_critical = temp_diff < FailureAnalysisConfig.HDF_TEMP_DIFF_THRESHOLD
        self._create_calculated_value_label(
            parent=self.analysis_result_frame,
            name="Isı Dağılımı ve Proses Arızası (HDF)", 
            formula_text=f"{process_temp:.1f} K - {air_temp:.1f} K",
            result_text=f"{temp_diff:.1f}",
            unit="K",
            normal_range=f"(Normal: <{FailureAnalysisConfig.HDF_TEMP_DIFF_THRESHOLD}K)",
            text_formula="(Formül: (İşlem Sıcaklığı - Hava Sıcaklığı) < 8.6K ve Dönüş Hızı < 1380 rpm)", 
            is_critical=is_temp_critical
        )
    
        # Aşırı Yük Değerini Göster
        machine_type = self.machine_type.get()[0]
        limit = FailureAnalysisConfig.OSF_LIMITS.get(machine_type, 12000)
        is_overstrain_critical = overstrain_product > limit
        self._create_calculated_value_label(
            parent=self.analysis_result_frame,
            name="Aşırı Zorlama (OSF)", 
            formula_text=f"{torque:.1f} Nm × {tool_wear:.0f} dk",
            result_text=f"{overstrain_product:.0f}",
            unit="minNm",
            normal_range=f"(Limit: {limit:,})",
            text_formula="(Formül: (Tork × Takım Aşınması) < 11000 (L), 12000 (M), 13000 (H))", 
            is_critical=is_overstrain_critical
        )
        
    def set_random_data(self):
        """Rastgele sensör verileri oluşturur"""
        # Tam rastgele değerler - veri setindeki min/max aralıkları
        self.sensor_vars['Air temperature [K]'].set(round(np.random.uniform(295, 305), 1))
        self.sensor_vars['Process temperature [K]'].set(round(np.random.uniform(305, 315), 1))
        self.sensor_vars['Rotational speed [rpm]'].set(round(np.random.uniform(1000, 3000), 0))
        self.sensor_vars['Torque [Nm]'].set(round(np.random.uniform(3, 77), 1))
        self.sensor_vars['Tool wear [min]'].set(round(np.random.uniform(0, 300), 0))
        
    def reset_data(self):
        """Verileri varsayılan değerlere sıfırlar"""
        self.sensor_vars['Air temperature [K]'].set(298.1)
        self.sensor_vars['Process temperature [K]'].set(308.6)
        self.sensor_vars['Rotational speed [rpm]'].set(1551)
        self.sensor_vars['Torque [Nm]'].set(42.8)
        self.sensor_vars['Tool wear [min]'].set(0)
        self.machine_type.set("M (Medium - %30)")
        
        # Sonuç alanını temizle
        for widget in self.result_frame.winfo_children():
            widget.destroy()
            
        welcome_label = tk.Label(self.result_frame, 
                                text="👋 Arıza tespiti için sensör verilerini girin ve\n'ARIZA ANALİZİ YAP' butonuna tıklayın", 
                                font=self.label_font, 
                                bg='#ecf0f1', 
                                fg='#7f8c8d',
                                justify='center')
        welcome_label.pack(expand=True)
        
        # Analiz alanını da temizle
        for widget in self.analysis_result_frame.winfo_children():
            widget.destroy()
            
        analysis_welcome = tk.Label(self.analysis_result_frame, 
                                   text="📊 Arıza analizi yaptıktan sonra burada detaylı bilgiler görünecek", 
                                   font=('Arial', 12, 'normal'), 
                                   bg='#ecf0f1', 
                                   fg='#7f8c8d')
        analysis_welcome.pack(expand=True)
    
    def reload_contracts(self):
        """Kontrat adreslerini yeniden yükler"""
        try:
            print("🔄 Kontrat adresleri yeniden yükleniyor...")
            
            # Blockchain bağlantısını yeniden kur
            blockchain_ready = hybrid_blockchain_handler._initialize_blockchain()
            
            if blockchain_ready:
                messagebox.showinfo("Başarılı", "✅ Kontrat adresleri başarıyla yeniden yüklendi!\n\n🔗 Blockchain bağlantısı aktif\n📋 Yeni kontrat adresleri kullanılıyor")
                print("✅ Kontrat adresleri yeniden yüklendi")
            else:
                messagebox.showwarning("Uyarı", "⚠️ Blockchain bağlantısı kurulamadı!\n\n🔧 Lütfen:\n• .env dosyasını kontrol edin\n• Deployment dosyasını kontrol edin\n• Ağ bağlantısını kontrol edin")
                print("⚠️ Kontrat adresleri yeniden yüklenemedi")
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Kontrat yeniden yükleme hatası:\n{e}")
            print(f"❌ Reload hatası: {e}")
    
    def show_blockchain_stats(self):
        """Aktif Blockchain istatistiklerini gösterir"""
        if not BLOCKCHAIN_AVAILABLE:
            messagebox.showinfo("Bilgi", "⚠️ Blockchain entegrasyonu mevcut değil!\n\nWeb3 kütüphanesini kurmak için:\npip install web3")
            return
            
        try:
            # Blockchain bağlantısını kontrol et
            if not hybrid_blockchain_handler.web3:
                messagebox.showerror("Hata", f"❌ {NETWORK_NAME} bağlantısı kurulamadı!\n\nBlockchain sistemi başlatılmamış.")
                return
                
            # Popup pencere oluştur
            stats_window = tk.Toplevel(self.root)
            stats_window.title(f"🔗 {NETWORK_NAME} Blockchain İstatistikleri")
            stats_window.geometry("650x550")
            stats_window.configure(bg='white')
            
            # Başlık (Arıza Tespit Sistemi ile aynı arka plan)
            title_frame = tk.Frame(stats_window, bg='#2c3e50', height=60)
            title_frame.pack(fill='x', padx=0, pady=0)
            title_frame.pack_propagate(False)
            title_label = tk.Label(title_frame, 
                                  text=f"🔐 {NETWORK_NAME.upper()} BLOCKCHAIN İSTATİSTİKLERİ", 
                                  font=('Arial', 18, 'bold'), 
                                  bg='#2c3e50', 
                                  fg='white')
            title_label.pack(expand=True)
            
            # Network bilgileri frame
            network_frame = tk.LabelFrame(stats_window, 
                                        text="🌐 Network Bilgileri", 
                                        font=('Arial', 14, 'bold'), 
                                        bg='white', 
                                        fg='#2c3e50')
            network_frame.pack(fill='x', padx=20, pady=15)
            
            # Network bilgilerini al ve göster (blok numarası kaldırıldı)
            network_info = self._get_hybrid_network_info()
            if network_info:
                tk.Label(network_frame, 
                        text=f"🌐 Network: {network_info['network_name']} (Chain ID: {network_info['chain_id']})", 
                        font=('Arial', 12), bg='white', fg='#2c3e50').pack(anchor='w', padx=10, pady=5)
                
                if ACTIVE_NETWORK == "ARBITRUM":
                    tk.Label(network_frame, 
                            text="🚀 Layer 2: 1-3s işlem süresi, %99 daha düşük gas", 
                            font=('Arial', 12), bg='white', fg='#27ae60').pack(anchor='w', padx=10, pady=5)
                
                tk.Label(network_frame, 
                        text=f"👤 Admin Account: {network_info['admin_account']}", 
                            font=('Arial', 12), bg='white', fg='#2c3e50').pack(anchor='w', padx=10, pady=5)
                
                tk.Label(network_frame, 
                        text=f"💰 Bakiye: {network_info['balance']:.4f} {network_info['currency']}", 
                        font=('Arial', 12), bg='white', fg='#2c3e50').pack(anchor='w', padx=10, pady=5)
            
            # Contract bilgileri frame
            contract_frame = tk.LabelFrame(stats_window, 
                                         text="📋 Contract Bilgileri", 
                                    font=('Arial', 14, 'bold'), 
                                    bg='white', 
                                    fg='#2c3e50')
            contract_frame.pack(fill='x', padx=20, pady=15)
            
            contract_info = self._get_hybrid_contract_info()
            if contract_info and contract_info.get('pdm_address'):
                pdm_address = contract_info['pdm_address']
                verifier_address = contract_info['verifier_address']
                access_control_address = contract_info.get('access_control_address', '0xc07Fc05fF357A324A366e336386165A9bc9b9346')

                # PDM Contract - İsim siyah, sadece adres tıklanabilir
                pdm_row = tk.Frame(contract_frame, bg='white')
                pdm_row.pack(anchor='w', padx=10, pady=5)
                tk.Label(pdm_row, text="🏗️ PdMSystemHybrid: ", font=('Arial', 12), bg='white', fg='black').pack(side='left')
                pdm_address_label = tk.Label(pdm_row, text=pdm_address, font=('Arial', 12, 'underline'), bg='white', fg='#3498db', cursor="hand2")
                pdm_address_label.pack(side='left')
                pdm_address_label.bind("<Button-1>", lambda _, addr=pdm_address: self.open_explorer(addr))

                # Verifier Contract - İsim siyah, sadece adres tıklanabilir
                try:
                    dep = getattr(hybrid_blockchain_handler, 'deployment_info', {}) or {}
                    contracts = dep.get('contracts', {}) if isinstance(dep, dict) else {}
                    verifier_name = 'UnifiedGroth16Verifier' if 'UnifiedGroth16Verifier' in contracts else 'OptimizedGroth16Verifier'
                except Exception:
                    verifier_name = 'Groth16Verifier'
                verifier_row = tk.Frame(contract_frame, bg='white')
                verifier_row.pack(anchor='w', padx=10, pady=5)
                tk.Label(verifier_row, text=f"🔐 {verifier_name}: ", font=('Arial', 12), bg='white', fg='black').pack(side='left')
                verifier_address_label = tk.Label(verifier_row, text=verifier_address, font=('Arial', 12, 'underline'), bg='white', fg='#3498db', cursor="hand2")
                verifier_address_label.pack(side='left')
                verifier_address_label.bind("<Button-1>", lambda _, addr=verifier_address: self.open_explorer(addr))

                # AccessControl Contract - İsim siyah, sadece adres tıklanabilir
                access_row = tk.Frame(contract_frame, bg='white')
                access_row.pack(anchor='w', padx=10, pady=5)
                tk.Label(access_row, text="🔑 AccessControlRegistry: ", font=('Arial', 12), bg='white', fg='black').pack(side='left')
                access_address_label = tk.Label(access_row, text=access_control_address, font=('Arial', 12, 'underline'), bg='white', fg='#3498db', cursor="hand2")
                access_address_label.pack(side='left')
                access_address_label.bind("<Button-1>", lambda _, addr=access_control_address: self.open_explorer(addr))
            else:
                tk.Label(contract_frame, text="⚠️ Contract deployment bilgisi bulunamadı", font=('Arial', 12), bg='white', fg='#e67e22').pack(anchor='w', padx=10, pady=5)
            
            # Kapat butonu
            close_button = tk.Button(stats_window, 
                                    text="❌ Kapat", 
                                    command=stats_window.destroy,
                                    font=('Arial', 12, 'bold'), 
                                    bg='#e74c3c', 
                                    fg='white')
            close_button.pack(pady=20)
                
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Blockchain istatistikleri gösterilirken hata:\n{e}")

def main():
    """Modüler PDM sistemi ana entry point fonksiyonu.

    Tam sistem başlatma sürecini yönetir: zkSync Era blockchain bağlantısı kontrolü,
    LSTM-CNN model eğitimi, GUI arayüzü başlatma. zkSync Era blockchain
    entegrasyonu ile çalışır.

    Execution Flow:
        1. zkSync Era sistemi kontrolü ve bağlantı testi
        2. Model eğitim pipeline'ı çalıştırma  
        3. GUI uygulaması başlatma
        4. Event loop başlatma

    Environment Variables Used:
        - ZKSYNC_ERA_RPC_URL: zkSync Era RPC endpoint
        - Private_Key: Wallet private key

    Raises:
        Exception: Model eğitimi veya GUI başlatma hatası oluşursa.

    Note:
        Bu fonksiyon modüler yapıyı kullanır: training_utils, reporting,
        config modülleri ve BlockchainHandler sınıfı.

    Example:
        >>> if __name__ == "__main__":
        ...     main()
        🚀 Modüler Arıza Tespit Sistemi
        🔗 zkSync Era sistemi kontrol ediliyor...
        ✅ zkSync Era modülü hazır
    """
    print(f"🚀 Modüler Arıza Tespit Sistemi - {NETWORK_NAME} Entegrasyonlu")
    print("=" * 70)
    
    # Blockchain setup
    print(f"🔗 {NETWORK_NAME} sistemi kontrol ediliyor...")
    blockchain_ready = setup_blockchain()
    if blockchain_ready:
        print(f"✅ {NETWORK_NAME} modülü hazır")
        # zkSync Era avantajları
        print("⚡ zkSync Era Avantajları: <2s işlem + %99+ düşük gas + zkEVM!")
    else:
        print(f"⚠️ {NETWORK_NAME} modülü kapalı - sadece local mod aktif")
    
    print("📊 Modüler model eğitimi başlatılıyor, lütfen bekleyin...")
    
    # Modeli eğit
    try:
        success = train_model()
        if not success:
            print("❌ Model eğitimi başarısız!")
            return
    except Exception as e:
        print(f"❌ Model eğitimi hatası: {e}")
        return
    
    # Tam GUI arayüzünü başlat
    print("🖥️ GUI arayüzü başlatılıyor...")
    root = tk.Tk()
    app = PredictiveMaintenance(root)
    
    print("✅ Sistem hazır! GUI açılıyor...")
    print("🔗 Modüler yapı başarıyla çalışıyor!")
    print(f"🎯 LSTM-CNN Model eğitildi, GUI aktif!")
    
    # GUI'yi başlat
    root.mainloop()

if __name__ == "__main__":
    main() 
