
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

