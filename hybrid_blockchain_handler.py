# -*- coding: utf-8 -*-
"""
Hibrit Blockchain Handler - Off-chain storage + ZK-SNARK proofs
Local DB'de veri saklama, blockchain'de sadece kanıtlar
"""

import json
import sqlite3
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
import sys
import warnings

# Windows konsollarında UTF-8/emoji yazdırma sorunlarını engelle
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# web3 bağımlılığının tetiklediği websockets.legacy uyarılarını sustur
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=r".*websockets\.legacy is deprecated.*"
)
from web3 import Web3

# Import components
from hybrid_storage_manager import LocalStorageManager, SensorData, PredictionData, MaintenanceData
from zk_proof_generator import ZKProofGenerator
import config
from config import BlockchainConfig, ConfigUtils

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

# Yeni ekleme
try:
    from database_manager import PdMDatabaseManager
except ImportError:
    PdMDatabaseManager = None


class _DBAdapter:
    """
    Adapter: PdMDatabaseManager varsa onu, yoksa LocalStorageManager kullan.
    Tek bir interface üzerinden store, get ve istatistik işlemleri yapılır.
    """
    def __init__(self, pdm_db=None, local_storage=None):
        self.pdm_db = pdm_db
        self.local = local_storage

    # --- Store Metodları ---
    def store_sensor_data(self, sensor_data):
        # Her durumda local'e yaz (ZK kanıt akışı bu DB'yi kullanıyor)
        local_result = self.local.store_sensor_data(sensor_data) if hasattr(self.local, "store_sensor_data") else (None, None)
        local_id, data_hash = local_result if isinstance(local_result, tuple) else (None, None)

        # PdM DB varsa aynı kaydı oraya da yansıt
        try:
            if self.pdm_db:
                # PdM şemasına uygun dict hazırla
                rec = {
                    'machine_id': int(getattr(sensor_data, 'machine_id', 0) or 0),
                    'timestamp': int(getattr(sensor_data, 'timestamp', int(time.time())) or int(time.time())),
                    'air_temp': float(getattr(sensor_data, 'air_temperature', 0.0) or 0.0),
                    'process_temp': float(getattr(sensor_data, 'process_temperature', 0.0) or 0.0),
                    'rotation_speed': int(getattr(sensor_data, 'rotational_speed', 0) or 0),
                    'torque': float(getattr(sensor_data, 'torque', 0.0) or 0.0),
                    'tool_wear': int(getattr(sensor_data, 'tool_wear', 0) or 0),
                    'machine_type': str(getattr(sensor_data, 'machine_type', 'M') or 'M'),
                    'prediction': None,
                    'prediction_probability': None,
                    'prediction_reason': None,
                    'analysis_time': None,
                    'blockchain_success': False,
                    'blockchain_tx_hash': None,
                }
                # Kayıt ekle
                if hasattr(self.pdm_db, 'save_sensor_data'):
                    pdm_id = self.pdm_db.save_sensor_data(rec)
                    # data_hash sütununu güncelle (eşleştirme için)
                    try:
                        db_path = getattr(self.pdm_db, 'db_path', None)
                        if db_path and data_hash:
                            conn = sqlite3.connect(str(db_path))
                            cur = conn.cursor()
                            cur.execute('UPDATE sensor_data SET data_hash=?, offchain_data_hash=? WHERE id=?', (str(data_hash), str(data_hash), int(pdm_id)))
                            conn.commit()
                            conn.close()
                    except Exception:
                        pass
        except Exception:
            pass

        return local_id, data_hash

    def store_prediction_data(self, prediction_data):
        # Önce local prediction_data tablosuna yaz (mevcut akış bunu bekliyor)
        pred_result = self.local.store_prediction_data(prediction_data) if hasattr(self.local, 'store_prediction_data') else (None, None)
        pred_id, pred_hash = pred_result if isinstance(pred_result, tuple) else (None, None)

        # PdM DB'deki sensor_data satırını tahmin bilgileriyle güncelle
        try:
            if self.pdm_db:
                # Local sensor kaydından data_hash'i bul
                data_id = getattr(prediction_data, 'data_id', None)
                data_hash_val = None
                try:
                    # local sqlite'tan çek
                    ldb_path = getattr(self.local, 'db_path', None)
                    if ldb_path and data_id:
                        conn_l = sqlite3.connect(str(ldb_path))
                        cur_l = conn_l.cursor()
                        cur_l.execute('SELECT data_hash FROM sensor_data WHERE id=?', (int(data_id),))
                        row = cur_l.fetchone()
                        conn_l.close()
                        if row and row[0]:
                            data_hash_val = str(row[0])
                except Exception:
                    pass

                if data_hash_val:
                    try:
                        db_path = getattr(self.pdm_db, 'db_path', None)
                        if db_path:
                            conn = sqlite3.connect(str(db_path))
                            cur = conn.cursor()
                            # prediction_reason alanı şemada var; basit bir açıklama yaz
                            pr = int(getattr(prediction_data, 'prediction', 0) or 0)
                            pp = float(getattr(prediction_data, 'probability', 0.0) or 0.0)
                            cur.execute(
                                'UPDATE sensor_data SET prediction=?, prediction_probability=?, prediction_reason=? WHERE data_hash=?',
                                (pr, pp, 'LSTM-CNN Model', data_hash_val)
                            )
                            conn.commit()
                            conn.close()
                    except Exception:
                        pass
        except Exception:
            pass

        return pred_id, pred_hash

    def store_maintenance_data(self, maintenance_data):
        if self.pdm_db and hasattr(self.pdm_db, "store_maintenance_data"):
            return self.pdm_db.store_maintenance_data(maintenance_data)
        return self.local.store_maintenance_data(maintenance_data)

    # --- Update Blockchain Info ---
    def update_blockchain_proof_id(self, table_name, local_id, proof_id, tx_hash=None):
        if self.pdm_db and hasattr(self.pdm_db, "update_blockchain_info"):
            try:
                return self.pdm_db.update_blockchain_info(
                record_id=local_id,
                success=True,
                    tx_hash=tx_hash,
                proof_id=proof_id
            )
            except Exception:
                pass
            
            # Doğrudan SQLite üzerinden güncelle
            try:
                db_path = getattr(self.pdm_db, 'db_path', None)
                if db_path is not None:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(sensor_data)")
                    cols = {row[1] for row in cursor.fetchall()}
                    set_parts = []
                    params = []
                    if 'blockchain_success' in cols:
                        set_parts.append("blockchain_success = ?")
                        params.append(1)
                    if tx_hash:
                        if 'blockchain_tx_hash' in cols:
                            set_parts.append("blockchain_tx_hash = ?")
                            params.append(tx_hash)
                        if 'tx_hash' in cols:
                            set_parts.append("tx_hash = ?")
                            params.append(tx_hash)
                    if set_parts:
                        params.append(local_id)
                        sql = f"UPDATE sensor_data SET {', '.join(set_parts)} WHERE id = ?"
                        cursor.execute(sql, params)
                    conn.commit()
                    conn.close()
                    return True
            except Exception:
                pass
        if self.local and hasattr(self.local, "update_blockchain_proof_id"):
            return self.local.update_blockchain_proof_id(table_name, local_id, proof_id, tx_hash)
        return None

    def update_blockchain_info(
        self,
        record_id,
        success,
        tx_hash=None,
        proof_id=None,
        zk_proof_hash=None,
        table_name="sensor_data",
    ):
        # 'N/A' benzeri değerleri None'a çevir
        if isinstance(zk_proof_hash, str) and zk_proof_hash.strip().upper() in {"N/A", "NA", "NONE", "NULL", ""}:
            zk_proof_hash = None
        if self.pdm_db and hasattr(self.pdm_db, "update_blockchain_info"):
            try:
                return self.pdm_db.update_blockchain_info(
                    record_id=record_id,
                    success=success,
                    tx_hash=tx_hash,
                    proof_id=proof_id,
                    offchain_hash=zk_proof_hash
                )
            except Exception as e:
                # PdMDatabaseManager'da conn/şema uyuşmazlığı varsa doğrudan SQLite ile güncelle
                try:
                    db_path = getattr(self.pdm_db, 'db_path', None)
                    if db_path is not None:
                        conn = sqlite3.connect(str(db_path))
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(sensor_data)")
                        cols = {row[1] for row in cursor.fetchall()}
                        set_parts = []
                        params = []
                        if 'blockchain_success' in cols:
                            set_parts.append("blockchain_success = ?")
                            params.append(1 if success else 0)
                        if tx_hash:
                            if 'blockchain_tx_hash' in cols:
                                set_parts.append("blockchain_tx_hash = ?")
                                params.append(tx_hash)
                            if 'tx_hash' in cols:
                                set_parts.append("tx_hash = ?")
                                params.append(tx_hash)
                        if zk_proof_hash:
                            if 'zk_proof_hash' in cols:
                                set_parts.append("zk_proof_hash = ?")
                                params.append(zk_proof_hash)
                            if 'offchain_data_hash' in cols:
                                set_parts.append("offchain_data_hash = ?")
                                params.append(zk_proof_hash)
                        if set_parts:
                            params.append(record_id)
                            sql = f"UPDATE sensor_data SET {', '.join(set_parts)} WHERE id = ?"
                            cursor.execute(sql, params)
                            conn.commit()
                        conn.close()
                        return True
                except Exception:
                    pass
        if self.local and hasattr(self.local, "update_blockchain_proof_id"):
            return self.local.update_blockchain_proof_id(table_name, record_id, proof_id, tx_hash)
        return None


    # --- Get Metodları ---
    def get_sensor_data(self, data_id):
        """ID ile sensör verisini getir. PdM DB boş/None dönerse local'e düş."""
        result = None
        if self.pdm_db and hasattr(self.pdm_db, "get_sensor_data"):
            try:
                result = self.pdm_db.get_sensor_data(record_id=data_id)
                # PdM DB'de yoksa local'e düş
                if (isinstance(result, list) and not result) or result is None:
                    result = None
            except Exception:
                result = None
        if result is None and self.local and hasattr(self.local, "get_sensor_data"):
            result = self.local.get_sensor_data(data_id)
        # Liste dönerse ilk elemanı ver
        if isinstance(result, list):
            return result[0] if result else None
        return result

    def get_sensor_data_by_hash(self, data_hash: str):
        result = None
        if self.pdm_db and hasattr(self.pdm_db, "get_sensor_data_by_hash"):
            try:
                result = self.pdm_db.get_sensor_data_by_hash(data_hash)
                if (isinstance(result, list) and not result) or result is None:
                    result = None
            except Exception:
                result = None
        if result is None and self.local and hasattr(self.local, "get_sensor_data_by_hash"):
            result = self.local.get_sensor_data_by_hash(data_hash)
        if isinstance(result, list):
            return result[0] if result else None
        return result

    # -- Yeni: PdM dict -> SensorData dönüştürücü yardımcılar --
    def get_sensor_data_obj(self, data_id):
        """ID ile sensör verisini getir ve SensorData döndür (PdM dict â†’ dataclass)."""
        # Önce PdM DB
        if self.pdm_db and hasattr(self.pdm_db, "get_sensor_data"):
            try:
                res_list = self.pdm_db.get_sensor_data(record_id=data_id)
                if isinstance(res_list, list) and res_list:
                    row = res_list[0]
                    if isinstance(row, dict):
                        return SensorData(
                            data_id=row.get('id') or row.get('data_id'),
                            machine_id=row.get('machine_id'),
                            air_temperature=row.get('air_temp') or row.get('air_temperature'),
                            process_temperature=row.get('process_temp') or row.get('process_temperature'),
                            rotational_speed=row.get('rotation_speed') or row.get('rotational_speed'),
                            torque=row.get('torque'),
                            tool_wear=row.get('tool_wear'),
                            machine_type=row.get('machine_type'),
                            timestamp=row.get('timestamp'),
                            submitter="",
                        )
                    return row
            except Exception:
                pass
        # Sonra local
        if self.local and hasattr(self.local, "get_sensor_data"):
            return self.local.get_sensor_data(data_id)
        return None

    def get_sensor_data_by_hash_obj(self, data_hash: str):
        """Hash ile sensör verisini getir ve SensorData döndür (PdM dict â†’ dataclass)."""
        if self.pdm_db and hasattr(self.pdm_db, "get_sensor_data_by_hash"):
            try:
                row = self.pdm_db.get_sensor_data_by_hash(data_hash)
                if isinstance(row, dict):
                    return SensorData(
                        data_id=row.get('id') or row.get('data_id'),
                        machine_id=row.get('machine_id'),
                        air_temperature=row.get('air_temp') or row.get('air_temperature'),
                        process_temperature=row.get('process_temp') or row.get('process_temperature'),
                        rotational_speed=row.get('rotation_speed') or row.get('rotational_speed'),
                        torque=row.get('torque'),
                        tool_wear=row.get('tool_wear'),
                        machine_type=row.get('machine_type'),
                        timestamp=row.get('timestamp'),
                        submitter="",
                    )
                if isinstance(row, list):
                    row = row[0] if row else None
                if row is not None:
                    return row
            except Exception:
                pass
        if self.local and hasattr(self.local, "get_sensor_data_by_hash"):
            return self.local.get_sensor_data_by_hash(data_hash)
        return None

    def get_prediction_data(self, pred_id):
        result = None
        if self.pdm_db and hasattr(self.pdm_db, "get_prediction_data"):
            result = self.pdm_db.get_prediction_data(pred_id)
        elif self.local and hasattr(self.local, "get_prediction_data"):
            result = self.local.get_prediction_data(pred_id)
        if isinstance(result, list):
            return result[0] if result else None
        return result

    # --- Statistics ---
    def get_statistics(self):
        """Local ve PdM DB istatistiklerini döndür"""
        stats = {}
        if self.pdm_db and hasattr(self.pdm_db, "get_statistics"):
            stats = self.pdm_db.get_statistics()
        elif self.local and hasattr(self.local, "get_statistics"):
            stats = self.local.get_statistics()
        else:
            stats = {
                'sensor_data_count': 0,
                'prediction_data_count': 0,
                'maintenance_data_count': 0
            }
        return stats

