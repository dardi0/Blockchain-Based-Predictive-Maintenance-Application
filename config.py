# -*- coding: utf-8 -*-
"""
🔧 PDM Sistemi - Konfigürasyon Dosyası
======================================
Bu dosya tüm sistem parametrelerini merkezi olarak yönetir.
Değişiklikler buradan yapılabilir, kod değişikliği gerektirmez.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Environment dosyasını hemen yükle (merkezi .env dosyası)
load_dotenv()  # Ana dizindeki .env dosyasını okur

# --- DOSYA YOLLARI ---
class FilePaths:
    """📁 Dosya yolları konfigürasyonu"""
    # Veri dosyaları
    DATASET_PATH = 'ai4i2020.csv'
    
    # Model dosyaları
    MODEL_DIR = Path("build")
    MODEL_PATH = MODEL_DIR / "model.h5"
    SCALER_PATH = MODEL_DIR / "scaler.joblib" 
    
    # Blockchain dosyaları
    DEPLOYMENT_INFO = Path("deployment_info_hybrid_ZKSYNC_ERA.json")
    
    # Contract artifacts
    PDM_ARTIFACTS_PATH = Path("artifacts-zk/contracts/PdMSystemHybrid.sol/PdMSystemHybrid.json")
    FAILURE_VERIFIER_ARTIFACTS_PATH = Path("artifacts-zk/contracts/OptimizedGroth16Verifier.sol/OptimizedGroth16Verifier.json")
    ACCESS_CONTROL_ARTIFACTS_PATH = Path("artifacts-zk/contracts/AccessControlRegistry.sol/AccessControlRegistry.json")

# --- MODEL PARAMETRELERİ ---
class ModelConfig:
    """🤖 LSTM-CNN Model konfigürasyonu"""
    # Model mimarisi 
    CNN_FILTERS_PER_LAYER = [128, 256]
    CNN_KERNEL_SIZE = 4
    CNN_POOL_SIZE = 2
    CNN_DROPOUT = 0.3
    CNN_ACTIVATION = 'relu'  
    
    LSTM_UNITS_PER_LAYER = [128, 256]
    LSTM_DROPOUT = 0.3
    
    DENSE_UNITS_PER_LAYER = [32, 64, 16]        
    DENSE_DROPOUT = 0.4
    DENSE_ACTIVATION = 'tanh'
    
    # Optimizasyon - ADAM
    LEARNING_RATE = 0.001  
    OPTIMIZER = 'adam'
    LOSS_FUNCTION = 'binary_crossentropy'

# --- EĞİTİM PARAMETRELERİ ---
class TrainingConfig:
    """📊 Model eğitimi konfigürasyonu"""
    # Cross Validation
    CV_SPLITS = 5
    CV_RANDOM_STATE = 42
    CV_SHUFFLE = True
    
    # Train/Test split
    TEST_SIZE = 0.2
    TRAIN_RANDOM_STATE = 42
    STRATIFY = True

    DROP_COLUMNS = ['UDI', 'Product ID', 'TWF', 'HDF', 'PWF', 'OSF', 'RNF']
    
    # Model eğitimi
    EPOCHS = 200
    FINAL_MODEL_EPOCHS = 500
    BATCH_SIZE = 64
    VALIDATION_SPLIT = 0.2
    
    # Early Stopping
    EARLY_STOPPING_MONITOR = 'val_loss'
    EARLY_STOPPING_PATIENCE = 80
    FINAL_MODEL_PATIENCE = 120
    EARLY_STOPPING_RESTORE_BEST = True
    
    # Threshold optimization
    DEFAULT_THRESHOLD = 0.5
    THRESHOLD_OPTIMIZATION_METHOD = 'f1'  # F1-Score maksimizasyonu ('f1', 'f_beta', 'recall_focused')
    F_BETA_VALUE = 2.0  # Sadece 'f_beta' yöntemi için kullanılır
    MIN_PRECISION_THRESHOLD = 0.2  # Minimum %20 precision korunarak recall maksimize edilir
    
    # SMOTE (Synthetic Minority Oversampling Technique)
    USE_SMOTE = True  # SMOTE kullanımını aktif/pasif eder
    SMOTE_RANDOM_STATE = 42  # SMOTE için random state
    SMOTE_K_NEIGHBORS = 5  # SMOTE k-neighbors parametresi
    

# --- GUI KONFİGÜRASYONU ---
class GUIConfig:
    """🖥️ Kullanıcı arayüzü konfigürasyonu"""
    # Ana pencere
    WINDOW_WIDTH = 1000
    WINDOW_HEIGHT = 700
    WINDOW_TITLE = "🔧 LSTM-CNN Arıza Tespit Sistemi"
    BACKGROUND_COLOR = '#f0f0f0'
    
    # Font ayarları
    TITLE_FONT_SIZE = 16
    LABEL_FONT_SIZE = 10
    BUTTON_FONT_SIZE = 12
    TITLE_FONT_WEIGHT = "bold"
    BUTTON_FONT_WEIGHT = "bold"
    
    # Renkler
    PRIMARY_COLOR = '#2c3e50'
    SECONDARY_COLOR = '#ecf0f1'
    SUCCESS_COLOR = '#27ae60'
    ERROR_COLOR = '#e74c3c'
    WARNING_COLOR = '#f39c12'
    INFO_COLOR = '#3498db'
    
    # Sensör varsayılan değerleri
    DEFAULT_AIR_TEMP = 0
    DEFAULT_PROCESS_TEMP = 0
    DEFAULT_ROTATION_SPEED = 0
    DEFAULT_TORQUE = 0
    DEFAULT_TOOL_WEAR = 0
    DEFAULT_MACHINE_TYPE = "M (Medium - %30)"
    
    # Sensör min/max aralıkları (AI4I2020)
    MIN_AIR_TEMP = 295.0
    MAX_AIR_TEMP = 305.0
    MIN_PROCESS_TEMP = 305.0
    MAX_PROCESS_TEMP = 315.0
    MIN_ROTATION_SPEED = 1000
    MAX_ROTATION_SPEED = 3000
    MIN_TORQUE = 3.0
    MAX_TORQUE = 77.0
    MIN_TOOL_WEAR = 0
    MAX_TOOL_WEAR = 300
    
    # Ek renkler
    TEXT_COLOR = '#2c3e50'
    
    # Threading
    QUEUE_CHECK_INTERVAL = 100  # ms

# --- BLOCKCHAIN KONFİGÜRASYONU ---
class BlockchainConfig:
    """🔗 Blockchain konfigürasyonu"""
    # Network ayarları
    DEFAULT_NETWORK = "ZKSYNC_ERA"
    
    # Gas ayarları
    SENSOR_DATA_GAS_LIMIT = 800000
    PREDICTION_GAS_LIMIT = 800000
    SENSOR_DATA_GAS_PRICE_GWEI = 0.25
    PREDICTION_GAS_PRICE_GWEI = 0.25
    
    # Transaction ayarları
    TRANSACTION_TIMEOUT = 120
    
    # Network bilgileri
    NETWORKS = {
        "ZKSYNC_ERA": {
            "name": "zkSync Era Sepolia",
            "currency": "ETH",
            "explorer": "https://sepolia.explorer.zksync.io",
            "type": "zkEVM Layer 2",
            "chain_id": 300,
            "rpc_url": "https://sepolia.era.zksync.dev",
            "advantages": [
                "İşlem süresi: <2 saniye",
                "Gas ücreti: %99+ daha düşük",
                "Throughput: 2000+ TPS",
                "zkEVM: Full Ethereum compatibility",
                "Account Abstraction: Gelişmiş wallet özellikleri"
            ]
        }
    }

# --- VİZUALİZASYON KONFİGÜRASYONU ---
class VisualizationConfig:
    """📈 Görselleştirme konfigürasyonu"""
    # Matplotlib ayarları
    FIGURE_SIZE_LOSS = (15, 6)
    FIGURE_SIZE_FOLD_PERFORMANCE = (12, 8)
    FIGURE_SIZE_CONFUSION_MATRIX = (10, 8)
    FIGURE_SIZE_CV_TEST_COMPARISON = (12, 8)
    FIGURE_SIZE_ROC_CURVE = (8, 6)
    FIGURE_SIZE_PR_CURVE = (8, 6)     # Precision-Recall Eğrisi
    
    # Renkler
    COLORS = {
        'accuracy': '#E74C3C',     # Kırmızı
        'f1': '#3498DB',           # Mavi
        'auc': '#1ABC9C',          # Turkuaz
        'precision': '#9B59B6',    # Mor
        'recall': '#F39C12',       # Turuncu
        'cv_mean': '#E67E22',      # Turuncu
        'test_result': '#2ECC71',  # Yeşil
        'roc_curve': '#8E44AD',    # Mor
        'pr_curve': '#E67E22',     # Turuncu (PR Eğrisi)
        'random_line': '#95A5A6'   # Gri
    }
    
    # Grafik ayarları
    LINE_WIDTH = 3
    MARKER_SIZE = 8
    GRID_ALPHA = 0.3
    LEGEND_FONT_SIZE = 12
    TITLE_FONT_SIZE = 16
    LABEL_FONT_SIZE = 14

    # Entropi analiz ayarları
    ENTROPY_HIGH_THRESHOLD = 0.8  # bit
    ENTROPY_TOP_N = 10            # listelenecek en yüksek entropili örnek sayısı

# --- ARIZA ANALİZ KONFİGÜRASYONU ---
class FailureAnalysisConfig:
    """🔍 Arıza analizi konfigürasyonu"""
    # Arıza eşikleri
    TWF_CRITICAL_THRESHOLD = 200  # dakika
    TWF_WARNING_THRESHOLD = 150   # dakika
    
    HDF_TEMP_DIFF_THRESHOLD = 8.6  # K
    HDF_ROTATION_THRESHOLD = 1380  # rpm
    
    PWF_MIN_POWER = 3500  # W
    PWF_MAX_POWER = 9000  # W
    
    # Overstrain limitleri (makine tipine göre)
    OSF_LIMITS = {
        'L': 11000,  # minNm
        'M': 12000,  # minNm
        'H': 13000   # minNm
    }
    
    # Fuzzy risk seviyeleri
    FUZZY_RISK_THRESHOLDS = {
        'MINIMAL': 0.05,
        'VERY_LOW': 0.2,
        'LOW': 0.4,
        'MEDIUM': 0.6,
        'HIGH': 0.8
    }

# --- LOG KONFİGÜRASYONU ---
class LogConfig:
    """📝 Loglama konfigürasyonu"""
    # TensorFlow log seviyesi
    TF_LOG_LEVEL = 'ERROR'
    
    # Python logging
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Hangi warning'leri gizleyelim
    SUPPRESS_WARNINGS = [
        'ignore',  # Tüm warning'ler
        'DeprecationWarning',
        'FutureWarning', 
        'UserWarning'
    ]
    
    # TensorFlow warning'lerini tamamen bastırma
    TF_CPP_MIN_LOG_LEVEL = '3'  # 0=INFO, 1=WARNING, 2=ERROR, 3=FATAL
    TF_AUTOTUNE_THRESHOLD = '3'
    
    @staticmethod
    def suppress_all_tf_warnings():
        """TensorFlow warning'lerini tamamen bastırır - import öncesi çağrılmalı"""
        import os
        
        # TensorFlow environment variables (import öncesi ayarlanmalı)
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = LogConfig.TF_CPP_MIN_LOG_LEVEL
        os.environ['TF_AUTOTUNE_THRESHOLD'] = LogConfig.TF_AUTOTUNE_THRESHOLD
        
        # CUDA warning'lerini bastır
        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # CPU only
        
        # Diğer TensorFlow warning'leri
        os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
        os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
    
    @staticmethod
    def suppress_tf_after_import():
        """TensorFlow import sonrası warning bastırma (TensorFlow 2.x uyumlu)"""
        try:
            import tensorflow as tf
            import logging
            
            # Modern TensorFlow 2.x logger ayarları
            tf.get_logger().setLevel('ERROR')
            
            # Python logging bastırma
            logging.getLogger('tensorflow').setLevel(logging.ERROR)
            logging.getLogger('tensorflow.python').setLevel(logging.ERROR)
            logging.getLogger('tensorflow.python.client').setLevel(logging.ERROR)
            
            # TensorFlow device ayarları
            tf.config.set_soft_device_placement(True)
            
        except ImportError:
            pass

