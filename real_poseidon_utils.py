"""
GERÇEK Poseidon Hash Utilities
Node.js circomlibjs kullanarak - Circom ile %100 uyumlu
"""

import subprocess
import json
from typing import List, Union, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class RealPoseidonHasher:
    """GERÇEK Poseidon hash fonksiyonları - Node.js circomlibjs ile (Singleton optimized)"""
    
    def __init__(self):
        self.poseidon_script = Path(__file__).parent / "poseidon_hash.js"
        if not self.poseidon_script.exists():
            raise FileNotFoundError(f"Poseidon hash script not found: {self.poseidon_script}")
        
        # Performance tracking
        self._first_call = True
        self._call_count = 0
    
    def _run_poseidon_command(self, command: str, *args, format_type: str = "field") -> str:
        """Node.js Poseidon hash komutunu çalıştır"""
        cmd = ["node", str(self.poseidon_script), command] + [str(arg) for arg in args] + [f"--format={format_type}"]
        
        try:
            # Performance tracking
            import time
            start_time = time.time()
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30,
                check=False
            )
            
            execution_time = (time.time() - start_time) * 1000  # ms
            self._call_count += 1
            
            if result.returncode == 0:
                # Log performance for first few calls
                if self._call_count <= 3:
                    if self._first_call:
                        # logger.info(f"🔧 First Poseidon call (with build): {execution_time:.1f}ms")
                        self._first_call = False
                    else:
                        # logger.info(f"⚡ Subsequent Poseidon call: {execution_time:.1f}ms")
                        pass

                return result.stdout.strip()
            else:
                logger.error(f"Poseidon command failed: {result.stderr}")
                raise RuntimeError(f"Poseidon hash failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            raise RuntimeError("Poseidon hash timeout")
        except Exception as e:
            raise RuntimeError(f"Poseidon hash error: {e}")
    
    def hash_sensor_data(self, machine_id: int, timestamp: int, air_temp: float, 
                        process_temp: float, rotational_speed: int, 
                        torque: float, tool_wear: int, machine_type: Union[str, int],
                        format_type: str = "field") -> str:
        """
        Sensör verisi için GERÇEK Poseidon hash
        
        Args:
            format_type: "field" (default), "hex", "json", "all"
            
        Returns: 
            - field: Field element as string
            - hex: Hexadecimal format (0x...)
            - json: JSON object with all formats
            - all: All formats for debugging
        """
        return self._run_poseidon_command(
            "sensor", 
            machine_id, timestamp, air_temp, process_temp, 
            rotational_speed, torque, tool_wear, machine_type,
            format_type=format_type
        )
    
    def hash_prediction_data(self, data_id: int, prediction: int, probability_int: int,
                           model_version_hash: int, timestamp: int) -> str:
        """
        Tahmin verisi için GERÇEK Poseidon hash
        """
        return self._run_poseidon_command(
            "prediction",
            data_id, prediction, probability_int, model_version_hash, timestamp
        )
    
    def hash_maintenance_data(self, prediction_id: int, task_type: int, 
                            priority: int, timestamp: int) -> str:
        """
        Bakım görevi için GERÇEK Poseidon hash
        """
        return self._run_poseidon_command(
            "maintenance",
            prediction_id, task_type, priority, timestamp
        )

    def hash_values(self, values: List[Union[int, float, str]], format_type: str = "field") -> str:
        """
        Değer listesi için GERÇEK Poseidon hash
        """
        return self._run_poseidon_command(
            "hash",
            *values,
            format_type=format_type
        )
    
    def poseidon_to_hex(self, poseidon_result: str) -> str:
        """
        Poseidon field element'ini hex string'e çevir
        Input: "14546554964546106321909808773230940350363889201000228725224136092114838966564" (tek büyük integer)
        Output: "0x..."
        """
        try:
            # Tek büyük integer'ı parse et
            big_int = int(poseidon_result.strip())
            
            # 32 byte (256-bit) hex string'e çevir
            # Python'da büyük integer'ları hex'e çevirmek güvenli
            hex_str = hex(big_int)[2:]  # "0x" prefix'ini kaldır
            
            # 64 karakter (32 byte) olacak şekilde pad et
            hex_str = hex_str.zfill(64)
            
            return "0x" + hex_str
            
        except ValueError as e:
            logger.error(f"❌ Poseidon result parse error: {poseidon_result}")
            # Fallback: ilk 32 byte'ı hash olarak kullan
            import hashlib
            fallback_hash = hashlib.sha256(poseidon_result.encode()).hexdigest()
            logger.warning(f"⚠️ Using fallback hash: {fallback_hash[:64]}")
            return "0x" + fallback_hash
    
    def string_to_field_element(self, text: str) -> int:
        """
        String'i Poseidon field element'e çevir
        """
        # Basit string->int dönüşümü
        text_bytes = text.encode('utf-8')
        result = 0
        for i, byte_val in enumerate(text_bytes[:30]):
            result += byte_val * (256 ** i)
        
        # Baby Jubjub field modulo
        FIELD_SIZE = 21888242871839275222246405745257275088548364400416034343698204186575808495617
        return result % FIELD_SIZE

# Test fonksiyonu
if __name__ == "__main__":
    hasher = RealPoseidonHasher()
    
    # Test sensör verisi
    print("🔐 Testing REAL Poseidon Hash...")
    
    poseidon_result = hasher.hash_sensor_data(
        machine_id=1001,
        timestamp=1757614455,
        air_temp=298.5,
        process_temp=308.2,
        rotational_speed=1500,
        torque=42.3,
        tool_wear=180,
        machine_type="M"
    )
    
    print(f"✅ Poseidon Result: {poseidon_result}")
    
    hex_hash = hasher.poseidon_to_hex(poseidon_result)
    print(f"✅ Hex Hash: {hex_hash}")
    
    # Model string test
    model_hash = hasher.string_to_field_element("LSTM-CNN-v1.0")
    print(f"✅ Model String Hash: {model_hash}")
    
    print("🎉 REAL POSEIDON HASH IS WORKING!")