class HybridBlockchainHandler:
    """
    Hibrit blockchain handler - Off-chain storage + On-chain proofs
    """
    
    def __init__(self, db_manager=None):
        # LocalStorage fallback
        self.local_storage = LocalStorageManager("pdm_hybrid_storage.db")

        # PdM DB (eğer dışarıdan verilmişse onu, yoksa kendisi oluşturur)
        self.pdm_db = db_manager if db_manager is not None else (
            PdMDatabaseManager() if PdMDatabaseManager else None
        )

        # Tek noktadan erişim: adapter
        self.storage_manager = _DBAdapter(
            pdm_db=self.pdm_db,
            local_storage=self.local_storage
        )

        self.zk_proof_generator = ZKProofGenerator()
        # Blockchain bağlantısı
        self.web3 = None
        self.pdm_contract = None
        self.admin_account = None
        self.private_key = None
        self.rpc_url = None
        self.network_name = None
        self.deployment_info = None
        self._verifier_contract = None
        self._sensor_vk_ready = False
        self._sensor_vk_warned = False
        self._no_window_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        # Initialize blockchain if available
        self._initialize_blockchain()

    def _extract_proof_id_from_receipt(self, receipt) -> int:
        """Tx receipt içinden proofId'yi olaylardan ayıkla.
        Hem SensorDataProofSubmitted hem PredictionProofSubmitted olaylarını dener.
        """
        try:
            if not self.pdm_contract:
                return 0
            # Önce Prediction
            try:
                evs = self.pdm_contract.events.PredictionProofSubmitted().process_receipt(receipt)
                for e in evs:
                    args = getattr(e, 'args', {}) or {}
                    pid = int(args.get('proofId') or args.get('proofID') or 0)
                    if pid:
                        return pid
            except Exception:
                pass
            # Sonra Sensor
            try:
                evs = self.pdm_contract.events.SensorDataProofSubmitted().process_receipt(receipt)
                for e in evs:
                    args = getattr(e, 'args', {}) or {}
                    pid = int(args.get('proofId') or args.get('proofID') or 0)
                    if pid:
                        return pid
            except Exception:
                pass
        except Exception:
            return 0
        return 0
    
    def _normalize_private_key(self) -> Optional[str]:
        """Env'den gelen private key'i güvenli biçime getir (0x + 64 hex)."""
        try:
            # Birden çok olası kaynak adı destekle
            pk = None
            if hasattr(config.EnvConfig, 'get_PRIVATE_KEY'):
                pk = config.EnvConfig.get_PRIVATE_KEY()
            if not pk and hasattr(config.EnvConfig, 'get_private_key'):
                pk = config.EnvConfig.get_private_key()
            if not pk:
                import os
                pk = os.getenv('Private_Key') or os.getenv('PRIVATE_KEY')
            if not pk:
                return None

            pk = pk.strip().strip('"').strip("'").replace(' ', '')
            hex_part = pk[2:] if pk.lower().startswith('0x') else pk
            import re
            if not re.fullmatch(r'[0-9a-fA-F]{64}', hex_part or ''):
                logger.error("❌ Invalid PRIVATE_KEY format (expected 64 hex chars)")
                return None
            return '0x' + hex_part.lower()
        except Exception:
            return None

    def _initialize_blockchain(self):
        """Blockchain bağlantısını kur"""
        try:
            # Config'ten bilgileri al
            self.private_key = self._normalize_private_key()
            self.rpc_url = ConfigUtils.get_current_rpc_url()
            self.network_name = ConfigUtils.get_network_config()['name']
            
            if not all([self.rpc_url, self.private_key]):
                logger.warning("⚠️ Blockchain config incomplete - running in local-only mode")
                return False
            
            # Web3 bağlantısı
            try:
                self.web3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={'timeout': 30}))
            except TypeError:
                self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if not self.web3.is_connected():
                logger.error(f"❌ Cannot connect to {self.network_name}")
                return False
            
            # Account setup
            account = self.web3.eth.account.from_key(self.private_key)
            self.admin_account = account.address
            balance = self.web3.from_wei(self.web3.eth.get_balance(self.admin_account), 'ether')
            
            # logger.info(f"✅ {self.network_name} connected!")
            # logger.info(f"👤 Account: {self.admin_account}")
            # logger.info(f"💰 Balance: {balance:.4f} ETH")
            
            # Contract'ı yükle
            try:
                onchain_chain_id = int(self.web3.eth.chain_id)
                cfg = ConfigUtils.get_network_config()
                expected_chain_id = int(cfg.get('chain_id', onchain_chain_id)) if isinstance(cfg, dict) else onchain_chain_id
                if onchain_chain_id != expected_chain_id:
                    logger.error(f"Chain ID mismatch: on-chain={onchain_chain_id}, expected={expected_chain_id}")
                    return False
            except Exception as e:
                logger.warning(f"Could not validate chain id: {e}")
            return self._load_hybrid_contract()
            
        except Exception as e:
            logger.error(f"❌ Blockchain initialization error: {e}")
            return False
    
    def _load_hybrid_contract(self):
        """Hibrit PDM contract'ını yükle"""
        try:
            # Deployment info dosyası
            deployment_path = ConfigUtils.get_deployment_info_path()
            if not deployment_path.exists():
                logger.warning("⚠️ No deployment info found - contracts not deployed")
                return False
            
            # Deployment bilgilerini yükle
            with open(deployment_path) as f:
                self.deployment_info = json.load(f)
            
            # Hybrid contract artifacts (zkSync Era artifacts)
            hybrid_artifacts_path = Path("artifacts-zk/contracts/PdMSystemHybrid.sol/PdMSystemHybrid.json")
            if not hybrid_artifacts_path.exists():
                logger.error(f"❌ Hybrid contract artifacts not found: {hybrid_artifacts_path}")
                return False
            
            with open(hybrid_artifacts_path) as f:
                hybrid_artifact = json.load(f)
            # logger.info("✅ Loaded PdMSystemHybrid artifacts from artifacts-zk")
            
            # Contract address'ini deployment_info.json'dan Ã§ek
            contracts = self.deployment_info.get('contracts', {})
            hybrid_address = contracts.get('PdMSystemHybrid', {}).get('address')
            if not hybrid_address:
                logger.error("❌ Hybrid contract address not found in deployment info")
                return False
            
            # Contract instance oluştur
            self.pdm_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(hybrid_address),
                abi=hybrid_artifact['abi']
            )
            
            # logger.info(f"✅ Hybrid PDM Contract loaded: {hybrid_address}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Contract loading error: {e}")
            return False
    
    def _get_verifier_contract(self):
        """Load verifier contract instance on demand."""
        if self._verifier_contract:
            return self._verifier_contract
        if not self.web3 or not self.deployment_info:
            return None
        try:
            contracts = self.deployment_info.get('contracts', {})
            # Hem eski (Optimized...) hem yeni (Unified...) anahtarları destekle
            verifier_info = contracts.get('OptimizedGroth16Verifier') or contracts.get('UnifiedGroth16Verifier') or {}
            verifier_address = verifier_info.get('address')
            if not verifier_address:
                logger.error("Verifier contract address not found in deployment info")
                return None

            # Artifact yolu için iki olasılığı sırayla dene
            candidate_paths = [
                Path("artifacts-zk/contracts/OptimizedGroth16Verifier.sol/OptimizedGroth16Verifier.json"),
                Path("artifacts-zk/contracts/UnifiedGroth16Verifier.sol/UnifiedGroth16Verifier.json")
            ]
            artifact = None
            for p in candidate_paths:
                if p.exists():
                    with open(p, encoding='utf-8') as f:
                        artifact = json.load(f)
                    break
            if artifact is None:
                logger.error("Verifier contract artifacts not found in expected paths")
                return None

            self._verifier_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(verifier_address),
                abi=artifact['abi']
            )
            return self._verifier_contract
        except Exception as e:
            logger.error(f"Verifier contract load error: {e}")
            return None

    def _load_local_sensor_vk_params(self):
        try:
            temp_dir = getattr(self.zk_proof_generator, 'temp_dir', Path('temp/zk_proofs'))
            vk_path = temp_dir / "verification_key.json"
            zkey_path = temp_dir / "sensor_data_proof.zkey"
            if not vk_path.exists():
                if not zkey_path.exists():
                    return None
                if not self._export_sensor_verification_key(zkey_path, vk_path):
                    return None
            vk_json = json.loads(vk_path.read_text(encoding='utf-8'))

            def _norm(v):
                if isinstance(v, int):
                    return v
                s = str(v)
                return int(s, 16) if s.lower().startswith('0x') else int(s)

            alpha = [_norm(vk_json['vk_alpha_1'][0]), _norm(vk_json['vk_alpha_1'][1])]

            def _g2(point):
                # VK için swap YOK - JSON'dan direkt al (on-chain ile aynı sıralama)
                return (
                    [_norm(point[0][0]), _norm(point[0][1])],
                    [_norm(point[1][0]), _norm(point[1][1])]
                )
          

            beta = _g2(vk_json['vk_beta_2'])
            gamma = _g2(vk_json['vk_gamma_2'])
            delta = _g2(vk_json['vk_delta_2'])
            return alpha, beta, gamma, delta
        except Exception:
            return None

    # ----- Revert Reason Yardımcıları -----
    def _extract_revert_reason(self, error) -> str:
        """Web3/JSON-RPC hatalarından olası revert sebebini okunur çıkar."""
        try:
            # web3.exceptions.ContractLogicError (v6) için
            try:
                from web3.exceptions import ContractLogicError  # type: ignore
                if isinstance(error, ContractLogicError):
                    msg = getattr(error, 'revert_message', None)
                    if msg:
                        return str(msg)
            except Exception:
                pass

            # ValueError({... 'message': 'execution reverted: REASON' ...})
            if hasattr(error, 'args') and error.args:
                arg0 = error.args[0]
                if isinstance(arg0, dict):
                    m = arg0.get('message') or ''
                    if isinstance(m, str) and m:
                        text = m
                    else:
                        # Bazı nodelar data -> error -> message taşır
                        data = arg0.get('data') or {}
                        if isinstance(data, dict):
                            # İlk alt hata mesajını topla
                            for v in data.values():
                                if isinstance(v, dict) and 'message' in v and isinstance(v['message'], str):
                                    text = v['message']
                                    break
                            else:
                                text = ''
                        else:
                            text = ''
                else:
                    text = str(arg0)
            else:
                text = str(error)

            import re
            # 'execution reverted: REASON' kalıbını yakala
            m = re.search(r'execution reverted(?::)?\s*(.*)', text, flags=re.IGNORECASE)
            if m and m.group(1):
                return m.group(1).strip()
            # Alternatif kısmi kalıp
            m = re.search(r'(?i)revert(?:ed)?(?::)?\s*(.*)', text)
            if m and m.group(1):
                return m.group(1).strip()
            return text.strip()
        except Exception:
            return str(error)

    def _sensor_verifier_is_set(self) -> bool:
        contract = self._get_verifier_contract()
        if not contract:
            print("❌ Verifier contract not available")
            return False
        try:
            # circuitKeys returns: struct DynVK {alpha, beta, gamma, delta, IC[], isSet}
            vk_info = contract.functions.circuitKeys(0).call()
            if not vk_info:
                print("❌ circuitKeys(0) returned empty")
                return False
            
            # DynVK struct: (G1Point alpha, G2Point beta, G2Point gamma, G2Point delta, G1Point[] IC, bool isSet)
            # Tuple indices: 0=alpha, 1=beta, 2=gamma, 3=delta, 4=IC, 5=isSet
            is_set = bool(vk_info[5]) if len(vk_info) > 5 else False
            print(f"🔍 Sensor VK status: isSet={is_set}")
            
            if len(vk_info) > 4:
                ic_array = vk_info[4]
                ic_length = len(ic_array) if isinstance(ic_array, (list, tuple)) else 0
                print(f"   IC Length: {ic_length}")
                if len(vk_info) > 0 and isinstance(vk_info[0], (list, tuple)) and len(vk_info[0]) >= 2:
                    print(f"   Alpha.X: {vk_info[0][0]}")
            
            if not is_set:
                print("❌ Sensor VK not set on contract - VK upload gerekli!")
                return False

            # On-chain VK ile local VK uyuşuyor mu?
            try:
                alpha_on, beta_on, gamma_on, delta_on = vk_info[0], vk_info[1], vk_info[2], vk_info[3]
                local_params = self._load_local_sensor_vk_params()
                if local_params is None:
                    self._sensor_vk_ready = True
                    return True
                alpha_l, beta_l, gamma_l, delta_l = local_params

                def _eq(a, b):
                    try:
                        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
                    except Exception:
                        return a == b

                if _eq(alpha_on, alpha_l) and _eq(beta_on, beta_l) and _eq(gamma_on, gamma_l) and _eq(delta_on, delta_l):
                    self._sensor_vk_ready = True
                    return True
                else:
                    return False
            except Exception:
                self._sensor_vk_ready = True
                return True
        except Exception as e:
            logger.warning(f"Unable to read verifier key state: {e}")
            return False

    def _export_sensor_verification_key(self, zkey_path: Path, vk_path: Path) -> bool:
        cmd = self.zk_proof_generator._build_snarkjs_command(
            "zkey",
            "export",
            "verificationkey",
            str(zkey_path),
            str(vk_path)
        )
        if not cmd:
            logger.error("snarkjs command not available to export verification key")
            return False
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
                creationflags=self._no_window_flag
            )
            if result.returncode == 0:
                # logger.info(f"Verification key exported to {vk_path}")
                return True
            logger.error(f"Verification key export failed: {result.stderr.strip() or result.stdout.strip()}")
        except Exception as e:
            logger.error(f"Verification key export error: {e}")
        return False

    def _upload_sensor_verifying_key(self) -> bool:
        contract = self._get_verifier_contract()
        if not contract:
            return False

        temp_dir = getattr(self.zk_proof_generator, 'temp_dir', Path('temp/zk_proofs'))
        vk_path = temp_dir / "verification_key.json"
        zkey_path = temp_dir / "sensor_data_proof.zkey"

        if not vk_path.exists():
            if not zkey_path.exists():
                logger.error(f"Verification key not found at {vk_path} and zkey missing at {zkey_path}")
                return False
            if not self._export_sensor_verification_key(zkey_path, vk_path):
                return False

        try:
            vk_json = json.loads(vk_path.read_text(encoding='utf-8'))

            def _norm(value):
                if isinstance(value, int):
                    return value
                sval = str(value)
                return int(sval, 16) if sval.lower().startswith('0x') else int(sval)

            alpha = (_norm(vk_json['vk_alpha_1'][0]), _norm(vk_json['vk_alpha_1'][1]))

            def _g2(point):
                if len(point) < 2:
                    raise ValueError('Invalid G2 point in verification key')
                # VK için swap YOK - JSON'dan direkt al
                return (
                    [_norm(point[0][0]), _norm(point[0][1])],
                    [_norm(point[1][0]), _norm(point[1][1])]
                )

            beta = _g2(vk_json['vk_beta_2'])
            gamma = _g2(vk_json['vk_gamma_2'])
            delta = _g2(vk_json['vk_delta_2'])
            ic_points = [(_norm(p[0]), _norm(p[1])) for p in vk_json['IC']]

            nonce = self.web3.eth.get_transaction_count(self.admin_account, 'pending')
            tx = contract.functions.setCircuitVerifyingKey(
                0,
                alpha,
                beta,
                gamma,
                delta,
                ic_points
            ).build_transaction({
                'from': self.admin_account,
                'nonce': nonce,
                'gas': 5000000,
                'gasPrice': self._get_gas_price()
            })
            signed = self.web3.eth.account.sign_transaction(tx, private_key=self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)
            # logger.info(f"Verifier key transaction sent: {tx_hash.hex()}")
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=BlockchainConfig.TRANSACTION_TIMEOUT)
            if receipt.status != 1:
                logger.error(f"Verifier key transaction failed with status {receipt.status}")
                return False
            # logger.info(f"Verifier key configured on-chain (block {receipt.blockNumber})")
            self._sensor_vk_ready = True
            return True
        except Exception as e:
            logger.error(f"Verifier key upload error: {e}")
            return False

    def _ensure_sensor_verifier_key(self) -> bool:
        if self._sensor_vk_ready:
            return True
        if self._sensor_verifier_is_set():
            return True
        if not self._sensor_vk_warned:
            # logger.info("Sensor circuit verifying key not set on-chain. Attempting automatic configuration (once).")
            self._sensor_vk_warned = True
        if self._upload_sensor_verifying_key():
            return True
        logger.error("Sensor circuit verifying key is missing. Run scripts/set_verifying_key_sensor.js and retry.")
        return False

    # --- Prediction circuit VK helpers ---
    def _prediction_verifier_is_set(self) -> bool:
        contract = self._get_verifier_contract()
        if not contract:
            return False
        try:
            # CircuitType.PREDICTION = 1; ABI: (alpha, beta, gamma, delta, isSet)
            vk_info = contract.functions.circuitKeys(1).call()
            if not vk_info:
                return False
            is_set = bool(vk_info[-1])
            if not is_set:
                return False

            # Yerel VK ile karÅŸÄ±laÅŸtÄ±r (uyum yoksa yeniden yÃ¼kleme tetikle)
            try:
                alpha_on, beta_on, gamma_on, delta_on = vk_info[0], vk_info[1], vk_info[2], vk_info[3]
                local_params = self._load_local_prediction_vk_params()
                if local_params is None:
                    return True
                alpha_l, beta_l, gamma_l, delta_l = local_params

                def _eq(a, b):
                    try:
                        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
                    except Exception:
                        return a == b

                if _eq(alpha_on, alpha_l) and _eq(beta_on, beta_l) and _eq(gamma_on, gamma_l) and _eq(delta_on, delta_l):
                    return True
                else:
                    return False
            except Exception:
                return True
        except Exception as e:
            logger.warning(f"Unable to read prediction verifier key state: {e}")
            return False

    def _export_prediction_verification_key(self, zkey_path: Path, vk_path: Path) -> bool:
        cmd = self.zk_proof_generator._build_snarkjs_command(
            "zkey", "export", "verificationkey", str(zkey_path), str(vk_path)
        )
        if not cmd:
            logger.error("snarkjs command not available to export verification key (prediction)")
            return False
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
                creationflags=self._no_window_flag
            )
            if result.returncode == 0:
                # logger.info(f"Prediction verification key exported to {vk_path}")
                return True
            logger.error(f"Prediction verification key export failed: {result.stderr.strip() or result.stdout.strip()}")
        except Exception as e:
            logger.error(f"Prediction verification key export error: {e}")
        return False

    def _upload_prediction_verifying_key(self) -> bool:
        contract = self._get_verifier_contract()
        if not contract:
            return False

        temp_dir = getattr(self.zk_proof_generator, 'temp_dir', Path('temp/zk_proofs'))
        vk_path = temp_dir / "prediction_verification_key.json"
        zkey_path = temp_dir / "prediction_proof.zkey"

        # VK yoksa ya da zkey daha yeniyse yeniden export et
        try:
            need_export = (not vk_path.exists())
            if (vk_path.exists() and zkey_path.exists() and zkey_path.stat().st_mtime > vk_path.stat().st_mtime):
                need_export = True
            if need_export:
                if not zkey_path.exists():
                    logger.error(f"Prediction VK not found at {vk_path} and zkey missing at {zkey_path}")
                    return False
                if not self._export_prediction_verification_key(zkey_path, vk_path):
                    return False
        except Exception:
            pass

        try:
            vk_json = json.loads(vk_path.read_text(encoding='utf-8'))

            def _norm(value):
                if isinstance(value, int):
                    return value
                sval = str(value)
                return int(sval, 16) if sval.lower().startswith('0x') else int(sval)

            alpha = (_norm(vk_json['vk_alpha_1'][0]), _norm(vk_json['vk_alpha_1'][1]))

            def _g2(point):
                if len(point) < 2:
                    raise ValueError('Invalid G2 point in verification key (prediction)')
                # VK için swap YOK - JSON'dan direkt al
                return (
                    [_norm(point[0][0]), _norm(point[0][1])],
                    [_norm(point[1][0]), _norm(point[1][1])]
                )

            beta = _g2(vk_json['vk_beta_2'])
            gamma = _g2(vk_json['vk_gamma_2'])
            delta = _g2(vk_json['vk_delta_2'])
            ic_points = [(_norm(p[0]), _norm(p[1])) for p in vk_json['IC']]

            nonce = self.web3.eth.get_transaction_count(self.admin_account, 'pending')
            tx = contract.functions.setCircuitVerifyingKey(
                1,
                alpha,
                beta,
                gamma,
                delta,
                ic_points
            ).build_transaction({
                'from': self.admin_account,
                'nonce': nonce,
                'gas': 5000000,
                'gasPrice': self._get_gas_price()
            })
            signed = self.web3.eth.account.sign_transaction(tx, private_key=self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)
            # logger.info(f"Prediction verifier key transaction sent: {tx_hash.hex()}")
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=BlockchainConfig.TRANSACTION_TIMEOUT)
            if receipt.status != 1:
                logger.error(f"Prediction verifier key transaction failed with status {receipt.status}")
                return False
            # logger.info(f"Prediction verifier key configured on-chain (block {receipt.blockNumber})")
            return True
        except Exception as e:
            logger.error(f"Prediction verifier key upload error: {e}")
            return False

    def _load_local_prediction_vk_params(self):
        try:
            temp_dir = getattr(self.zk_proof_generator, 'temp_dir', Path('temp/zk_proofs'))
            vk_path = temp_dir / "prediction_verification_key.json"
            zkey_path = temp_dir / "prediction_proof.zkey"
            if not vk_path.exists():
                if not zkey_path.exists():
                    return None
                if not self._export_prediction_verification_key(zkey_path, vk_path):
                    return None
            vk_json = json.loads(vk_path.read_text(encoding='utf-8'))

            def _norm(value):
                if isinstance(value, int):
                    return value
                sval = str(value)
                return int(sval, 16) if sval.lower().startswith('0x') else int(sval)

            # On-chain ABI circuitKeys(1) döndüğünü şekle uygun olacak biçimde
            # G1: [X, Y]
            # G2: [[X0, X1], [Y0, Y1]]
            alpha = [_norm(vk_json['vk_alpha_1'][0]), _norm(vk_json['vk_alpha_1'][1])]

            def _g2(point):
                # VK için swap YOK – JSON sırası ile (on-chain'e yazılan sıraya uygun)
                return (
                    [_norm(point[0][0]), _norm(point[0][1])],
                    [_norm(point[1][0]), _norm(point[1][1])]
                )

            beta = _g2(vk_json['vk_beta_2'])
            gamma = _g2(vk_json['vk_gamma_2'])
            delta = _g2(vk_json['vk_delta_2'])
            return (alpha, beta, gamma, delta)
        except Exception:
            return None

    def _ensure_prediction_verifier_key(self) -> bool:
        # Eğer on-chain VK var ve yerel VK ile eşleşiyorsa tamam
        if self._prediction_verifier_is_set():
            return True
        logger.warning("Prediction circuit verifying key not set/mismatch. Attempting automatic configuration.")
        if self._upload_prediction_verifying_key():
            return True
        logger.error("Prediction circuit verifying key is missing. Configure verifier key and retry.")
        return False
    
    def is_ready(self):
        """Sistem hazır mı?"""
        return all([self.web3, self.admin_account, self.pdm_contract])

    def diagnose(self) -> Dict:
        """Ağ/kontrat/konfigürasyon durumunu özetler (hızlı teşhis)."""
        diag: Dict = {
            'rpc_url': self.rpc_url,
            'network_name': self.network_name,
            'web3_connected': False,
            'admin_account': self.admin_account,
            'balance_eth': None,
            'pdm_contract_loaded': False,
            'pdm_contract_address': None,
            'artifacts_present': False,
            'deployment_info_present': False
        }
        try:
            diag['web3_connected'] = bool(self.web3 and self.web3.is_connected())
        except Exception:
            diag['web3_connected'] = False

        try:
            if self.admin_account and self.web3:
                bal = self.web3.from_wei(self.web3.eth.get_balance(self.admin_account), 'ether')
                diag['balance_eth'] = float(bal)
        except Exception:
            pass

        try:
            hybrid_artifacts_path = Path("artifacts-zk/contracts/PdMSystemHybrid.sol/PdMSystemHybrid.json")
            diag['artifacts_present'] = hybrid_artifacts_path.exists()
        except Exception:
            diag['artifacts_present'] = False

        try:
            dep_path = ConfigUtils.get_deployment_info_path()
            diag['deployment_info_present'] = dep_path.exists()
            if dep_path.exists():
                with open(dep_path) as f:
                    dep = json.load(f)
                pdm_addr = dep.get('contracts', {}).get('PdMSystemHybrid', {}).get('address')
                diag['pdm_deployment_address'] = pdm_addr
        except Exception:
            pass

        try:
            if self.pdm_contract:
                diag['pdm_contract_loaded'] = True
                diag['pdm_contract_address'] = self.pdm_contract.address
        except Exception:
            pass

        # logger.info(f"✅ Diagnose: {diag}")
        return diag
    
    def submit_sensor_data_hybrid(self, prediction_data: Dict) -> Dict:
        """
        Hibrit yaklaşımla sensör verisi gönder
        1. Local DB'ye kaydet
        2. ZK proof oluştur  
        3. Blockchain'e proof gönder
        """
        try:
            # logger.info("Starting hybrid sensor data submission...")
            
            sensor_data = SensorData(
                machine_id=(int(time.time()) % 9999) + 1,
                air_temperature=prediction_data['air_temp'],
                process_temperature=prediction_data['process_temp'],
                rotational_speed=int(prediction_data['rotation_speed']),
                torque=prediction_data['torque'],
                tool_wear=int(prediction_data['tool_wear']),
                machine_type=prediction_data.get('machine_type', 'M'),
                timestamp=int(time.time()),
                submitter=self.admin_account or "0x0000000000000000000000000000000000000000"
            )
            
            # logger.info("Veri depolanıyor (PdM DB mevcutsa öncelikli)...")
            data_id, data_hash = self.storage_manager.store_sensor_data(sensor_data)
            storage_location = f"sensor_{data_id}"

            # logger.info("Generating ZK proof...")
            sensor_data.data_id = data_id
            proof_data = self.zk_proof_generator.generate_sensor_proof_v2(sensor_data)
            
            if not proof_data:
                return {'success': False, 'error': 'ZK proof generation failed'}
            
            blockchain_result: Dict[str, Any] = {'success': False}
            
            if self.is_ready():
                # logger.info("Submitting proof to blockchain...")
                blockchain_result = self._submit_sensor_proof_to_blockchain(
                    sensor_data,
                    data_hash,
                    storage_location,
                    proof_data
                )
                if blockchain_result.get('success'):
                    self.storage_manager.update_blockchain_proof_id(
                        'sensor_data',
                        data_id,
                        blockchain_result.get('proof_id'),
                        blockchain_result.get('tx_hash')
                    )
            else:
                logger.warning("Blockchain not ready - data stored locally only")
            
            # Compute overall status and success
            blockchain_attempted = self.is_ready()
            blockchain_ok = bool(blockchain_result.get('success'))
            status = (
                'onchain_success' if blockchain_attempted and blockchain_ok else
                'onchain_failed' if blockchain_attempted and not blockchain_ok else
                'local_only'
            )

            result: Dict[str, Any] = {
                'success': (blockchain_ok if blockchain_attempted else True),
                'status': status,
                'storage_type': 'hybrid',
                'local_data_id': data_id,
                'data_hash': data_hash,
                'storage_location': storage_location,
                'zk_proof_generated': True,
                'blockchain_submitted': blockchain_ok,
                'tx_hash': blockchain_result.get('tx_hash', 'N/A'),
                'block_number': blockchain_result.get('block_number', 'N/A'),
                'zk_proof_hash': blockchain_result.get('zk_proof_hash', 'N/A'),
            }

            if blockchain_result.get('success'):
                result.update({
                    'blockchain_proof_id': blockchain_result.get('proof_id'),
                    'gas_used': blockchain_result.get('gas_used')
                })
            
            try:
                success_value = blockchain_result.get('success', False)
                
                # Local DB (pdm_hybrid_storage.db) güncellemesi
                self.storage_manager.update_blockchain_info(
                    record_id=data_id,
                    success=success_value,
                    tx_hash=result['tx_hash'],
                    proof_id=blockchain_result.get('proof_id'),
                    zk_proof_hash=result.get('zk_proof_hash')
                )
                
                # PdM DB (PdMDatabase/PdMDatabase) için data_hash ile eşleştirme
                if self.storage_manager.pdm_db:
                    try:
                        db_path = getattr(self.storage_manager.pdm_db, 'db_path', None)
                        if db_path:
                            import sqlite3
                            conn = sqlite3.connect(str(db_path))
                            cursor = conn.cursor()
                            # data_hash ile eşleştir (offchain_data_hash sütunu)
                            cursor.execute("""
                                UPDATE sensor_data 
                                SET blockchain_success = ?, 
                                    blockchain_tx_hash = ?,
                                    blockchain_proof_id = ?
                                WHERE offchain_data_hash = ? OR data_hash = ?
                            """, (
                                1 if success_value else 0,
                                result['tx_hash'],
                                blockchain_result.get('proof_id'),
                                data_hash,
                                data_hash
                            ))
                            conn.commit()
                            conn.close()
                    except Exception as pdm_err:
                        logger.warning(f"⚠️ PdM DB update via data_hash failed: {pdm_err}")
                
            except AttributeError:
                pass
            except Exception as db_error:
                logger.warning(f"Could not update blockchain info in DB: {db_error}")

            # Bubble up blockchain error info if on-chain submission was attempted and failed
            if blockchain_attempted and not blockchain_ok and blockchain_result.get('error'):
                result['error'] = blockchain_result.get('error')

            # logger.info("Hybrid sensor data submission completed!")
            return result
            
        except Exception as e:
            logger.error(f"Hybrid sensor data submission error: {e}")
            return {
                'success': False,
                'error': str(e),
                'storage_type': 'hybrid',
                'local_data_id': None,
                'data_hash': None,
                'storage_location': None,
                'zk_proof_generated': False,
                'blockchain_submitted': False,
                'tx_hash': 'N/A',
                'block_number': 'N/A',
            }
    
    def _submit_sensor_proof_to_blockchain(self, sensor_data: SensorData, data_hash: str, 
                                         storage_location: str, proof_data: Dict) -> Dict:
        """ZK proof'u blockchain'e gönder"""
        try:
            # --- Access Control Pre-flight Check ---
            # logger.info("✅ Performing access control pre-flight check...")
            try:
                # Load AccessControlRegistry contract if not already loaded
                if not hasattr(self, 'access_registry_contract'):
                    access_registry_address = self.pdm_contract.functions.accessRegistry().call()
                    access_artifacts_path = Path("artifacts-zk/contracts/AccessControlRegistry.sol/AccessControlRegistry.json")
                    with open(access_artifacts_path) as f:
                        access_artifact = json.load(f)
                    self.access_registry_contract = self.web3.eth.contract(
                        address=access_registry_address,
                        abi=access_artifact['abi']
                    )
                
                sensor_data_resource = self.pdm_contract.functions.SENSOR_DATA_RESOURCE().call()
                write_limited_level = 2  # Corresponds to AccessLevel.WRITE_LIMITED (0=NO_ACCESS, 1=READ_ONLY, 2=WRITE_LIMITED)
                
                has_access, reason = self.access_registry_contract.functions.checkAccess(
                    self.admin_account,
                    sensor_data_resource,
                    write_limited_level
                ).call()

                if not has_access:
                    error_msg = f"Access denied for {self.admin_account} on SENSOR_DATA_RESOURCE. Reason: {reason}"
                    logger.error(f"❌ {error_msg}")
                    return {'success': False, 'error': 'access_control', 'details': error_msg}
                
                # logger.info("✅ Access control check passed.")

            except Exception as ac_error:
                logger.error(f"❌ Failed to perform access control check: {ac_error}")
                # Continue anyway but log the failure, as the main transaction might still work
                # if the check itself was faulty.

            # --- Duplicate data hash check (prevent revert: "Data hash already used") ---
            try:
                if data_hash and isinstance(data_hash, str) and data_hash.startswith('0x') and self.pdm_contract:
                    already_used = bool(self.pdm_contract.functions.usedDataHashes(bytes.fromhex(data_hash[2:])).call())
                    if already_used:
                        logger.error("❌ Sensor data hash already used on-chain; skipping submission")
                        return {'success': False, 'error': 'data_hash_already_used'}
            except Exception as dupe_err:
                logger.warning(f"⚠️ Could not check usedDataHashes: {dupe_err}")
            
            proof = proof_data['proof']
            public_inputs = proof_data['publicInputs']
            # --- Proof verilerini hazırla (Unified) ---
            
            if 'pi_a' in proof:
                a = [int(proof['pi_a'][0]), int(proof['pi_a'][1])]
                b_native = [[int(proof['pi_b'][0][0]), int(proof['pi_b'][0][1])],
                     [int(proof['pi_b'][1][0]), int(proof['pi_b'][1][1])]]
                c = [int(proof['pi_c'][0]), int(proof['pi_c'][1])]
            else:
                a = [int(proof['a'][0]), int(proof['a'][1])]
                b_native = [[int(proof['b'][0][0]), int(proof['b'][0][1])],
                     [int(proof['b'][1][0]), int(proof['b'][1][1])]]
                c = [int(proof['c'][0]), int(proof['c'][1])]
            
            public_inputs_int = [int(x) for x in public_inputs]
            # Sensor circuit (privacy-first) expects exactly 3 public inputs: [machineId, timestamp, dataCommitment]
            if len(public_inputs_int) > 3:
                public_inputs_int = public_inputs_int[:3]

            # dataCommitment is the 3rd public input (Poseidon hash of sensor values)
            data_commitment_int = int(public_inputs_int[2])
            # Convert to bytes32 for contract call
            commitment_hash = data_commitment_int.to_bytes(32, byteorder='big')

            # --- DEBUG LOG ---
            print("\n" + "="*70)
            print("🔍 PREPARING SENSOR PROOF TRANSACTION")
            print("="*70)
            print(f"   machineId: {sensor_data.machine_id}")
            print(f"   timestamp: {public_inputs_int[1]}")
            print(f"   dataHash: {data_hash}")
            print(f"   commitmentHash: {commitment_hash.hex()}")
            print(f"   storageLocation: {storage_location}")
            print(f"   sensorCount: 1")
            print(f"   a: {a}")
            # B noktasını doğrulama öncesi seç (native vs swapped)
            b = b_native

            print(f"   b: {b}")
            print(f"   c: {c}")
            print(f"   publicInputs: {public_inputs_int}")
            print("="*70 + "\n")

            if not self._ensure_sensor_verifier_key():
                return {'success': False, 'error': 'verifier_key_not_configured'}

            nonce = self.web3.eth.get_transaction_count(self.admin_account, 'pending')
            
            # Pre-simulation to catch reverts early
            print("🧪 Testing transaction simulation...")
            try:
                gas_estimate = self.pdm_contract.functions.submitSensorDataProof(
                    int(sensor_data.machine_id),
                    bytes.fromhex(data_hash[2:]),
                    commitment_hash,
                    self._string_to_bytes32(storage_location),
                    1,
                    [a[0], a[1]],
                    [[b[0][0], b[0][1]], [b[1][0], b[1][1]]],
                    [c[0], c[1]],
                    public_inputs_int
                ).estimate_gas({'from': self.admin_account})
                print(f"✅ Simulation passed! Gas estimate: {gas_estimate}")
            except Exception as sim_err:
                reason = self._extract_revert_reason(sim_err)
                print(f"❌ SIMULATION FAILED: {reason}")
                print(f"   Full error: {str(sim_err)}")
                logger.error(f"Sensor tx simulation failed: {reason}")
                return {'success': False, 'error': f'simulation_failed: {reason}'}
            
            submit_proof_tx = self.pdm_contract.functions.submitSensorDataProof(
                int(sensor_data.machine_id),
                bytes.fromhex(data_hash[2:]),
                commitment_hash,
                self._string_to_bytes32(storage_location),
                1,
                [a[0], a[1]],
                [[b[0][0], b[0][1]], [b[1][0], b[1][1]]],
                [c[0], c[1]],
                public_inputs_int
            ).build_transaction({
                'from': self.admin_account,
                'nonce': nonce,
                'gas': getattr(BlockchainConfig, 'SENSOR_DATA_GAS_LIMIT', 800000),
                'gasPrice': self._get_gas_price()
            })
            
            # !CALL_MARK 
            try:
                proof_id = self.pdm_contract.functions.submitSensorDataProof(
                    sensor_data.machine_id,
                    bytes.fromhex(data_hash[2:]),
                    commitment_hash,
                    self._string_to_bytes32(storage_location),
                    1,
                    a, b, c,
                    public_inputs_int
                ).call({'from': self.admin_account})
                # logger.info(f"âœ… Proof ID from call: {proof_id}")
            except Exception as call_error:
                logger.warning(f"❌ Call failed (reason): {call_error}")
                proof_id = None
            
            signed_tx = self.web3.eth.account.sign_transaction(submit_proof_tx, private_key=self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            # logger.info(f"✅ Transaction sent: {tx_hash.hex()}")
            
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=BlockchainConfig.TRANSACTION_TIMEOUT)
            
            if receipt.status == 1:
                if proof_id is None:
                    proof_id = self._extract_proof_id_from_receipt(receipt)
                zk_hash_hex = None
                try:
                    if proof_id:
                        sp = self.pdm_contract.functions.sensorProofs(int(proof_id)).call()
                        # struct SensorDataProof: index 7 is zkProofHash
                        if isinstance(sp, (list, tuple)) and len(sp) >= 8:
                            zk_val = sp[7]
                            try:
                                # bytes32 -> hex
                                zk_hash_hex = self.web3.to_hex(zk_val) if hasattr(self.web3, 'to_hex') else (
                                    zk_val.hex() if hasattr(zk_val, 'hex') else str(zk_val)
                                )
                            except Exception:
                                zk_hash_hex = zk_val.hex() if hasattr(zk_val, 'hex') else str(zk_val)
                except Exception:
                    zk_hash_hex = None
                return {
                    'success': True,
                    'proof_id': proof_id,
                    'tx_hash': tx_hash.hex(),
                    'block_number': receipt.blockNumber,
                    'gas_used': receipt.gasUsed,
                    'zk_proof_hash': zk_hash_hex or 'N/A'
                }
            else:
                return {'success': False, 'error': f'Transaction failed - Status: {receipt.status}'}
                
        except Exception as e:
            logger.error(f"❌ Blockchain proof submission error: {e}")
            return {'success': False, 'error': str(e)}
    
    def retrieve_sensor_data(self, data_identifier: Any) -> Optional[SensorData]:
        """
        Sensör verisini geri getir (ID veya hash ile)
        Boş liste veya beklenmeyen format kontrolü içerir
        """
        try:
            retrieved_data = None
            if isinstance(data_identifier, int):
                # Adapter exposes get_sensor_data; there is no get_sensor_data_obj
                retrieved_data = self.storage_manager.get_sensor_data(data_identifier)
            elif isinstance(data_identifier, str):
                retrieved_data = self.storage_manager.get_sensor_data_by_hash_obj(data_identifier)
            else:
                logger.error(f"❌ Invalid data identifier type: {type(data_identifier)}")
                return None

            # Liste dönmüşse ve boşsa None dön
            if isinstance(retrieved_data, list):
                return retrieved_data[0] if retrieved_data else None

            # SensorData nesnesi dönmüşse direkt return
            if hasattr(retrieved_data, 'machine_id'):
                return retrieved_data

            logger.warning(f"❌ Retrieved data in unexpected format: {retrieved_data}")
            return None

        except Exception as e:
            logger.error(f"❌ Data retrieval error: {e}")
            return None
            
    def verify_data_integrity(self, data_id: int, expected_hash: str) -> bool:
        """
        Veri bütünlüğünü doğrula
        """
        try:
            # Local DB'den veriyi al
            # Adapter exposes get_sensor_data; there is no get_sensor_data_obj
            sensor_data = self.storage_manager.get_sensor_data(data_id)
            if not sensor_data:
                return False
            
            # Hash'i yeniden hesapla (Poseidon hash kullan)
            from real_poseidon_utils import RealPoseidonHasher
            poseidon_hasher = RealPoseidonHasher()
            
            machine_type_int = {"L": 1, "M": 2, "H": 3}.get(sensor_data.machine_type, 2)
            sensor_values = [
                int(sensor_data.air_temperature * 100),
                int(sensor_data.process_temperature * 100),
                int(sensor_data.rotational_speed),
                int(sensor_data.torque * 100),
                int(sensor_data.tool_wear),
                machine_type_int
            ]
            try:
                import json, subprocess
                hash_cmd = f"""
                const circomlibjs = require("circomlibjs");
                (async () => {{
                    const poseidon = await circomlibjs.buildPoseidon();
                    const inputs = {json.dumps([str(v) for v in sensor_values])}.map(BigInt);
                    const hash = poseidon(inputs);
                    console.log(poseidon.F.toString(hash));
                }})();
                """
                result = subprocess.run(
                    ["node", "-e", hash_cmd],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True
                )
                poseidon_result = result.stdout.strip()
            except Exception as e:
                logger.error(f"Poseidon hash failed in integrity check: {e}")
                return False
            calculated_hash = poseidon_hasher.poseidon_to_hex(poseidon_result)
            
            is_valid = calculated_hash == expected_hash
            # logger.info(f"✅ Data integrity check: {'✅ Valid' if is_valid else '❌ Invalid'}")
            return is_valid
            
        except Exception as e:
            logger.error(f"❌ Data integrity verification error: {e}")
            return False
    
    def get_system_statistics(self) -> Dict:
        """
        Sistem istatistikleri
        """
        try:
            # Local storage stats
            local_stats = self.storage_manager.get_statistics()
            
            # Blockchain stats (if available)
            blockchain_stats = {}
            if self.is_ready():
                try:
                    blockchain_stats = {
                        'network': self.network_name,
                        'connected': True,
                        'contract_address': self.pdm_contract.address,
                        'admin_account': self.admin_account,
                        'balance': float(self.web3.from_wei(self.web3.eth.get_balance(self.admin_account), 'ether'))
                    }
                except:
                    blockchain_stats = {'connected': False}
            else:
                blockchain_stats = {'connected': False}
            
            return {
                'storage_type': 'hybrid',
                'local_storage': local_stats,
                'blockchain': blockchain_stats,
                'timestamp': int(time.time())
            }
            
        except Exception as e:
            logger.error(f"❌ Statistics error: {e}")
            return {'error': str(e)}
    
    def _string_to_bytes32(self, text: str) -> bytes:
        """
        String'i bytes32'ye çevir (gaz optimizasyonu için)
        Kısa metinlerde UTF-8 ile pad edilmiş 32 byte döner.
        32 karakterden uzun metinlerde SHA-256 digest (32 byte) döner.
        """
        if len(text) > 32:
            # Uzun string'ler için gerçek 32 byte'lık SHA-256 digest kullan
            digest = hashlib.sha256(text.encode('utf-8')).digest()  # 32 bytes
            try:
                logger.warning(
                    f"❌ Storage location too long, using sha256 digest: {text} -> 0x{digest.hex()}"
                )
            except Exception:
                # Bazı konsollar unicode/encoding sorunu yaşayabilir
                logger.warning(
                    "Storage location too long, using sha256 digest (see debug for hex)"
                )
                logger.debug({"original": text, "digest_hex": digest.hex()})
            return digest

        # Kısa metinler için string'i 32 byte'a pad et
        return text.encode('utf-8').ljust(32, b'\x00')
    
    def _bytes32_to_string(self, data: bytes) -> str:
        """
        bytes32'yi string'e çevir
        """
        return data.rstrip(b'\x00').decode('utf-8')
    
    def _get_gas_price(self):
        """Gas price hesapla"""
        try:
            current_gas_price = self.web3.eth.gas_price
            min_gas_price = self.web3.to_wei(BlockchainConfig.SENSOR_DATA_GAS_PRICE_GWEI, 'gwei')
            return max(current_gas_price, min_gas_price)
        except Exception:
            return self.web3.to_wei(BlockchainConfig.SENSOR_DATA_GAS_PRICE_GWEI, 'gwei')
    
    def get_network_info(self) -> Optional[Dict]:
        """Network bilgilerini döndürür"""
        if not self.web3:
            return None
            
        try:
            block_number = self.web3.eth.block_number
            
            # Balance bilgisini al
            balance_wei = 0
            balance_eth = 0.0
            if self.admin_account:
                try:
                    balance_wei = self.web3.eth.get_balance(self.admin_account)
                    balance_eth = self.web3.from_wei(balance_wei, 'ether')
                except Exception as e:
                    logger.warning(f"Balance alınamadı: {e}")
            
            return {
                'network_name': self.network_name,
                'chain_id': self.web3.eth.chain_id,
                'block_number': block_number,
                'rpc_url': self.rpc_url,
                'admin_account': self.admin_account,
                'balance': float(balance_eth),
                'currency': 'ETH'
            }
        except Exception as e:
            logger.error(f"Network info error: {e}")
            return None
    
    def get_contract_info(self) -> Optional[Dict]:
        """Contract bilgilerini döndürür"""
        if not self.deployment_info:
            return None
            
        try:
            contracts = self.deployment_info.get('contracts', {})
            hybrid_contract = contracts.get('PdMSystemHybrid', {})
            verifier_contract = contracts.get('OptimizedGroth16Verifier', {}) or contracts.get('UnifiedGroth16Verifier', {})
            access_control_contract = contracts.get('AccessControlRegistry', {})
            
            return {
                'pdm_address': hybrid_contract.get('address'),
                'verifier_address': verifier_contract.get('address'),
                'access_control_address': access_control_contract.get('address'),
                'deployment_time': self.deployment_info.get('timestamp', 'Unknown'),
                'system_type': self.deployment_info.get('system_type', 'hybrid'),
                'admin_account': self.admin_account
            }
        except Exception as e:  
            logger.error(f"Contract info error: {e}")
            return None

    # --- New: Full prediction submission with on-chain proof ---
    def submit_prediction_hybrid_v2(self, prediction_data: Dict, sensor_data_id: int) -> Dict:
        """
        Improved hybrid prediction submission: generates ZK proof and submits to blockchain.
        prediction_data may include 'data_proof_id_onchain' (int) to reference sensor proof on-chain.
        """
        try:
            # logger.info("✅ Starting hybrid prediction submission (v2)...")

            sensor_data = self.storage_manager.get_sensor_data_obj(sensor_data_id)
            if not sensor_data:
                return {'success': False, 'error': f'Sensor data ID {sensor_data_id} not found'}

            prediction = PredictionData(
                data_id=sensor_data_id,
                prediction=int(prediction_data['prediction']),
                probability=float(prediction_data['probability']),
                model_version="LSTM-CNN-v1.0",
                model_hash=hashlib.sha256(f"model_{time.time()}".encode()).hexdigest(),
                predictor=self.admin_account or "0x0000000000000000000000000000000000000000",
                timestamp=int(time.time())
            )

            # logger.info("✅ Storing prediction in local database...")
            pred_id, pred_hash = self.storage_manager.store_prediction_data(prediction)

            # On-chain sensor proof ID zorunlu: yoksa DB'den çözmeyi dene
            data_proof_id_onchain = prediction_data.get('data_proof_id_onchain')
            if not data_proof_id_onchain:
                data_proof_id_onchain = self._resolve_sensor_proof_id_onchain(sensor_data_id)
            try:
                data_proof_id_onchain = int(data_proof_id_onchain or 0)
            except Exception:
                data_proof_id_onchain = 0
            if data_proof_id_onchain <= 0:
                return {
                    'success': False,
                    'error': 'missing_data_proof_id_onchain',
                    'details': 'Prediction göndermeden önce sensör kanıtını zincire yazın ve dönen proof_idyi data_proof_id_onchain olarak geçin.'
                }

            # logger.info("✅ Generating prediction ZK proof (v2)...")
            prediction.prediction_id = pred_id
            proof_data = self.zk_proof_generator.generate_prediction_proof(
                prediction,
                sensor_data,
                data_proof_id_onchain=data_proof_id_onchain
            )
            if not proof_data:
                return {'success': False, 'error': 'Prediction ZK proof generation failed'}

            blockchain_result: Dict[str, Any] = {'success': False}
            if self.is_ready():
                # logger.info("✅ Submitting prediction proof to blockchain (v2)...")
                model_commitment = self.web3.keccak(text=prediction.model_hash or prediction.model_version)
                confidence_int = int(float(prediction.probability) * 10000)
                
                blockchain_result = self._submit_prediction_proof_to_blockchain(
                    data_proof_id_onchain=data_proof_id_onchain,
                    prediction_hash=pred_hash,
                    model_commitment=model_commitment,
                    prediction_value=int(prediction.prediction),
                    confidence_value=confidence_int,
                    proof_data=proof_data
                )
                if blockchain_result.get('success'):
                    self.storage_manager.update_blockchain_proof_id('prediction_data', pred_id, blockchain_result.get('proof_id'))

            result = {
                'success': bool(blockchain_result.get('success')),
                'storage_type': 'hybrid',
                'local_prediction_id': pred_id,
                'prediction_hash': pred_hash,
                'zk_proof_generated': True,
                'blockchain_submitted': bool(blockchain_result.get('success')),
                'tx_hash': blockchain_result.get('tx_hash', 'N/A'),
                'block_number': blockchain_result.get('block_number', 'N/A')
            }

            # Hata detayını kullanıcıya yansıt
            if not blockchain_result.get('success') and blockchain_result.get('error'):
                result['error'] = blockchain_result.get('error')

            # logger.info("✅ Hybrid prediction submission (v2) completed!")
            return result
        except Exception as e:
            logger.error(f"❌ Hybrid prediction submission (v2) error: {e}")
            return {'success': False, 'error': str(e)}

    def _resolve_sensor_proof_id_onchain(self, sensor_data_id: int) -> Optional[int]:
        """DB'den sensor_data.blockchain_proof_id alanını bulup döndür. 
        Önce PdM DB (varsa), ardından local SQLite taranır.
        """
        # PdM DB
        try:
            if self.pdm_db and hasattr(self.pdm_db, 'get_sensor_data'):
                rows = self.pdm_db.get_sensor_data(record_id=sensor_data_id)
                if isinstance(rows, list) and rows:
                    row = rows[0]
                    if isinstance(row, dict):
                        pid = row.get('blockchain_proof_id') or row.get('proof_id')
                        if pid:
                            return int(pid)
        except Exception:
            pass
        # Local SQLite
        try:
            if self.local_storage and hasattr(self.local_storage, 'db_path'):
                import sqlite3
                conn = sqlite3.connect(str(self.local_storage.db_path))
                cur = conn.cursor()
                cur.execute('SELECT blockchain_proof_id FROM sensor_data WHERE id=?', (sensor_data_id,))
                row = cur.fetchone()
                conn.close()
                if row and row[0]:
                    return int(row[0])
        except Exception:
            pass
        return None