# --- PERFORMANS KONFİGÜRASYONU ---
class PerformanceConfig:
    """⚡ Performans konfigürasyonu"""
    # Threading
    MAX_WORKER_THREADS = 4
    
    # Memory
    MEMORY_LIMIT_GB = 8
    
    # Processing
    BATCH_PROCESSING_SIZE = 1000
    
    # Caching
    ENABLE_CACHING = True
    CACHE_SIZE_MB = 500

# --- GÜVENLIK KONFİGÜRASYONU ---
class SecurityConfig:
    """🔐 Güvenlik konfigürasyonu"""
    # API rate limiting
    MAX_REQUESTS_PER_MINUTE = 60
    
    # Input validation
    MAX_INPUT_LENGTH = 1000
    ALLOWED_FILE_EXTENSIONS = ['.csv', '.json', '.h5']
    
    # Encryption
    HASH_ALGORITHM = 'sha256'
    
    # Session
    SESSION_TIMEOUT_MINUTES = 30

# --- ENVIRONMENT VARIABLES ---
class EnvConfig:
    """🌍 Environment değişkenleri"""
    @staticmethod
    def get_network():
        return "ZKSYNC_ERA"
    
    @staticmethod
    def get_zksync_era_rpc():
        return os.getenv("ZKSYNC_ERA_RPC_URL", "https://sepolia.era.zksync.dev")
    
    @staticmethod
    def get_PRIVATE_KEY():
        return os.getenv("PRIVATE_KEY")

