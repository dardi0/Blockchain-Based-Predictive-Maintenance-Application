import sys
import logging
import warnings

# --- CONFIGURATION IMPORT ---
import config
from config import (
    FilePaths, ModelConfig, TrainingConfig, GUIConfig, 
    BlockchainConfig, VisualizationConfig, FailureAnalysisConfig,
    LogConfig, ConfigUtils, EnvConfig
)

# --- TensorFlow WARNING'LERİNİ BASTIR (Import öncesi) ---
LogConfig.suppress_all_tf_warnings()

# --- LOGGING KONFIGÜRASYONU (Blockchain debug logları için) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
# Blockchain handler loglarını göster
logging.getLogger('hybrid_blockchain_handler').setLevel(logging.INFO)
logging.getLogger('zk_proof_generator').setLevel(logging.INFO)

# Windows/Python UTF-8 konsol çıktısı (Türkçe karakterler için)
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# Konfigürasyondan warning ayarlarını al
for warning_type in LogConfig.SUPPRESS_WARNINGS:
    if warning_type == 'ignore':
        warnings.filterwarnings('ignore')
    else:
        warnings.filterwarnings('ignore', category=eval(warning_type))

import pandas as pd
import numpy as np
import pickle
import joblib
import tkinter as tk
from tkinter import ttk, messagebox, font
from dotenv import load_dotenv  
import webbrowser
import queue  
import time
import threading
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.models import load_model

# Blockchain entegrasyonu
try:
    from web3 import Web3
    from hybrid_blockchain_handler import HybridBlockchainHandler
    BLOCKCHAIN_AVAILABLE = True
    print("🔐 Hibrit Blockchain modülü yüklendi")
except ImportError as e:
    BLOCKCHAIN_AVAILABLE = False
    print(f"⚠️ Hibrit Blockchain modülü yüklenemedi: {e}")

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


# Ensure build directory exists (no-op if already exists)
try:
    ConfigUtils.create_build_directory()
except Exception:
    pass
# Global Değişkenler
model = None
scaler = None
feature_names = None
optimal_threshold = TrainingConfig.DEFAULT_THRESHOLD

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

def load_trained_model():
    """Eğitilmiş model ve scaler'ı yükler"""
    global model, scaler, feature_names, optimal_threshold
    
    print("🔄 Eğitilmiş model yükleniyor...")
    
    # Model dosyasını kontrol et
    if not MODEL_PATH.exists():
        print(f"❌ Model dosyası bulunamadı: {MODEL_PATH}")
        print("⚠️ Önce 'python pdm_main.py' ile modeli eğitmelisiniz!")
        return False
    
    # Scaler dosyasını kontrol et
    if not SCALER_PATH.exists():
        print(f"❌ Scaler dosyası bulunamadı: {SCALER_PATH}")
        print("⚠️ Önce 'python pdm_main.py' ile modeli eğitmelisiniz!")
        return False
    
    try:
        # Model yükle
        print(f"📂 Model yükleniyor: {MODEL_PATH}")
        model = load_model(MODEL_PATH, compile=False)
        print("✅ Model başarıyla yüklendi!")
        
        # Scaler yükle (joblib kullanarak - training_utils.py ile uyumlu)
        print(f"📂 Scaler yükleniyor: {SCALER_PATH}")
        scaler = joblib.load(SCALER_PATH)
        # Feature count guard from scaler
        scaler_features = getattr(scaler, 'n_features_in_', None)
        if scaler_features is None:
            scaler_features = getattr(scaler, 'n_features_', None)
        # Scaler tipini kontrol et ve doğrula
        print(f"🔍 Scaler tipi: {type(scaler)}")
        if not hasattr(scaler, 'transform'):
            print(f"⚠️ Scaler geçersiz tip! StandardScaler olmalı, {type(scaler)} bulundu")
            print("❌ Scaler dosyası bozuk! Lütfen modeli yeniden eğitin: python pdm_main.py")
            return False
        print("✅ Scaler başarıyla yüklendi!")
        
        # Model metadata yükle (optimal threshold dahil)
        metadata_path = MODEL_PATH.parent / 'model_metadata.pkl'
        if metadata_path.exists():
            print(f"📂 Model metadata yükleniyor: {metadata_path}")
            metadata = joblib.load(metadata_path)
            optimal_threshold = metadata.get('optimal_threshold', TrainingConfig.DEFAULT_THRESHOLD)
            feature_names = metadata.get('feature_names', [
                'Air temperature [K]',
                'Process temperature [K]',
                'Rotational speed [rpm]',
                'Torque [Nm]',
                'Tool wear [min]',
                'Type_H',
                'Type_L',
                'Type_M'
            ])
            # Feature count consistency check
            try:
                if scaler_features is not None and scaler_features != len(feature_names):
                    print(f"Feature count mismatch: scaler={scaler_features}, metadata={len(feature_names)}")
                    print("Please retrain the model: python pdm_main.py")
                    return False
            except Exception:
                pass
            print(f"✅ Metadata yüklendi!")
            print(f"   🎯 Optimal Threshold: {optimal_threshold:.3f}")
            print(f"   📅 Eğitim Tarihi: {metadata.get('training_date', 'Bilinmiyor')}")
        else:
            print(f"⚠️ Metadata dosyası bulunamadı, varsayılan değerler kullanılıyor")
            optimal_threshold = TrainingConfig.DEFAULT_THRESHOLD
            feature_names = [
                'Air temperature [K]',
                'Process temperature [K]',
                'Rotational speed [rpm]',
                'Torque [Nm]',
                'Tool wear [min]',
                'Type_H',
                'Type_L',
                'Type_M'
            ]
            # Metadata missing: still check scaler feature count
            try:
                expected = len(feature_names)
                if scaler_features is not None and scaler_features != expected:
                    print(f"Scaler feature count ({scaler_features}) does not match expected ({expected})")
                    print("Please retrain the model: python pdm_main.py")
                    return False
            except Exception:
                pass
            print(f"   ⚠️ Optimal Threshold: {optimal_threshold:.3f} (varsayılan)")
            print(f"   ℹ️ Doğru threshold için modeli yeniden eğitin: python pdm_main.py")
        
        # Model summary göster
        print("\n📊 Model Bilgileri:")
        model.summary()
        
        print(f"\n✅ Model hazır!")
        print(f"🎯 Optimal Threshold: {optimal_threshold:.3f}")
        print(f"📊 Feature Sayısı: {len(feature_names)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Model yükleme hatası: {e}")
        import traceback
        traceback.print_exc()
        return False