# --- Monkey patch: improve sensor proof submission by trying swapped B if needed ---
try:
    _orig_submit_sensor = None
    if 'HybridBlockchainHandler' in globals():
        _orig_submit_sensor = getattr(HybridBlockchainHandler, '_submit_sensor_proof_to_blockchain', None)

    def _swap_b_array(b_arr):
        try:
            return [[int(b_arr[0][1]), int(b_arr[0][0])], [int(b_arr[1][1]), int(b_arr[1][0])]]
        except Exception:
            return b_arr

    def _patched_submit_sensor(self, sensor_data, data_hash, storage_location, proof_data):
        if _orig_submit_sensor is None:
            # Fallback to error
            return {'success': False, 'error': 'submit_method_missing'}
        # İlk deneme: orijinal yöntem (native b)
        result = _orig_submit_sensor(self, sensor_data, data_hash, storage_location, proof_data)
        err = (result or {}).get('error')
        if result and result.get('success'):
            return result
        # Eğer invalid proof/simulation_failed hatası varsa b'yi swap ederek tekrar dene
        reason_text = str(err or '')
        should_retry = ('simulation_failed' in reason_text) or ('Invalid sensor data ZK proof' in reason_text)
        if not should_retry:
            return result
        try:
            # Derin kopya al ve b'yi swap et
            import copy
            proof_data_swapped = copy.deepcopy(proof_data)
            pf = proof_data_swapped.get('proof') or {}
            if 'pi_b' in pf:
                pf['pi_b'] = _swap_b_array(pf['pi_b'])
            elif 'b' in pf:
                pf['b'] = _swap_b_array(pf['b'])
            # Tekrar dene
            return _orig_submit_sensor(self, sensor_data, data_hash, storage_location, proof_data_swapped)
        except Exception:
            return result

    if _orig_submit_sensor is not None:
        HybridBlockchainHandler._submit_sensor_proof_to_blockchain = _patched_submit_sensor
