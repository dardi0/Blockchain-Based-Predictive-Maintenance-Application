"""
Hibrit PDM Sistemi - Local Database Storage Manager
Off-chain veri saklama ve ZK-SNARK proof generation
"""

import sqlite3
import json
import time
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from real_poseidon_utils import RealPoseidonHasher

# Logging setup (INFO, WARNING, ERROR açık)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

@dataclass
class SensorData:
    """AI4I2020 sensör verisi yapısı"""
    machine_id: int
    air_temperature: float      # Kelvin
    process_temperature: float  # Kelvin  
    rotational_speed: int       # rpm
    torque: float              # Nm
    tool_wear: int             # minutes
    machine_type: str          # L/M/H
    timestamp: int
    submitter: str
    data_id: Optional[int] = None
    
@dataclass
class PredictionData:
    """Model tahmin verisi yapısı"""
    data_id: int
    prediction: int            # 0 or 1
    probability: float         # 0.0 - 1.0
    model_version: str
    model_hash: str
    predictor: str
    timestamp: int
    prediction_id: Optional[int] = None
    
@dataclass
class MaintenanceData:
    """Bakım görevi verisi yapısı"""
    prediction_id: int
    task_description: str
    assigned_engineer: str
    created_at: int
    completed_at: Optional[int] = None
    completion_notes: Optional[str] = None
    is_completed: bool = False
    task_id: Optional[int] = None

