
pragma circom 2.0.0;

include "circomlib/circuits/poseidon.circom";

template MaintenanceProof() {
    signal input predictionProofId;
    signal input taskHash;
    signal input engineerAddress;
    signal input timestamp;

    signal input nonce;

    signal output validProof;
    signal output commitmentHash;

    component hasher = Poseidon(4);
    hasher.inputs[0] <== predictionProofId;
    hasher.inputs[1] <== taskHash;
    hasher.inputs[2] <== engineerAddress;
    hasher.inputs[3] <== timestamp;

    commitmentHash <== hasher.out;

    validProof <== 1;
}

component main = MaintenanceProof();

// Public inputs are automatically inferred from signal input declarations