# --- YARDıMCı FONKSİYONLAR ---
class ConfigUtils:
    """🛠️ Konfigürasyon yardımcı fonksiyonları"""
    
    @staticmethod
    def get_network_config(network_name=None):
        """zkSync Era network konfigürasyonunu döndürür"""
        return BlockchainConfig.NETWORKS.get("ZKSYNC_ERA")
    
    @staticmethod
    def get_deployment_info_path():
        """zkSync Era deployment dosya yolunu döndürür"""
        return FilePaths.DEPLOYMENT_INFO
    
    @staticmethod
    def get_current_rpc_url():
        """zkSync Era RPC URL'ini döndürür"""
        return EnvConfig.get_zksync_era_rpc()
    
    @staticmethod
    def create_build_directory():
        """Build klasörünü oluşturur"""
        FilePaths.MODEL_DIR.mkdir(exist_ok=True)
        return FilePaths.MODEL_DIR
    
    @staticmethod
    def validate_config():
        """Konfigürasyon doğrulaması yapar"""
        errors = []
        
        # Dosya varlığı kontrolü
        if not Path(FilePaths.DATASET_PATH).exists():
            errors.append(f"Dataset dosyası bulunamadı: {FilePaths.DATASET_PATH}")
        
        # Environment değişken kontrolü
        if not EnvConfig.get_PRIVATE_KEY():
            errors.append("Private_Key environment değişkeni eksik")
        
        # RPC URL kontrolü
        rpc_url = ConfigUtils.get_current_rpc_url()
        if not rpc_url:
            errors.append("zkSync Era RPC URL bulunamadı")
        
        # zkSync Era RPC kontrolü
        if not EnvConfig.get_zksync_era_rpc():
            errors.append("ZKSYNC_ERA_RPC_URL environment değişkeni eksik")
        
        return errors

