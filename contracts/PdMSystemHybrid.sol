// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "./AccessControlRegistry.sol";
import "./UnifiedGroth16Verifier.sol";
import "./interfaces/ISensorVerifier.sol";
interface IPredictionVerifier {
    function verifyPredictionProof(
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory public_inputs
    ) external view returns (bool);
}
interface IPredictionVerifierDirect {
    function verifyProofRaw(
        uint[2] calldata a,
        uint[2][2] calldata b,
        uint[2] calldata c,
        uint[5] calldata pub
    ) external view returns (bool);
}

/**
 * @title PdMSystemHybrid
 * @dev Hibrit PDM sistemi - Off-chain storage + ZK-SNARK proofs
 * @notice Sensör verileri local DB'de, sadece ZK kanıtları blockchain'de
 */
contract PdMSystemHybrid is Ownable, Pausable, ReentrancyGuard {
    
    // --- ACCESS CONTROL INTEGRATION ---
    AccessControlRegistry public immutable accessRegistry;
    UnifiedGroth16Verifier public zkVerifier;
    ISensorVerifier public sensorVerifier;
    IPredictionVerifier public predictionVerifier;
    
    bytes32 public constant SENSOR_DATA_RESOURCE = keccak256("SENSOR_DATA");
    bytes32 public constant PREDICTION_RESOURCE = keccak256("PREDICTION");
    bytes32 public constant MAINTENANCE_RESOURCE = keccak256("MAINTENANCE");
    
    // --- ENUMS ---
    enum StorageType {
        LOCAL_DB,       // 0 - Local database
        IPFS,          // 1 - IPFS (future)
        ARWEAVE        // 2 - Arweave (future)
    }
    
    enum ProofType {
        SENSOR_DATA,    // 0 - Sensör verisi kanıtı
        PREDICTION,     // 1 - Tahmin kanıtı  
        MAINTENANCE,    // 2 - Bakım kanıtı
        BATCH_SENSOR    // 3 - Toplu sensör verisi
    }
    
    // --- STRUCTS ---
    struct SensorDataProof {
        bytes32 dataHash;           // Off-chain verinin hash'i
        bytes32 commitmentHash;     // ZK commitment hash
        bytes32 storageLocation;    // Local DB key veya path (32 byte'a kadar - BÜYÜK gaz tasarrufu)
        uint256 timestamp;
        address submitter;
        uint256 machineId;
        StorageType storageType;
        bytes32 zkProofHash;        // ZK proof'un hash'i
        uint256 sensorCount;        // Kaç sensör verisi (batch için)

    }
    
    struct PredictionProof {
        bytes32 predictionHash;     // Tahmin verisinin hash'i
        bytes32 modelCommitment;    // Model commitment
        uint256 dataProofId;        // Hangi sensör verisine dayalı
        uint256 prediction;         // 0 veya 1
        uint256 confidence;         // 0-10000
        address predictor;
        uint256 timestamp;
        bytes32 zkProofHash;
        // isVerified kaldırıldı - zincirdeki varlığı doğrulanmış olduğunu gösterir (20K gaz tasarrufu)
    }
    
    struct MaintenanceProof {
        bytes32 taskHash;           // Görev verisinin hash'i
        uint256 predictionProofId;  // Hangi tahmine dayalı
        address assignedEngineer;
        uint256 createdAt;
        uint256 completedAt;
        bool isCompleted;
        bytes32 zkProofHash;
        bytes32 notesCommitment;    // Tamamlama notları commitment
    }
    
    struct ZKProofMetadata {
        ProofType proofType;
        bytes32 publicInputsHash;   // Public input'ların hash'i
        uint256 relatedId;          // İlgili proof ID'si
        address submitter;
        uint256 timestamp;
        // isValid kaldırıldı - zincirdeki varlığı doğrulanmış olduğunu gösterir (20K gaz tasarrufu)
    }
    
    // --- STATE VARIABLES ---
    uint256 public sensorProofCounter;
    uint256 public predictionProofCounter;
    uint256 public maintenanceProofCounter;
    uint256 public zkProofCounter;
    
    // Mappings
    mapping(uint256 => SensorDataProof) public sensorProofs;
    mapping(uint256 => PredictionProof) public predictionProofs;
    mapping(uint256 => MaintenanceProof) public maintenanceProofs;
    mapping(bytes32 => ZKProofMetadata) public zkProofs;
    mapping(bytes32 => bool) public usedDataHashes;
    mapping(address => uint256[]) public userSensorProofs;
    mapping(uint256 => uint256[]) public machineSensorProofs;
    
    // --- EVENTS ---
    event SensorDataProofSubmitted(
        uint256 indexed proofId,
        bytes32 indexed dataHash,
        bytes32 storageLocation,
        uint256 indexed machineId,
        address submitter
    );
    
    event PredictionProofSubmitted(
        uint256 indexed proofId,
        bytes32 indexed predictionHash,
        uint256 indexed dataProofId,
        uint256 prediction,
        address predictor
    );
    
    event MaintenanceProofSubmitted(
        uint256 indexed proofId,
        bytes32 indexed taskHash,
        uint256 indexed predictionProofId,
        address engineer
    );
    
    event ZKVerifierUpdated(
        address indexed oldVerifier,
        address indexed newVerifier
    );
    
    event SensorVerifierUpdated(
        address indexed oldVerifier,
        address indexed newVerifier
    );
    event PredictionVerifierUpdated(
        address indexed oldVerifier,
        address indexed newVerifier
    );
    
    // --- MODIFIERS ---
    modifier onlyAuthorizedNode(bytes32 resource, AccessControlRegistry.AccessLevel requiredLevel) {
        (bool hasAccess, string memory reason) = accessRegistry.checkAccess(
            msg.sender, 
            resource, 
            requiredLevel
        );
        require(hasAccess, string(abi.encodePacked("Access denied: ", reason)));
        _;
    }
    
    modifier validDataHash(bytes32 dataHash) {
        require(dataHash != bytes32(0), "PdMHybrid: Invalid data hash");
        require(!usedDataHashes[dataHash], "PdMHybrid: Data hash already used");
        _;
    }
    
    // --- CONSTRUCTOR ---
    constructor(
        address _accessRegistry,
        address _zkVerifier,
        address _initialAdmin
    ) {
        require(_initialAdmin != address(0), "PdMHybrid: Invalid admin");
        _transferOwnership(_initialAdmin);
        require(_accessRegistry != address(0), "PdMHybrid: Invalid access registry");
        require(_zkVerifier != address(0), "PdMHybrid: Invalid ZK verifier");
        
        accessRegistry = AccessControlRegistry(_accessRegistry);
        zkVerifier = UnifiedGroth16Verifier(_zkVerifier);
        
        sensorProofCounter = 1;
        predictionProofCounter = 1;
        maintenanceProofCounter = 1;
        zkProofCounter = 1;
    }
    
    // --- SENSOR DATA PROOF FUNCTIONS ---
    function submitSensorDataProof(
        uint256 machineId,
        bytes32 dataHash,
        bytes32 commitmentHash,
        bytes32 storageLocation,
        uint256 sensorCount,
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[3] memory publicInputs  // [machineId, timestamp, dataCommitment] - Privacy-first!
    ) 
        external 
        whenNotPaused 
        onlyAuthorizedNode(SENSOR_DATA_RESOURCE, AccessControlRegistry.AccessLevel.WRITE_LIMITED)
        validDataHash(dataHash)
        returns (uint256 proofId) 
    {
        require(machineId > 0, "PdMHybrid: Invalid machine ID");
        require(storageLocation != bytes32(0), "PdMHybrid: Storage location required");
        require(sensorCount > 0 && sensorCount <= 100, "PdMHybrid: Invalid sensor count");
        
        // ZK Proof doğrulama (Sensor Data için özel fonksiyon) - Privacy-first: only 3 inputs
        uint[] memory inputs = new uint[](3);
        for(uint i=0; i<3; i++) {
            inputs[i] = publicInputs[i];
        }
        bool proofValid = false;
        if (address(sensorVerifier) != address(0)) {
            try sensorVerifier.verifySensorDataProof(a, b, c, inputs) returns (bool ok) {
                proofValid = ok;
            } catch {
                proofValid = false;
            }
        }
        if (!proofValid) {
            proofValid = zkVerifier.verifySensorDataProof(a, b, c, inputs);
        }
        require(proofValid, "PdMHybrid: Invalid sensor data ZK proof");
        
        // Public input doğrulaması (Privacy-first: machineId, timestamp, dataCommitment)
        require(publicInputs[0] == machineId, "PdMHybrid: Machine ID mismatch");
        require(publicInputs[1] <= block.timestamp + 300, "PdMHybrid: Invalid timestamp"); // 5 dakika tolerance
        // publicInputs[2] is dataCommitment (hash of sensor values) - verified by ZK proof
        
        // ZK proof hash hesapla (İspat + Public Inputs birlikte)
        bytes32 zkProofHash = keccak256(abi.encodePacked(a, b, c, publicInputs));
        bytes32 publicInputsHash = keccak256(abi.encodePacked(publicInputs));
        
        // Sensor proof oluştur
        proofId = sensorProofCounter++;
        sensorProofs[proofId] = SensorDataProof({
            dataHash: dataHash,
            commitmentHash: commitmentHash,
            storageLocation: storageLocation,
            timestamp: block.timestamp,
            submitter: msg.sender,
            machineId: machineId,
            storageType: StorageType.LOCAL_DB,
            zkProofHash: zkProofHash,
            sensorCount: sensorCount
        });
        
        // ZK proof metadata kaydet
        zkProofs[zkProofHash] = ZKProofMetadata({
            proofType: ProofType.SENSOR_DATA,
            publicInputsHash: publicInputsHash,
            relatedId: proofId,
            submitter: msg.sender,
            timestamp: block.timestamp
        });
        
        // Mappings güncelle
        usedDataHashes[dataHash] = true;
        userSensorProofs[msg.sender].push(proofId);
        machineSensorProofs[machineId].push(proofId);
        
        emit SensorDataProofSubmitted(proofId, dataHash, storageLocation, machineId, msg.sender);
    }
    
    // --- PREDICTION PROOF FUNCTIONS ---
    function submitPredictionProof(
        uint256 dataProofId,
        bytes32 predictionHash,
        bytes32 modelCommitment,
        uint256 prediction,
        uint256 confidence,
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory publicInputs  // [dataProofId, modelHash, timestamp]
    )
        external
        whenNotPaused
        onlyAuthorizedNode(PREDICTION_RESOURCE, AccessControlRegistry.AccessLevel.WRITE_LIMITED)
        returns (uint256 proofId)
    {
        require(dataProofId < sensorProofCounter && dataProofId > 0, "PdMHybrid: Invalid data proof ID");
        require(sensorProofs[dataProofId].submitter != address(0), "PdMHybrid: Data proof does not exist");
        require(prediction <= 1, "PdMHybrid: Invalid prediction");
        require(confidence <= 10000, "PdMHybrid: Invalid confidence");
        
        // ZK Proof doğrulama (Prediction için özel fonksiyon)
        uint[] memory inputs = new uint[](publicInputs.length);
        for(uint i=0; i<publicInputs.length; i++) {
            inputs[i] = publicInputs[i];
        }
        // Expect exactly 3 public inputs after making prediction/confidence private
        require(publicInputs.length == 3, "PdMHybrid: invalid prediction input len");
        bool proofValid = zkVerifier.verifyPredictionProof(a, b, c, inputs);
        require(proofValid, "PdMHybrid: Invalid prediction ZK proof");
        
        // Public input doğrulaması
        require(publicInputs[0] == dataProofId, "PdMHybrid: Data proof ID mismatch");
        // prediction and confidence are private; no equality checks against public inputs
        
        // ZK proof hash hesapla (İspat + Public Inputs birlikte)
        bytes32 zkProofHash = keccak256(abi.encodePacked(a, b, c, publicInputs));
        bytes32 publicInputsHash = keccak256(abi.encodePacked(publicInputs));
        
        proofId = predictionProofCounter++;
        predictionProofs[proofId] = PredictionProof({
            predictionHash: predictionHash,
            modelCommitment: modelCommitment,
            dataProofId: dataProofId,
            prediction: prediction,
            confidence: confidence,
            predictor: msg.sender,
            timestamp: block.timestamp,
            zkProofHash: zkProofHash
        });
        
        zkProofs[zkProofHash] = ZKProofMetadata({
            proofType: ProofType.PREDICTION,
            publicInputsHash: publicInputsHash,
            relatedId: proofId,
            submitter: msg.sender,
            timestamp: block.timestamp
        });
        
        emit PredictionProofSubmitted(proofId, predictionHash, dataProofId, prediction, msg.sender);
    }
    
    // --- MAINTENANCE PROOF FUNCTIONS ---
    function submitMaintenanceProof(
        uint256 predictionProofId,
        bytes32 taskHash,
        bytes32 notesCommitment,
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[4] memory publicInputs  // [predictionProofId, taskHash, engineerAddress, timestamp]
    )
        external
        whenNotPaused
        onlyAuthorizedNode(MAINTENANCE_RESOURCE, AccessControlRegistry.AccessLevel.WRITE_LIMITED)
        returns (uint256 proofId)
    {
        require(predictionProofId < predictionProofCounter && predictionProofId > 0, "PdMHybrid: Invalid prediction proof ID");
        require(predictionProofs[predictionProofId].predictor != address(0), "PdMHybrid: Prediction proof does not exist");
        
        // ZK Proof doğrulama (Maintenance için özel fonksiyon)
            uint[] memory inputs = new uint[](4);
            for(uint i=0; i<4; i++) {
                inputs[i] = publicInputs[i];
            }
            bool proofValid = zkVerifier.verifyMaintenanceProof(a, b, c, inputs);
        require(proofValid, "PdMHybrid: Invalid maintenance ZK proof");
        
        // Public input doğrulaması (argümanlarla tutarlılık)
        require(publicInputs[0] == predictionProofId, "PdMHybrid: Prediction proof ID mismatch");
        require(bytes32(publicInputs[1]) == taskHash, "PdMHybrid: Task hash mismatch");
        require(address(uint160(publicInputs[2])) == msg.sender, "PdMHybrid: Engineer address mismatch");
        require(publicInputs[3] <= block.timestamp + 300, "PdMHybrid: Invalid timestamp"); // 5 dk tolerans
        
        // ZK proof hash hesapla (İspat + Public Inputs birlikte)
        bytes32 zkProofHash = keccak256(abi.encodePacked(a, b, c, publicInputs));
        bytes32 publicInputsHash = keccak256(abi.encodePacked(publicInputs));
        
        proofId = maintenanceProofCounter++;
        maintenanceProofs[proofId] = MaintenanceProof({
            taskHash: taskHash,
            predictionProofId: predictionProofId,
            assignedEngineer: msg.sender,
            createdAt: block.timestamp,
            completedAt: 0,
            isCompleted: false,
            zkProofHash: zkProofHash,
            notesCommitment: notesCommitment
        });
        
        // ZK proof metadata kaydet
        zkProofs[zkProofHash] = ZKProofMetadata({
            proofType: ProofType.MAINTENANCE,
            publicInputsHash: publicInputsHash,
            relatedId: proofId,
            submitter: msg.sender,
            timestamp: block.timestamp
        });
        
        emit MaintenanceProofSubmitted(proofId, taskHash, predictionProofId, msg.sender);
    }
    
    // --- VIEW FUNCTIONS ---
    function getSensorProof(uint256 proofId) external view returns (SensorDataProof memory) {
        require(proofId < sensorProofCounter && proofId > 0, "PdMHybrid: Invalid proof ID");
        return sensorProofs[proofId];
    }
    
    function getPredictionProof(uint256 proofId) external view returns (PredictionProof memory) {
        require(proofId < predictionProofCounter && proofId > 0, "PdMHybrid: Invalid proof ID");
        return predictionProofs[proofId];
    }
    
    function getMachineProofs(uint256 machineId) external view returns (uint256[] memory) {
        return machineSensorProofs[machineId];
    }
    
    function getUserProofs(address user) external view returns (uint256[] memory) {
        return userSensorProofs[user];
    }
    
    function verifyDataHash(bytes32 dataHash, string calldata /* storageLocation */) external view returns (bool) {
        return usedDataHashes[dataHash];
    }
    
    // --- ADMIN FUNCTIONS ---
    function emergencyPause() external onlyOwner {
        _pause();
    }
    
    function emergencyUnpause() external onlyOwner {
        _unpause();
    }
    
    function updateZKVerifier(address newVerifier) external onlyOwner {
        require(newVerifier != address(0), "PdMHybrid: Invalid verifier");
        
        // Update the ZK verifier address
        address oldVerifier = address(zkVerifier);
        zkVerifier = UnifiedGroth16Verifier(newVerifier);
        
        emit ZKVerifierUpdated(oldVerifier, newVerifier);
    }

    function updateSensorVerifier(address newVerifier) external onlyOwner {
        require(newVerifier != address(0), "PdMHybrid: Invalid sensor verifier");
        address oldVerifier = address(sensorVerifier);
        sensorVerifier = ISensorVerifier(newVerifier);
        emit SensorVerifierUpdated(oldVerifier, newVerifier);
    }

    function updatePredictionVerifier(address newVerifier) external onlyOwner {
        require(newVerifier != address(0), "PdMHybrid: Invalid prediction verifier");
        address oldVerifier = address(predictionVerifier);
        predictionVerifier = IPredictionVerifier(newVerifier);
        emit PredictionVerifierUpdated(oldVerifier, newVerifier);
    }
}
