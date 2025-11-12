"""
ZK-SNARK Proof Generator for Hybrid PDM System
Sensör verisi, tahmin ve bakım verileri için ZK kanıtları oluşturur
"""

import json
import hashlib
import time
import subprocess
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import asdict

# Poseidon hash artık real_poseidon_utils.py'de

# Import storage manager
from hybrid_storage_manager import SensorData, PredictionData, MaintenanceData

# Logging yapılandırması (INFO, WARNING, ERROR açık)
# logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

class ZKProofGenerator:
    """ZK-SNARK proof oluşturucu sınıf"""
    
    def __init__(self, circuits_dir: str = "circuits/hybrid"):
        self.circuits_dir = Path(circuits_dir)
        # Use temp/zk_proofs in project directory
        self.temp_dir = Path("temp/zk_proofs")
        self._snarkjs_base_cmd: Optional[List[str]] = None
        self._snarkjs_not_found_logged = False
        self._no_window_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.circuits_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.sensor_circuit = self.circuits_dir / "sensor_data_proof.circom"
        self.prediction_circuit = self.circuits_dir / "prediction_proof.circom" 
        self.maintenance_circuit = self.circuits_dir / "maintenance_proof.circom"
        
        self._create_circuits()
    
    def _create_circuits(self):
        """ZK circuit dosyalarını oluştur"""
        
        sensor_circuit_code = '''
pragma circom 2.0.0;
include "circomlib/circuits/poseidon.circom";
include "circomlib/circuits/comparators.circom";

template SensorDataProof() {
    /* Public Inputs - Only metadata (3) */
    signal input machineId;
    signal input timestamp;
    signal input dataCommitment;  // Hash of sensor data (public for verification)

    /* Private Inputs - Actual sensor data (hidden from blockchain) */
    signal input airTemperature;   
    signal input processTemperature; 
    signal input rotationalSpeed;
    signal input torque;             
    signal input toolWear;
    signal input machineType;
    signal input nonce;

    /* Internal signals */
    signal validProof;
    signal commitmentHash;

    /* Exposed outputs (only metadata, count = 3) */
    signal output out_machineId;
    signal output out_timestamp;
    signal output out_dataCommitment;

    /* Constraints */
    // Compute hash of all sensor data (private)
    component hasher = Poseidon(6);
    hasher.inputs[0] <== airTemperature;
    hasher.inputs[1] <== processTemperature;
    hasher.inputs[2] <== rotationalSpeed;
    hasher.inputs[3] <== torque;
    hasher.inputs[4] <== toolWear;
    hasher.inputs[5] <== machineType;

    commitmentHash <== hasher.out;

    // CRITICAL: Verify the provided commitment matches computed hash
    // This proves we know the preimage (sensor values) of the commitment
    dataCommitment === commitmentHash;

    /* Map inputs to outputs (only public metadata) */
    out_machineId <== machineId;
    out_timestamp <== timestamp;
    out_dataCommitment <== dataCommitment;

    /* Validation constraints */
    component airTempCheck1 = GreaterEqThan(16);
    airTempCheck1.in[0] <== airTemperature;
    airTempCheck1.in[1] <== 29500;

    component airTempCheck2 = LessEqThan(16);
    airTempCheck2.in[0] <== airTemperature;
    airTempCheck2.in[1] <== 30500;

    component processTempCheck1 = GreaterEqThan(16);
    processTempCheck1.in[0] <== processTemperature;
    processTempCheck1.in[1] <== 30500;

    component processTempCheck2 = LessEqThan(16);
    processTempCheck2.in[0] <== processTemperature;
    processTempCheck2.in[1] <== 31500;

    component speedCheck1 = GreaterEqThan(12);
    speedCheck1.in[0] <== rotationalSpeed;
    speedCheck1.in[1] <== 1000;

    component speedCheck2 = LessEqThan(12);
    speedCheck2.in[0] <== rotationalSpeed;
    speedCheck2.in[1] <== 3000;

    component torqueCheck1 = GreaterEqThan(13);
    torqueCheck1.in[0] <== torque;
    torqueCheck1.in[1] <== 300;

    component torqueCheck2 = LessEqThan(13);
    torqueCheck2.in[0] <== torque;
    torqueCheck2.in[1] <== 7700;

    component toolWearCheck = LessEqThan(9);
    toolWearCheck.in[0] <== toolWear;
    toolWearCheck.in[1] <== 300;

    component machineTypeCheck1 = GreaterEqThan(2);
    machineTypeCheck1.in[0] <== machineType;
    machineTypeCheck1.in[1] <== 1;

    component machineTypeCheck2 = LessEqThan(2);
    machineTypeCheck2.in[0] <== machineType;
    machineTypeCheck2.in[1] <== 3;

    /* Basit validasyon - sadece temel kontroller */
    component basicCheck1 = GreaterThan(32);
    basicCheck1.in[0] <== machineId;
    basicCheck1.in[1] <== 0;
    
    component basicCheck2 = GreaterThan(32);
    basicCheck2.in[0] <== timestamp;
    basicCheck2.in[1] <== 0;
    
    validProof <== basicCheck1.out * basicCheck2.out;
}

// Wrap to expose main-level inputs (Circom 2.x): only main's inputs count as public inputs
template Main() {
    // Public inputs (visible on blockchain)
    signal input machineId;
    signal input timestamp;
    signal input dataCommitment;
    
    // Private inputs (hidden from blockchain)
    signal input airTemperature;
    signal input processTemperature;
    signal input rotationalSpeed;
    signal input torque;
    signal input toolWear;
    signal input machineType;
    signal input nonce;

    component P = SensorDataProof();
    P.machineId <== machineId;
    P.timestamp <== timestamp;
    P.dataCommitment <== dataCommitment;
    P.airTemperature <== airTemperature;
    P.processTemperature <== processTemperature;
    P.rotationalSpeed <== rotationalSpeed;
    P.torque <== torque;
    P.toolWear <== toolWear;
    P.machineType <== machineType;
    P.nonce <== nonce;

    // Public outputs (only metadata)
    signal output out_machineId;
    signal output out_timestamp;
    signal output out_dataCommitment;

    out_machineId <== P.out_machineId;
    out_timestamp <== P.out_timestamp;
    out_dataCommitment <== P.out_dataCommitment;
}

component main = Main();

'''
        circuits = [
            (self.sensor_circuit, sensor_circuit_code),
        ]
        
        for circuit_path, circuit_code in circuits:
            # Dosya varsa üzerine yazma (mevcut devreyi koru)
            if circuit_path.exists():
                # logger.info(f"✅ Keeping existing circuit: {circuit_path.name}")
                pass
            else:
                with open(circuit_path, 'w', encoding='utf-8') as f:
                    f.write(circuit_code)
                    # logger.info(f"✅ Created circuit: {circuit_path.name}")
    

    def _find_snarkjs_base_cmd(self) -> Optional[List[str]]:
        """Resolve the base snarkjs command so we can reuse it."""
        snarkjs_path = shutil.which("snarkjs")
        if snarkjs_path:
            return [snarkjs_path]

        local_bin = Path(__file__).resolve().parent / "node_modules" / ".bin"
        for candidate_name in ("snarkjs.cmd", "snarkjs.exe", "snarkjs"):
            candidate = local_bin / candidate_name
            if candidate.exists():
                return [str(candidate)]

        appdata = os.environ.get("APPDATA")
        if appdata:
            npm_dir = Path(appdata) / "npm"
            for candidate_name in ("snarkjs.cmd", "snarkjs.exe", "snarkjs"):
                candidate = npm_dir / candidate_name
                if candidate.exists():
                    return [str(candidate)]

        # Eğer hiçbiri bulunmazsa None döndür
        return None

    def _build_snarkjs_command(self, *args: str) -> Optional[List[str]]:
        """Compose the full snarkjs command with the resolved executable."""
        if self._snarkjs_base_cmd is None:
            self._snarkjs_base_cmd = self._find_snarkjs_base_cmd()

        if not self._snarkjs_base_cmd:
            if not self._snarkjs_not_found_logged:
                logger.error("snarkjs executable not found. Please install snarkjs and ensure it is reachable from PATH.")
                self._snarkjs_not_found_logged = True
            return None

        return [*self._snarkjs_base_cmd, *args]
    
    def _compile_circuit(self, circuit_path: Path) -> bool:
        """Circuit'i derle (Circom 2.x uyumlu)"""
        try:
            # Prefer bundled Circom if available
            circom_exe = str((Path(__file__).resolve().parent / "tools" / "circom.exe"))
            if not Path(circom_exe).exists():
                # fallback to PATH-provided circom
                circom_exe = "circom"
            compile_cmd = [
                circom_exe,
                str(circuit_path),
                "--output", str(self.temp_dir),
                "--wasm", "--r1cs", "--sym",
                "-l", "node_modules"
            ]
            result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=120, check=False)
            if result.returncode == 0:
                # logger.info(f"✅ Circuit compiled: {circuit_path.stem}")
                return True
            else:
                error_message = result.stderr if result.stderr else result.stdout
                logger.error(f"❌ Circuit compilation failed: {error_message.strip()}")
                logger.error(f"   Command: {' '.join(compile_cmd)}")
                return False
        except Exception as e:
            logger.error(f"❌ Circuit compilation error: {e}")
            return False
    
    def _calculate_witness(self, circuit_name: str, inputs: Dict) -> Optional[Path]:
        """Witness hesapla - snarkjs ile"""
        input_file = self.temp_dir / f"{circuit_name}_input.json"
        wasm_file = self.temp_dir / f"{circuit_name}_js/{circuit_name}.wasm"
        witness_file = self.temp_dir / f"{circuit_name}_witness.wtns"
        
        try:
            # SnarkJS JSON input: use strings for big integers to avoid JS 53-bit truncation
            def _to_serializable(v):
                if isinstance(v, bool):
                    return v
                if isinstance(v, int):
                    return str(v)
                if isinstance(v, float):
                    # floats should not appear for circuit inputs; but convert deterministically
                    return str(int(v))
                if isinstance(v, (list, tuple)):
                    return [_to_serializable(x) for x in v]
                if isinstance(v, dict):
                    return {k: _to_serializable(val) for k, val in v.items()}
                return v

            serializable_inputs = _to_serializable(inputs)
            with open(input_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_inputs, f)
            
            # snarkjs ile witness calculation - tam yol kullan
            witness_cmd = self._build_snarkjs_command(
                "wc",
                str(wasm_file),
                str(input_file),
                str(witness_file)
            )
            if not witness_cmd:
                return None
            cmd_display = ' '.join(str(part) for part in witness_cmd)
            # logger.info(f"🔒 Witness calculation command: {cmd_display}")
            result = subprocess.run(
                witness_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                creationflags=self._no_window_flag
            )
            # logger.info(f"🔒 Witness calculation return code: {result.returncode}")
            # logger.info(f"🔒 Witness calculation stdout: {result.stdout}")
            # logger.info(f"🔒 Witness calculation stderr: {result.stderr}")
            
            if result.returncode == 0:
                # Witness dosyasının gerçekten oluştuğunu kontrol et
                if witness_file.exists():
                    # logger.info(f"✅ Witness calculated: {circuit_name}")
                    return witness_file
                else:
                    logger.error(f"❌ Witness file not created: {witness_file}")
                    return None
            else:
                logger.error(f"❌ Witness calculation failed: {result.stderr.strip()}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Witness calculation error: {e}")
            return None
    
    def _perform_trusted_setup(self, circuit_name: str) -> bool:
        r1cs_file = self.temp_dir / f"{circuit_name}.r1cs"
        zkey_file = self.temp_dir / f"{circuit_name}.zkey"
        
        # Eğer R1CS, mevcut zkey'den daha yeniyse zkey'i yeniden oluştur
        try:
            if zkey_file.exists() and r1cs_file.exists():
                if r1cs_file.stat().st_mtime > zkey_file.stat().st_mtime:
                    zkey_file.unlink()
                    # logger.info(f"🔄 R1CS updated; regenerating zkey for {circuit_name}")
        except Exception:
            pass
        
        if zkey_file.exists():
            # logger.info(f"✅ ZKey already exists for {circuit_name}; reusing it.")
            return True

        # logger.info(f"🔒 Performing trusted setup for {circuit_name}... This may take a moment.")
        
        # Powers of Tau file - prefer prepared phase2 if available
        pot_prepared = self.temp_dir / "pot16_final_prepared.ptau"
        pot_file = pot_prepared if pot_prepared.exists() else (self.temp_dir / "pot16_final.ptau")
        if not pot_file.exists():
            logger.error(f"❌ Powers of Tau file not found at {pot_file}. Please download it manually.")
            return False

        try:
            zkey_cmd = self._build_snarkjs_command(
                "groth16",
                "setup",
                str(r1cs_file),
                str(pot_file),
                str(zkey_file)
            )
            if not zkey_cmd:
                return False
            result = subprocess.run(
                zkey_cmd,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
                creationflags=self._no_window_flag
            )
        
            if result.returncode == 0:
                # logger.info(f"✅ Trusted setup successful for {circuit_name}")
                return True
            else:
                logger.error(f"❌ Trusted setup failed: {result.stderr.strip()}")
                return False
        except Exception as e:
            logger.error(f"❌ Trusted setup error: {e}")
            return False
    
    def _generate_proof_snarkjs(self, circuit_name: str, witness_file: Path) -> Optional[Dict]:
        """SnarkJS ile proof oluÅŸtur"""
        zkey_file = self.temp_dir / f"{circuit_name}.zkey"
        proof_file = self.temp_dir / f"{circuit_name}_proof.json"
        public_file = self.temp_dir / f"{circuit_name}_public.json"

        try:
            proof_cmd = self._build_snarkjs_command(
                "groth16",
                "prove",
                str(zkey_file),
                str(witness_file),
                str(proof_file),
                str(public_file)
            )
            if not proof_cmd:
                return None
            cmd_display = ' '.join(str(part) for part in proof_cmd)
            # logger.info(f"🔒 Proof generation command: {cmd_display}")
            result = subprocess.run(
                proof_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                creationflags=self._no_window_flag
            )
            # logger.info(f"🔒 Return code: {result.returncode}")
            # logger.info(f"🔒 stdout: {result.stdout}")
            # logger.info(f"🔒 stderr: {result.stderr}")
        
            if result.returncode == 0:
                with open(proof_file, 'r', encoding='utf-8') as f:
                    proof_data = json.load(f)
                with open(public_file, 'r', encoding='utf-8') as f:
                    public_inputs = json.load(f)

                # commitmentHash artık gerekmiyor, zaten public inputs'ta var
        
                # logger.info(f"✅ ZK proof generated: {circuit_name}")
                return {'proof': proof_data, 'publicInputs': public_inputs}
            else:
                logger.error(f"❌ Proof generation failed: {result.stderr.strip()}")
                return None
        except Exception as e:
            logger.error(f"❌ Proof generation error: {e}")
            return None


    def _has_circom_tools(self) -> bool:
        """Circom araçları mevcut mu kontrol et"""
        try:
            circom_cmd = ["circom", "--version"]
            snarkjs_cmd = self._build_snarkjs_command("--version")

            if not snarkjs_cmd:
                logger.warning("❌ Circom/snarkjs tools not working properly - Using mock proofs")
                return False

            circom_result = subprocess.run(
                circom_cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            snarkjs_result = subprocess.run(
                snarkjs_cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            circom_ok = circom_result.returncode == 0
            snarkjs_output = snarkjs_result.stdout if snarkjs_result.stdout else snarkjs_result.stderr
            snarkjs_ok = "snarkjs@" in snarkjs_output
            success = circom_ok and snarkjs_ok
            
            if success:
                # logger.info("✅ Circom and snarkjs tools detected - Real ZK proofs enabled!")
                # logger.info(f"   Circom output: {circom_result.stdout.strip()[:50]}...")
                # logger.info(f"   snarkjs detected: True")
                pass
            else:
                logger.warning("❌ Circom/snarkjs tools not working properly - Using mock proofs")
            return success
        except Exception as e:
            logger.warning(f"❌ Circom tools check failed: {e} - Using mock proofs")
            return False

    def generate_sensor_proof_v2(self, sensor_data: SensorData) -> Optional[Dict]:
        """Daha sağlam sensör kanıtı üretimi - Privacy-first approach."""
        try:
            # 1) Girdi haritaları
            mt_map = {'L': 1, 'M': 2, 'H': 3}
            
            # Compute data commitment (hash of sensor values only, without machineId/timestamp)
            # This matches our circuit: Poseidon(6) with [airTemp, processTemp, rotation, torque, toolWear, machineType]
            import subprocess
            sensor_values = [
                int(sensor_data.air_temperature * 100),
                int(sensor_data.process_temperature * 100),
                int(sensor_data.rotational_speed),
                int(sensor_data.torque * 100),
                int(sensor_data.tool_wear),
                mt_map.get(sensor_data.machine_type, 2)
            ]
            
            # logger.info(f"🔒 Computing Poseidon hash for sensor values: {sensor_values}")
            
            # Use circomlibjs for %100 circuit compatibility
            try:
                hash_cmd = f"""
                const circomlibjs = require("circomlibjs");
                (async () => {{
                    const poseidon = await circomlibjs.buildPoseidon();
                    const inputs = {json.dumps([str(v) for v in sensor_values])}.map(BigInt);
                    const hash = poseidon(inputs);
                    // F.toString(hash) converts field element to decimal string
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
                data_commitment = int(result.stdout.strip())
                # logger.info(f"✅ Data commitment: {data_commitment}")
                # logger.info(f"   Hex: {hex(data_commitment)}")
            except subprocess.TimeoutExpired as timeout_err:
                # Timeout but result may be in stdout
                if timeout_err.stdout and timeout_err.stdout.strip():
                    data_commitment = int(timeout_err.stdout.strip())
                    logger.warning(f"⚠️ Poseidon hash timeout but result found: {data_commitment}")
                else:
                    logger.error(f"❌ Poseidon hash timeout with no output")
                    raise Exception(f"Poseidon hash timeout")
            except Exception as hash_err:
                logger.error(f"❌ Poseidon hash failed: {hash_err}")
                if hasattr(hash_err, 'stdout'):
                    logger.error(f"   stdout: {hash_err.stdout}")
                if hasattr(hash_err, 'stderr'):
                    logger.error(f"   stderr: {hash_err.stderr}")
                raise Exception(f"Poseidon hash error: {hash_err}")
            
            circuit_inputs = {
                # Public inputs (visible on blockchain)
                'machineId': int(sensor_data.machine_id),
                'timestamp': int(sensor_data.timestamp),
                'dataCommitment': int(data_commitment),
                # Private inputs (hidden from blockchain)
                'airTemperature': sensor_values[0],
                'processTemperature': sensor_values[1],
                'rotationalSpeed': sensor_values[2],
                'torque': sensor_values[3],
                'toolWear': sensor_values[4],
                'machineType': sensor_values[5],
                'nonce': int(time.time()) % 100000
            }
            
            # Only metadata goes to blockchain (3 public inputs)
            public_inputs_list = [
                circuit_inputs['machineId'],
                circuit_inputs['timestamp'],
                circuit_inputs['dataCommitment']
            ]
            
            # logger.info(f"🔒 Privacy Mode: {len(public_inputs_list)} public inputs (was 8)")
            # logger.info(f"   Public: machineId={circuit_inputs['machineId']}, timestamp={circuit_inputs['timestamp']}")
            # logger.info(f"   Commitment: {hex(circuit_inputs['dataCommitment'])[:16]}...")
            # logger.info(f"   Private: 6 sensor values hidden from blockchain")

            # 2) Derle
            if not self._compile_circuit(self.sensor_circuit):
                return None

            # 3) ZKey hazır mı?
            zkey_path = self.temp_dir / 'sensor_data_proof.zkey'
            if not zkey_path.exists():
                if not self._perform_trusted_setup('sensor_data_proof'):
                    return None

            # 4) Witness
            witness_file = self._calculate_witness('sensor_data_proof', circuit_inputs)
            if not witness_file:
                return None

            # 5) Prove
            proof_data = self._generate_proof_snarkjs('sensor_data_proof', witness_file)
            if not proof_data:
                return None

            # Do NOT override snarkjs public inputs; use as produced by snarkjs
            # logger.info(f"✅ Public inputs from snarkjs kept (count={len(public_inputs_list)})")
            return proof_data
        except Exception as e:
            logger.error(f"❌ Sensor proof generation (v2) error: {e}")
            return None


    def generate_prediction_proof(self, prediction: PredictionData, sensor_data: SensorData, data_proof_id_onchain: Optional[int] = None) -> Optional[Dict]:
        """Generate ZK proof for prediction data (3 public inputs).
        Public inputs (metadata only): [dataProofId, modelHash, timestamp]
        Prediction and confidence remain private within the circuit.
        """
        if not self._has_circom_tools():
            logger.error("Circom/snarkjs tools not found. Cannot generate prediction proof.")
            return None

        try:
            # Prepare inputs
            data_proof_id = int(data_proof_id_onchain) if data_proof_id_onchain is not None else int(sensor_data.data_id or 0)
            prediction_int = int(prediction.prediction)
            confidence_int = int(float(prediction.probability) * 10000)

            # Convert model version/hash string to a field element (compact representation)
            try:
                from real_poseidon_utils import RealPoseidonHasher
                model_hash_fe = RealPoseidonHasher().string_to_field_element(prediction.model_version or "model")
            except Exception:
                # Fallback: simple deterministic hash
                import hashlib
                model_hash_fe = int(hashlib.sha256((prediction.model_version or "model").encode()).hexdigest(), 16) % (2**254)

            ts = int(prediction.timestamp or time.time())

            circuit_inputs = {
                'dataProofId': data_proof_id,
                'prediction': prediction_int,
                'confidence': confidence_int,
                'modelHash': int(model_hash_fe),
                'timestamp': ts,
                'nonce': int(time.time()) % 100000
            }

            public_inputs_list = [
                circuit_inputs['dataProofId'],
                circuit_inputs['modelHash'],
                circuit_inputs['timestamp']
            ]

            # Compile, setup, witness, prove
            if not self._compile_circuit(self.prediction_circuit):
                return None

            if not self._perform_trusted_setup('prediction_proof'):
                return None

            witness_file = self._calculate_witness('prediction_proof', circuit_inputs)
            if not witness_file:
                return None

            proof_data = self._generate_proof_snarkjs('prediction_proof', witness_file)
            if not proof_data:
                return None

            # logger.info(f"Using snarkjs-produced publicInputs (len={len(public_inputs_list)})")

            return proof_data
        except Exception as e:
            logger.error(f"Prediction proof generation error: {e}")
            return None

    

# Test
if __name__ == "__main__":
    
    sensor_data_obj = SensorData(
        machine_id=1001,
        air_temperature=298.1,
        process_temperature=308.6,
        rotational_speed=1551,
        torque=42.8,
        tool_wear=0,
        machine_type="M",
        timestamp=int(time.time()),
        submitter="0x... "
    )
    
    zk_gen = ZKProofGenerator()
    proof = zk_gen.generate_sensor_proof_v2(sensor_data_obj)
    
    if proof:
        print("\n--- ZK PROOF RESULT ---")
        print(json.dumps(proof, indent=2))
        print("-----------------------")