except Exception:
    pass

# --- Monkey patch: fix sensor VK check for UnifiedGroth16Verifier ABI ---
try:
    _orig_sensor_vk_check = None
    if 'HybridBlockchainHandler' in globals():
        _orig_sensor_vk_check = getattr(HybridBlockchainHandler, '_sensor_verifier_is_set', None)

    def _patched_sensor_verifier_is_set(self) -> bool:
        contract = self._get_verifier_contract()
        if not contract:
            print("Verifier contract not available")
            return False
        try:
            vk_info = contract.functions.circuitKeys(0).call()
            if not vk_info:
                print("circuitKeys(0) returned empty")
                return False
            is_set = bool(vk_info[-1]) if isinstance(vk_info, (list, tuple)) else False
            print(f"Sensor VK status: isSet={is_set}")
            # Optional diagnostics
            try:
                alpha_val = vk_info[0]
                if isinstance(alpha_val, (list, tuple)) and len(alpha_val) >= 2:
                    print(f"   Alpha.X: {alpha_val[0]}")
            except Exception:
                pass
            # If there's an IC array (older ABI), show its length
            try:
                if isinstance(vk_info, (list, tuple)) and len(vk_info) > 4 and isinstance(vk_info[4], (list, tuple)):
                    print(f"   IC Length: {len(vk_info[4])}")
            except Exception:
                pass
            if not is_set:
                print("Sensor VK not set on contract - VK upload gerekli!")
                return False
            # Compare with local VK if available (best-effort)
            try:
                alpha_on, beta_on, gamma_on, delta_on = vk_info[0], vk_info[1], vk_info[2], vk_info[3]
                local_params = self._load_local_sensor_vk_params()
                if local_params is None:
                    self._sensor_vk_ready = True
                    return True
                alpha_l, beta_l, gamma_l, delta_l = local_params
                def _eq(a, b):
                    try:
                        import json as _json
                        return _json.dumps(a, sort_keys=True) == _json.dumps(b, sort_keys=True)
                    except Exception:
                        return a == b
                if _eq(alpha_on, alpha_l) and _eq(beta_on, beta_l) and _eq(gamma_on, gamma_l) and _eq(delta_on, delta_l):
                    self._sensor_vk_ready = True
                    return True
                else:
                    return False
            except Exception:
                self._sensor_vk_ready = True
                return True
        except Exception as e:
            logger.warning(f"Unable to read verifier key state: {e}")
            return False

    if _orig_sensor_vk_check is not None:
        HybridBlockchainHandler._sensor_verifier_is_set = _patched_sensor_verifier_is_set