# --- QUICK ACCESS ---
# Hızlı erişim için sık kullanılan değerler
DATASET_FILE = FilePaths.DATASET_PATH
MODEL_FILE = FilePaths.MODEL_PATH
LEARNING_RATE = ModelConfig.LEARNING_RATE
EPOCHS = TrainingConfig.EPOCHS
BATCH_SIZE = TrainingConfig.BATCH_SIZE
CV_SPLITS = TrainingConfig.CV_SPLITS
DEFAULT_THRESHOLD = TrainingConfig.DEFAULT_THRESHOLD

# Konfigürasyon doğrulaması
if __name__ == "__main__":
    # Test modu
    print("🔧 Konfigürasyon test ediliyor...")
    errors = ConfigUtils.validate_config()
    if errors:
        print("❌ Konfigürasyon hataları:")
        for error in errors:
            print(f"  • {error}")
    else:
        print("✅ Konfigürasyon geçerli!")
        
    print(f"\n📊 Aktif Konfigürasyon:")
    print(f"  • Dataset: {DATASET_FILE}")
    print(f"  • Network: {EnvConfig.get_network()}")
    print(f"  • Learning Rate: {LEARNING_RATE}")
    print(f"  • Epochs: {EPOCHS}")
    print(f"  • CV Splits: {CV_SPLITS}") 