class LocalStorageManager:
    """Local SQLite database yöneticisi"""
    
    def __init__(self, db_path: str = "pdm_hybrid_storage.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.poseidon_hasher = RealPoseidonHasher()
        self._init_database()
        
    def _init_database(self):
        """Database ve tabloları oluştur"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Sensor data tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hash TEXT UNIQUE NOT NULL,
                    machine_id INTEGER NOT NULL,
                    air_temperature REAL NOT NULL,
                    process_temperature REAL NOT NULL,
                    rotational_speed INTEGER NOT NULL,
                    torque REAL NOT NULL,
                    tool_wear INTEGER NOT NULL,
                    machine_type TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    submitter TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    blockchain_proof_id INTEGER,
                    is_verified BOOLEAN DEFAULT FALSE,
                    offchain_data_hash TEXT,
                    tx_hash TEXT,
                    zk_proof_hash TEXT
                )
            ''')
            
            # Prediction data tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prediction_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_hash TEXT UNIQUE NOT NULL,
                    data_id INTEGER NOT NULL,
                    prediction INTEGER NOT NULL,
                    probability REAL NOT NULL,
                    model_version TEXT NOT NULL,
                    model_hash TEXT NOT NULL,
                    predictor TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    blockchain_proof_id INTEGER,
                    is_verified BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (data_id) REFERENCES sensor_data (id)
                )
            ''')
            
            # Maintenance data tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS maintenance_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_hash TEXT UNIQUE NOT NULL,
                    prediction_id INTEGER NOT NULL,
                    task_description TEXT NOT NULL,
                    assigned_engineer TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    completion_notes TEXT,
                    is_completed BOOLEAN DEFAULT FALSE,
                    blockchain_proof_id INTEGER,
                    is_verified BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (prediction_id) REFERENCES prediction_data (id)
                )
            ''')
            
            # ZK proof metadata tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS zk_proof_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proof_hash TEXT UNIQUE NOT NULL,
                    proof_type TEXT NOT NULL,
                    related_id INTEGER NOT NULL,
                    public_inputs TEXT NOT NULL,
                    proof_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    blockchain_tx_hash TEXT,
                    is_submitted BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Indexler oluştur
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_machine_id ON sensor_data(machine_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_data(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_prediction_data_id ON prediction_data(data_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_maintenance_prediction_id ON maintenance_data(prediction_id)')
            
            conn.commit()
            # logger.info(f"✅ Database initialized: {self.db_path}")
    
    def store_sensor_data(self, sensor_data: SensorData) -> Tuple[int, str]:
        """
        Sensör verisini local DB'ye kaydet ve hash döner
        
        Returns:
            (data_id, data_hash)
        """
        # Data hash hesapla
        # Data hash hesapla (GERÇEK Poseidon)
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
            logger.error(f"Poseidon hash failed in storage manager: {e}")
            raise
        # Poseidon hash'i doğrudan kaydet (ek ölçekleme gerekmez)
        data_hash = self.poseidon_hasher.poseidon_to_hex(poseidon_result)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO sensor_data (
                        data_hash, machine_id, air_temperature, process_temperature,
                        rotational_speed, torque, tool_wear, machine_type,
                        timestamp, submitter
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data_hash, sensor_data.machine_id, sensor_data.air_temperature,
                    sensor_data.process_temperature, sensor_data.rotational_speed,
                    sensor_data.torque, sensor_data.tool_wear, sensor_data.machine_type,
                    sensor_data.timestamp, sensor_data.submitter
                ))
                
                data_id = cursor.lastrowid
                conn.commit()
                
                # logger.info(f"✅ Sensor data stored: ID={data_id}, Hash={data_hash[:16]}...")
                return data_id, data_hash
                
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    # Hash zaten mevcut, mevcut ID'yi döner
                    cursor.execute('SELECT id FROM sensor_data WHERE data_hash = ?', (data_hash,))
                    existing_id = cursor.fetchone()[0]
                    logger.warning(f"✅ Sensor data already exists: ID={existing_id}")
                    return existing_id, data_hash
                else:
                    raise
    
    def store_prediction_data(self, prediction_data: PredictionData) -> Tuple[int, str]:
        """
        Tahmin verisini local DB'ye kaydet ve hash döner
        """
        # Prediction hash hesapla (GERÇEK Poseidon)
        model_version_hash = self.poseidon_hasher.string_to_field_element(prediction_data.model_version)
        probability_int = int(prediction_data.probability * 10000)  # 0.9876 -> 9876
        poseidon_result = self.poseidon_hasher.hash_prediction_data(
            prediction_data.data_id,
            prediction_data.prediction,
            probability_int,
            model_version_hash,
            prediction_data.timestamp
        )
        prediction_hash = self.poseidon_hasher.poseidon_to_hex(poseidon_result)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO prediction_data (
                        prediction_hash, data_id, prediction, probability,
                        model_version, model_hash, predictor, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    prediction_hash, prediction_data.data_id, prediction_data.prediction,
                    prediction_data.probability, prediction_data.model_version,
                    prediction_data.model_hash, prediction_data.predictor,
                    prediction_data.timestamp
                ))
                
                prediction_id = cursor.lastrowid
                conn.commit()
                
                # logger.info(f"✅ Prediction data stored: ID={prediction_id}, Hash={prediction_hash[:16]}...")
                return prediction_id, prediction_hash
                
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    cursor.execute('SELECT id FROM prediction_data WHERE prediction_hash = ?', (prediction_hash,))
                    existing_id = cursor.fetchone()[0]
                    logger.warning(f"✅ Prediction data already exists: ID={existing_id}")
                    return existing_id, prediction_hash
                else:
                    raise
    
    def store_maintenance_data(self, maintenance_data: MaintenanceData) -> Tuple[int, str]:
        """
        Bakım verisini local DB'ye kaydet ve hash döner
        """
        # Maintenance hash hesapla (GERÇEK Poseidon)
        task_type_int = {"preventive": 1, "corrective": 2, "emergency": 3}.get(maintenance_data.task_type, 1)
        priority_int = {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(maintenance_data.priority, 2)
        poseidon_result = self.poseidon_hasher.hash_maintenance_data(
            maintenance_data.prediction_id,
            task_type_int,
            priority_int,
            maintenance_data.timestamp
        )
        task_hash = self.poseidon_hasher.poseidon_to_hex(poseidon_result)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO maintenance_data (
                        task_hash, prediction_id, task_description, assigned_engineer,
                        created_at, completed_at, completion_notes, is_completed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_hash, maintenance_data.prediction_id, maintenance_data.task_description,
                    maintenance_data.assigned_engineer, maintenance_data.created_at,
                    maintenance_data.completed_at, maintenance_data.completion_notes,
                    maintenance_data.is_completed
                ))
                
                task_id = cursor.lastrowid
                conn.commit()
                
                # logger.info(f"✅ Maintenance data stored: ID={task_id}, Hash={task_hash[:16]}...")
                return task_id, task_hash
                
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    cursor.execute('SELECT id FROM maintenance_data WHERE task_hash = ?', (task_hash,))
                    existing_id = cursor.fetchone()[0]
                    logger.warning(f"✅ Maintenance data already exists: ID={existing_id}")
                    return existing_id, task_hash
                else:
                    raise
    
    def get_sensor_data(self, data_id: int) -> Optional[SensorData]:
        """ID ile sensör verisi getir"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sensor_data WHERE id = ?', (data_id,))
            row = cursor.fetchone()
            
            if row:
                return SensorData(
                    data_id=row[0],
                    machine_id=row[2],
                    air_temperature=row[3],
                    process_temperature=row[4],
                    rotational_speed=row[5],
                    torque=row[6],
                    tool_wear=row[7],
                    machine_type=row[8],
                    timestamp=row[9],
                    submitter=row[10]
                )
            return None
    
    def get_sensor_data_by_hash(self, data_hash: str) -> Optional[SensorData]:
        """Hash ile sensör verisi getir"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM sensor_data WHERE data_hash = ?', (data_hash,))
            row = cursor.fetchone()
            
            if row:
                return SensorData(
                    data_id=row[0],
                    machine_id=row[2],
                    air_temperature=row[3],
                    process_temperature=row[4],
                    rotational_speed=row[5],
                    torque=row[6],
                    tool_wear=row[7],
                    machine_type=row[8],
                    timestamp=row[9],
                    submitter=row[10]
                )
            return None
    
    def get_prediction_data(self, prediction_id: int) -> Optional[PredictionData]:
        """ID ile tahmin verisi getir"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM prediction_data WHERE id = ?', (prediction_id,))
            row = cursor.fetchone()
            
            if row:
                return PredictionData(
                    prediction_id=row[0],
                    data_id=row[2],
                    prediction=row[3],
                    probability=row[4],
                    model_version=row[5],
                    model_hash=row[6],
                    predictor=row[7],
                    timestamp=row[8]
                )
            return None
    
    def get_machine_sensor_data(self, machine_id: int, limit: int = 100) -> List[SensorData]:
        """Makineye ait sensör verilerini getir"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM sensor_data 
                WHERE machine_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (machine_id, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append(SensorData(
                    data_id=row[0],
                    machine_id=row[2],
                    air_temperature=row[3],
                    process_temperature=row[4],
                    rotational_speed=row[5],
                    torque=row[6],
                    tool_wear=row[7],
                    machine_type=row[8],
                    timestamp=row[9],
                    submitter=row[10]
                ))
            return results
    
    def update_blockchain_proof_id(self, table_name, local_id, proof_id, tx_hash=None):
        """Update blockchain metadata for a stored record (schema-aware)."""
        valid_tables = {"sensor_data", "prediction_data", "maintenance_data"}
        if table_name not in valid_tables:
            raise ValueError(f"Unsupported table for blockchain update: {table_name}")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if table_name == "sensor_data":
                # Check available columns
                cursor.execute('PRAGMA table_info(sensor_data)')
                cols = {row[1] for row in cursor.fetchall()}
                if 'tx_hash' in cols and tx_hash:
                    cursor.execute(
                        """
                        UPDATE sensor_data
                        SET blockchain_proof_id=?, tx_hash=?
                        WHERE id=?
                        """,
                        (proof_id, tx_hash, local_id),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE sensor_data
                        SET blockchain_proof_id=?
                        WHERE id=?
                        """,
                        (proof_id, local_id),
                    )
            else:
                cursor.execute(
                    f"""
                    UPDATE {table_name}
                    SET blockchain_proof_id=?
                    WHERE id=?
                    """,
                    (proof_id, local_id),
                )
            conn.commit()

        log_msg = f"Updated {table_name} ID={local_id} with blockchain proof ID={proof_id}"
        if tx_hash and table_name == "sensor_data":
            log_msg += f" and tx_hash={tx_hash}"
        # logger.info(log_msg)

    def get_statistics(self) -> Dict[str, int]:
        """Database istatistikleri"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Sensor data count
            cursor.execute('SELECT COUNT(*) FROM sensor_data')
            stats['sensor_data_count'] = cursor.fetchone()[0]
            
            # Prediction data count
            cursor.execute('SELECT COUNT(*) FROM prediction_data')
            stats['prediction_data_count'] = cursor.fetchone()[0]
            
            # Maintenance data count
            cursor.execute('SELECT COUNT(*) FROM maintenance_data')
            stats['maintenance_data_count'] = cursor.fetchone()[0]
            
            # Verified data count
            cursor.execute('SELECT COUNT(*) FROM sensor_data WHERE is_verified = TRUE')
            stats['verified_sensor_count'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM prediction_data WHERE is_verified = TRUE')
            stats['verified_prediction_count'] = cursor.fetchone()[0]
            
            return stats
    
    def cleanup_old_data(self, days_old: int = 30):
        """Eski verileri temizle (opsiyonel)"""
        cutoff_timestamp = int(time.time()) - (days_old * 24 * 60 * 60)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Sadece verify edilmemiş eski verileri sil
            cursor.execute('''
                DELETE FROM sensor_data 
                WHERE timestamp < ? AND is_verified = FALSE
            ''', (cutoff_timestamp,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"✅ Cleaned up {deleted_count} old unverified records")
            return deleted_count

# Test fonksiyonu
if __name__ == "__main__":
    # Test storage manager
    storage = LocalStorageManager("test_pdm.db")
    
    # Test sensor data
    # Varsayılan adresi dinamik belirle
    try:
        from utils.address_utils import get_default_address
        _default_submitter = get_default_address()
    except Exception:
        _default_submitter = "0x0000000000000000000000000000000000000000"

    sensor_data = SensorData(
        machine_id=1001,
        air_temperature=298.1,
        process_temperature=308.6,
        rotational_speed=1551,
        torque=42.8,
        tool_wear=0,
        machine_type="M",
        timestamp=int(time.time()),
        submitter=_default_submitter
    )
    
    data_id, data_hash = storage.store_sensor_data(sensor_data)
    print(f"✅ Stored sensor data: ID={data_id}, Hash={data_hash[:16]}...")
    
    # Retrieve test
    retrieved = storage.get_sensor_data(data_id)
    print(f"✅ Retrieved: Machine ID={retrieved.machine_id}, Temp={retrieved.air_temperature}")
    
    # Stats test
    stats = storage.get_statistics()
    print(f"✅ Stats: {stats}")
