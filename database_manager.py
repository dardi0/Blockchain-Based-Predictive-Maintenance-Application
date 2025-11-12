#!/usr/bin/env python3
"""
PdMDatabase Manager - Sensör verilerini SQLite'a kaydetme ve sorgulama
"""

import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, getcontext, InvalidOperation
from dataclasses import dataclass
import json

@dataclass
class SensorData:
    """Sensör verisi data class"""
    id: Optional[int] = None
    machine_id: Optional[int] = None
    timestamp: int = 0
    air_temp: float = 0.0
    process_temp: float = 0.0
    rotation_speed: int = 0
    torque: float = 0.0
    tool_wear: int = 0
    machine_type: str = "M"
    prediction: Optional[int] = None
    prediction_probability: Optional[float] = None
    prediction_reason: Optional[str] = None
    analysis_time: Optional[float] = None
    blockchain_success: bool = False
    blockchain_tx_hash: Optional[str] = None
    created_at: Optional[str] = None

class PdMDatabaseManager:
    """PdMDatabase SQLite manager sınıfı"""
    
    def __init__(self, db_path: str = "PdMDatabase/PdMDatabase"):
        """Database manager başlat"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Database'i başlat
        self._initialize_database()
        print(f"PdM Database Manager hazır: {self.db_path}")
    
    def _initialize_database(self):
        """Database ve tabloları oluştur"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Sensor data tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id INTEGER,
                timestamp INTEGER NOT NULL,
                air_temp REAL NOT NULL,
                process_temp REAL NOT NULL,
                rotation_speed INTEGER NOT NULL,
                torque REAL NOT NULL,
                tool_wear INTEGER NOT NULL,
                machine_type TEXT NOT NULL DEFAULT 'M',
                prediction INTEGER,
                prediction_probability REAL,
                prediction_reason TEXT,
                analysis_time REAL,
                data_hash TEXT,
                offchain_data_hash TEXT,
                tx_hash TEXT,
                zk_proof_hash TEXT,
                blockchain_success BOOLEAN DEFAULT 0,
                blockchain_tx_hash TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index'ler
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON sensor_data(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_machine_id ON sensor_data(machine_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prediction ON sensor_data(prediction)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_machine_type ON sensor_data(machine_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blockchain_success ON sensor_data(blockchain_success)")
        
        conn.commit()

        # Şema uyumluluğu: eksik kolonları ekle (eski DB'lerde kırılmayı önlemek için)
        try:
            cursor.execute("PRAGMA table_info(sensor_data)")
            existing_cols = {row[1] for row in cursor.fetchall()}

            # Hedef opsiyonel kolonlar ve tipleri
            desired = [
                ("data_hash", "TEXT"),
                ("offchain_data_hash", "TEXT"),
                ("tx_hash", "TEXT"),
                ("zk_proof_hash", "TEXT"),
                ("blockchain_success", "BOOLEAN DEFAULT 0"),
                ("blockchain_tx_hash", "TEXT"),
                ("blockchain_proof_id", "INTEGER")
            ]
            for col, coltype in desired:
                if col not in existing_cols:
                    try:
                        cursor.execute(f"ALTER TABLE sensor_data ADD COLUMN {col} {coltype}")
                    except Exception:
                        # Aynı anda birden fazla süreç ALTER yapmaya çalışırsa sessiz geç
                        pass
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()
    
    def save_sensor_data(self, sensor_data: Dict) -> int:
        """
        Sensör verisini database'e kaydet
        
        Args:
            sensor_data: Sensör verisi dict'i
            
        Returns:
            int: Kaydedilen record'un ID'si
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            # Machine ID oluştur (eğer yoksa)
            machine_id = sensor_data.get('machine_id', int(time.time()) % 10000)
            
            cursor.execute("""
                INSERT INTO sensor_data (
                    machine_id, timestamp, air_temp, process_temp, rotation_speed,
                    torque, tool_wear, machine_type, prediction, prediction_probability,
                    prediction_reason, analysis_time, blockchain_success, blockchain_tx_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                machine_id,
                sensor_data.get('timestamp', int(time.time())),
                sensor_data['air_temp'],
                sensor_data['process_temp'],
                sensor_data['rotation_speed'],
                sensor_data['torque'],
                sensor_data['tool_wear'],
                sensor_data['machine_type'],
                sensor_data.get('prediction'),
                sensor_data.get('prediction_probability'),
                sensor_data.get('prediction_reason'),
                sensor_data.get('analysis_time'),
                sensor_data.get('blockchain_success', False),
                sensor_data.get('blockchain_tx_hash')
            ))
            
            record_id = cursor.lastrowid
            conn.commit()
            
            print(f"✅ Sensör verisi kaydedildi - ID: {record_id}")
            return record_id
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Database kayıt hatası: {e}")
            raise
        finally:
            conn.close()
    
    def get_sensor_data(self, record_id: int = None, limit: int = 10, 
                       prediction_filter: str = None, machine_type_filter: str = None,
                       blockchain_filter: str = None, start_date: str = None, 
                       end_date: str = None) -> List[Dict]:
        """
        Sensör verilerini getir (filtreleme ile)
        
        Args:
            record_id: Specific record ID (opsiyonel)
            limit: Maximum kayıt sayısı
            prediction_filter: "Normal", "Arıza", None
            machine_type_filter: "L", "M", "H", None
            blockchain_filter: "Başarılı", "Başarısız", None
            start_date: Başlangıç tarihi (YYYY-MM-DD formatında)
            end_date: Bitiş tarihi (YYYY-MM-DD formatında)
            
        Returns:
            List[Dict]: Sensör verileri listesi
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Dict-like access
        cursor = conn.cursor()
        
        try:
            if record_id:
                cursor.execute("SELECT * FROM sensor_data WHERE id = ?", (record_id,))
                result = cursor.fetchone()
                return [dict(result)] if result else []
            else:
                # SQL sorgusu oluştur
                query = "SELECT * FROM sensor_data WHERE 1=1"
                params = []
                
                # Filtreleri ekle
                if prediction_filter == "Normal":
                    query += " AND prediction = 0"
                elif prediction_filter == "Arıza":
                    query += " AND prediction = 1"
                
                if machine_type_filter and machine_type_filter in ["L", "M", "H"]:
                    query += " AND machine_type = ?"
                    params.append(machine_type_filter)
                
                if blockchain_filter == "Başarılı":
                    query += " AND blockchain_success = 1"
                elif blockchain_filter == "Başarısız":
                    query += " AND blockchain_success = 0"
                
                # Tarih filtreleri
                if start_date:
                    query += " AND DATE(created_at) >= ?"
                    params.append(start_date)
                
                if end_date:
                    query += " AND DATE(created_at) <= ?"
                    params.append(end_date)
                
                # Sıralama ve limit – en yeni kayıttan en eskiye (son tahminden ilkine)
                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                return [dict(row) for row in results]
                
        except Exception as e:
            print(f"❌ Database sorgu hatası: {e}")
            return []
        finally:
            conn.close()

    # ----- FORMATLAMA & DÖNÜŞÜM YARDIMCILARI -----
    def _safe_percent(self, value) -> str:
        """Probability değerini Decimal ile yüzde formatına çevirir (%.2f)."""
        try:
            if value is None:
                return 'N/A'
            # bytes → float
            if isinstance(value, (bytes, bytearray)):
                import struct
                if len(value) == 8:
                    value = struct.unpack('d', value)[0]
                elif len(value) == 4:
                    value = struct.unpack('f', value)[0]
                else:
                    return f"Binary({len(value)} bytes)"
            # str/float/int → Decimal
            dec = Decimal(str(value))
            percent = (dec * Decimal('100')).quantize(Decimal('0.01'))
            return f"{percent}%"
        except (InvalidOperation, ValueError):
            return f"Raw: {value}"

    def format_record(self, record: Dict) -> Dict:
        """GUI-agnostik biçimde tek bir kaydı kullanıcı dostu alanlarla zenginleştirir."""
        from datetime import datetime
        created_at = record.get('created_at', '')
        try:
            dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            time_str = dt.strftime('%d.%m.%Y %H:%M:%S')
        except Exception:
            time_str = created_at or 'N/A'

        prediction = record.get('prediction')
        pred_text = 'Arıza' if prediction == 1 else 'Normal' if prediction == 0 else 'N/A'

        prob_text = self._safe_percent(record.get('prediction_probability'))

        reason = record.get('prediction_reason', '') or ''
        reason_short = (reason[:20] + '...') if len(reason) > 20 else reason

        analysis_time = record.get('analysis_time')
        analysis_text = f"{analysis_time:.4f}s" if isinstance(analysis_time, (int, float)) else 'N/A'

        bc_success = bool(record.get('blockchain_success', False))
        bc_text = '✅' if bc_success else '❌'

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
            'prediction': prediction
        }
    
    def get_statistics(self) -> Dict:
        """Database istatistikleri"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            # Toplam kayıt sayısı
            cursor.execute("SELECT COUNT(*) FROM sensor_data")
            total_records = cursor.fetchone()[0]
            
            # Arıza tahmini dağılımı
            cursor.execute("""
                SELECT prediction, COUNT(*) as count 
                FROM sensor_data 
                WHERE prediction IS NOT NULL 
                GROUP BY prediction
            """)
            prediction_dist = dict(cursor.fetchall())
            
            # Makine tipi dağılımı
            cursor.execute("""
                SELECT machine_type, COUNT(*) as count 
                FROM sensor_data 
                GROUP BY machine_type
            """)
            machine_type_dist = dict(cursor.fetchall())
            
            # Son kayıt zamanı
            cursor.execute("SELECT MAX(created_at) FROM sensor_data")
            last_record = cursor.fetchone()[0]
            
            return {
                'total_records': total_records,
                'prediction_distribution': prediction_dist,
                'machine_type_distribution': machine_type_dist,
                'last_record_time': last_record
            }
            
        except Exception as e:
            print(f"❌ İstatistik hatası: {e}")
            return {}
        finally:
            conn.close()

    # ----- GÜNCELLEME YARDIMCILARI -----
    def update_blockchain_info(self, record_id, success, tx_hash=None, proof_id=None, offchain_hash=None) -> bool:
        """Belirli bir sensör kaydı için blockchain alanlarını günceller.
        Eski şemalarda eksik kolonları otomatik atlayarak güvenli günceller.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        try:
            # Var olan kolonları al
            cursor.execute("PRAGMA table_info(sensor_data)")
            cols = {row[1] for row in cursor.fetchall()}

            set_parts = []
            params = []

            if 'blockchain_success' in cols:
                set_parts.append("blockchain_success = ?")
                params.append(1 if success else 0)

            if proof_id is not None and 'blockchain_proof_id' in cols:
                set_parts.append("blockchain_proof_id = ?")
                params.append(int(proof_id))

            if tx_hash:
                if 'blockchain_tx_hash' in cols:
                    set_parts.append("blockchain_tx_hash = ?")
                    params.append(tx_hash)
                if 'tx_hash' in cols:
                    set_parts.append("tx_hash = ?")
                    params.append(tx_hash)

            if offchain_hash:
                if 'zk_proof_hash' in cols:
                    set_parts.append("zk_proof_hash = ?")
                    params.append(offchain_hash)
                if 'offchain_data_hash' in cols:
                    set_parts.append("offchain_data_hash = ?")
                    params.append(offchain_hash)

            if not set_parts:
                conn.close()
                return True

            params.append(record_id)
            sql = f"UPDATE sensor_data SET {', '.join(set_parts)} WHERE id = ?"
            cursor.execute(sql, params)
            conn.commit()
            return True
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"⚠️ Blockchain info update error (manager): {e}")
            return False
        finally:
            conn.close()

    def search_by_prediction(self, prediction: int, limit: int = 50) -> List[Dict]:
        """Tahmin sonucuna göre ara"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM sensor_data 
                WHERE prediction = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (prediction, limit))
            
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
        except Exception as e:
            print(f"❌ Arama hatası: {e}")
            return []
        finally:
            conn.close()

def test_database_manager():
    """Database manager test"""
    print("🧪 PdM Database Manager Test")
    
    db_manager = PdMDatabaseManager()
    
    # Test verisi
    test_data = {
        'air_temp': 298.5,
        'process_temp': 308.2,
        'rotation_speed': 1500,
        'torque': 42.3,
        'tool_wear': 180,
        'machine_type': 'M',
        'prediction': 1,
        'prediction_probability': 0.85,
        'prediction_reason': 'LSTM-CNN Model',
        'analysis_time': 2.45,
        'blockchain_success': True,
        'blockchain_tx_hash': '0x1234567890abcdef'
    }
    
    # Kayıt test
    record_id = db_manager.save_sensor_data(test_data)
    print(f"📝 Test kaydı oluşturuldu - ID: {record_id}")
    
    # Getir test
    records = db_manager.get_sensor_data(limit=5)
    print(f"📊 Son {len(records)} kayıt getirildi")
    
    # İstatistik test
    stats = db_manager.get_statistics()
    print(f"📈 İstatistikler: {json.dumps(stats, indent=2)}")
    
    print("✅ Database manager test tamamlandı!")

if __name__ == "__main__":
    test_database_manager()