except Exception:
    pass

    def _submit_prediction_proof_to_blockchain(self,
                                               data_proof_id_onchain: int,
                                               prediction_hash: str,
                                               model_commitment: bytes,
                                               prediction_value: int,
                                               confidence_value: int,
                                               proof_data: Dict) -> Dict:
        try:
            if not self._ensure_prediction_verifier_key():
                return {'success': False, 'error': 'prediction_verifier_key_not_configured'}

            proof = proof_data['proof']
            public_inputs = proof_data['publicInputs']

            if 'pi_a' in proof:
                a = [int(proof['pi_a'][0]), int(proof['pi_a'][1])]
                b_native = [[int(proof['pi_b'][0][0]), int(proof['pi_b'][0][1])],
                            [int(proof['pi_b'][1][0]), int(proof['pi_b'][1][1])]]
                c = [int(proof['pi_c'][0]), int(proof['pi_c'][1])]
            else:
                a = [int(proof['a'][0]), int(proof['a'][1])]
                b_native = [[int(proof['b'][0][0]), int(proof['b'][0][1])],
                            [int(proof['b'][1][0]), int(proof['b'][1][1])]]
                c = [int(proof['c'][0]), int(proof['c'][1])]

            # Decide B order: if adapter is configured on-chain, send precompile order (swapped) 
            use_adapter = False
            # Unified verifier swaps G2 internally, ancak bazı snarkjs çıktılarında
            # b dizisi ters eksen ile gelebilir. Önden native dene, başarısızsa swap dene.
            def _swap_b(bpt):
                try:
                    return [[int(bpt[0][1]), int(bpt[0][0])], [int(bpt[1][1]), int(bpt[1][0])]]
                except Exception:
                    return bpt
            b_candidates = [b_native, _swap_b(b_native)]
            b = b_candidates[0]

            public_inputs_int = [int(x) for x in public_inputs]
            # After making prediction/confidence private, circuit exposes exactly 3 public inputs
            if len(public_inputs_int) > 3:
                public_inputs_int = public_inputs_int[:3]

            # 🐛 DEBUG: Print public inputs for validation
            print(f"\n🔍 PREDICTION PROOF DEBUG:")
            print(f"   📊 dataProofId={data_proof_id_onchain}")
            print(f"   🎯 prediction={prediction_value}")
            print(f"   📈 confidence={confidence_value}")
            print(f"   🔐 publicInputs count: {len(public_inputs_int)}")
            print(f"   📋 publicInputs values: {public_inputs_int}")
            print(f"   ✅ Expected: [dataProofId={data_proof_id_onchain}, modelHash, timestamp]")
            print(f"   🔍 Proof a={a}")
            print(f"   🔍 Proof b={b}")
            print(f"   🔍 Proof c={c}")

            # Adapter pre-verify kaldırıldı; Unified üzerinden doğrudan gönderilir

            nonce = self.web3.eth.get_transaction_count(self.admin_account, 'pending')
            # Ön-simülasyon ve gas tahmini
            # Önce mevcut b ile dene; Invalid proof olursa swap ile tekrar dene
            def _estimate_with_b(bpt):
                return self.pdm_contract.functions.submitPredictionProof(
                    int(data_proof_id_onchain),
                    bytes.fromhex(prediction_hash[2:]),
                    model_commitment,
                    int(prediction_value),
                    int(confidence_value),
                    [a[0], a[1]],
                    [[bpt[0][0], bpt[0][1]], [bpt[1][0], bpt[1][1]]],
                    [c[0], c[1]],
                    public_inputs_int
                ).estimate_gas({'from': self.admin_account})

            sim_ok = False
            sim_err_reason = None
            for b_try in b_candidates:
                try:
                    _ = _estimate_with_b(b_try)
                    b = b_try
                    sim_ok = True
                    break
                except Exception as sim_err:
                    sim_err_reason = self._extract_revert_reason(sim_err)
                    # Sadece invalid proof/revert gibi hatalarda sonraki b denenir
                    continue
            if not sim_ok:
                logger.error(f"❌ Prediction tx simulation failed: {sim_err_reason}")
                return {'success': False, 'error': f'simulation_failed: {sim_err_reason}'}
            
            tx = self.pdm_contract.functions.submitPredictionProof(
                int(data_proof_id_onchain),
                bytes.fromhex(prediction_hash[2:]),
                model_commitment,
                int(prediction_value),
                int(confidence_value),
                [a[0], a[1]],
                [[b[0][0], b[0][1]], [b[1][0], b[1][1]]],
                [c[0], c[1]],
                public_inputs_int
            ).build_transaction({
                'from': self.admin_account,
                'nonce': nonce,
                'gas': getattr(BlockchainConfig, 'PREDICTION_GAS_LIMIT', 800000),
                'gasPrice': self._get_gas_price()
            })

            try:
                self.pdm_contract.functions.submitPredictionProof(
                    int(data_proof_id_onchain),
                    bytes.fromhex(prediction_hash[2:]),
                    model_commitment,
                    int(prediction_value),
                    int(confidence_value),
                    [a[0], a[1]],
                    [[b[0][0], b[0][1]], [b[1][0], b[1][1]]],
                    [c[0], c[1]],
                    public_inputs_int
                ).call({'from': self.admin_account})
            except Exception as call_error:
                logger.warning(f"❌ Call failed (prediction): {call_error}")

            signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            # logger.info(f"✅ Prediction proof Transaction sent: {tx_hash.hex()}")

            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=BlockchainConfig.TRANSACTION_TIMEOUT)
            if receipt.status == 1:
                proof_id = self._extract_proof_id_from_receipt(receipt)
                return {
                    'success': True,
                    'proof_id': proof_id,
                    'tx_hash': tx_hash.hex(),
                    'block_number': receipt.blockNumber,
                    'gas_used': receipt.gasUsed
                }
            else:
                return {'success': False, 'error': f'Transaction failed - Status: {receipt.status}'}
        except Exception as e:
            logger.error(f"Prediction proof submission error: {e}")
            return {'success': False, 'error': str(e)}