# PredictiveMaintenance sınıfını import et
# (Aynı GUI kodunu kullanıyoruz, sadece import ediyoruz)
import pdm_main
from pdm_main import PredictiveMaintenance

def main():
    """Sadece GUI'yi başlatır, model eğitimi yapmaz"""
    print(f"🚀 PDM Sistemi GUI - {NETWORK_NAME} Entegrasyonlu")
    print("=" * 70)
    
    # Blockchain setup
    print(f"🔗 {NETWORK_NAME} sistemi kontrol ediliyor...")
    blockchain_ready = setup_blockchain()
    if blockchain_ready:
        print(f"✅ {NETWORK_NAME} modülü hazır")
        print("⚡ zkSync Era Avantajları: <2s işlem + %99+ düşük gas + zkEVM!")
    else:
        print(f"⚠️ {NETWORK_NAME} modülü kapalı - sadece local mod aktif")
    
    # Eğitilmiş modeli yükle
    print("\n📊 Eğitilmiş model yükleniyor...")
    model_loaded = load_trained_model()
    
    if not model_loaded:
        print("\n❌ Model yüklenemedi!")
        print("⚠️ Önce modeli eğitmeniz gerekiyor:")
        print("   python pdm_main.py")
        return
    
    # Global değişkenleri pdm_main modülüne de aktar
    pdm_main.model = model
    pdm_main.scaler = scaler
    pdm_main.feature_names = feature_names
    pdm_main.optimal_threshold = optimal_threshold
    
    # Blockchain global değişkenlerini de aktar
    pdm_main.hybrid_blockchain_handler = hybrid_blockchain_handler
    pdm_main.pdm_db = pdm_db
    pdm_main.BLOCKCHAIN_AVAILABLE = BLOCKCHAIN_AVAILABLE
    pdm_main.EXPLORER_BASE_URL = EXPLORER_BASE_URL
    pdm_main.NETWORK_NAME = NETWORK_NAME
    pdm_main.CURRENT_RPC_URL = CURRENT_RPC_URL
    pdm_main.DEPLOYMENT_INFO_PATH = DEPLOYMENT_INFO_PATH
    pdm_main.ACTIVE_NETWORK = ACTIVE_NETWORK
    
    print(f"✅ Global değişkenler pdm_main modülüne aktarıldı")
    print(f"   • Model: {model is not None}")
    print(f"   • Scaler: {scaler is not None}")
    print(f"   • Optimal Threshold: {optimal_threshold:.3f}")
    print(f"   • Blockchain: {BLOCKCHAIN_AVAILABLE}")
    print(f"   • Network: {NETWORK_NAME}")
    print(f"   • Explorer: {EXPLORER_BASE_URL[:50]}..." if len(EXPLORER_BASE_URL) > 50 else f"   • Explorer: {EXPLORER_BASE_URL}")
    
    # GUI arayüzünü başlat
    print("\n🖥️ GUI arayüzü başlatılıyor...")
    root = tk.Tk()
    app = PredictiveMaintenance(root)
    
    print("\n✅ Sistem hazır! GUI açılıyor...")
    print("🎯 Eğitilmiş model yüklendi, GUI aktif!")
    print("⚡ Hızlı başlatma: Model eğitimi atlandı!")
    print("=" * 70)
    
    # GUI'yi başlat
    root.mainloop()

if __name__ == "__main__":
    main()