# Test
if __name__ == "__main__":
    # Test hybrid handler
    handler = HybridBlockchainHandler()
    
    # Test sensor data submission
    test_prediction_data = {
        'air_temp': 288.2,
        'process_temp': 309.7,
        'rotation_speed': 1552,
        'torque': 42,
        'tool_wear': 0,
        'machine_type': 'M',
        'prediction': 0,
        'probability': 0.15
    }
    
    result = handler.submit_sensor_data_hybrid(test_prediction_data)
    print(f"✅ Sensor submission result: {result}")
    
    if result['success']:
        # Test data retrieval
        data_id = result['local_data_id']
        retrieved_data = handler.retrieve_sensor_data(data_id)
        
        # Dönen verinin liste mi yoksa tek bir nesne mi olduğunu kontrol ederek hatayı gider
        record_to_check = None
        if isinstance(retrieved_data, list) and retrieved_data:
            # Eğer liste dönerse ve boş değilse, ilk elemanı al
            record_to_check = retrieved_data[0]
        elif hasattr(retrieved_data, 'machine_id'):
            # Eğer doğrudan SensorData nesnesi dönerse, onu kullan
            record_to_check = retrieved_data

        if record_to_check:
            # record_to_check'in artık güvenli bir şekilde bir nesne olduğu varsayılabilir.
            print(f"✅ Retrieved data: Machine {record_to_check.machine_id}, Temp {record_to_check.air_temperature}K")
            
            # Test integrity
            integrity_ok = handler.verify_data_integrity(data_id, result['data_hash'])
            print(f"✅ Data integrity: {'✅ Valid' if integrity_ok else '❌ Invalid'}")
        else:
            # Veri alınamadıysa veya format yanlışsa
            print(f"❌ Retrieved data is empty or in unexpected format: {retrieved_data}")

    # System stats
    stats = handler.get_system_statistics()
    print(f"✅ System stats: {json.dumps(stats, indent=2)}")
