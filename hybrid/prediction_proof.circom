
pragma circom 2.0.0;

include "circomlib/circuits/poseidon.circom";
include "circomlib/circuits/comparators.circom";

template PredictionProof() {
    // Inputs
    signal input dataProofId;
    signal input prediction;    
    signal input confidence;    
    signal input modelHash;     
    signal input timestamp;     

    // Private input (not exposed as public via wrapper)
    signal input nonce;

    // Internal/public signals as needed
    signal output validProof;
    signal output commitmentHash;

    component hasher = Poseidon(5);
    hasher.inputs[0] <== dataProofId;
    hasher.inputs[1] <== prediction;
    hasher.inputs[2] <== confidence;
    hasher.inputs[3] <== modelHash;
    hasher.inputs[4] <== timestamp;

    commitmentHash <== hasher.out;

    component predCheck = LessThan(8);
    predCheck.in[0] <== prediction;
    predCheck.in[1] <== 2;

    validProof <== predCheck.out;
}

// Wrapper: expose only metadata as public signals
template Main() {
    // Public metadata inputs (visible on-chain)
    signal input dataProofId;
    signal input modelHash;
    signal input timestamp;

    // Private inputs (hidden)
    signal input prediction;
    signal input confidence;
    signal input nonce;

    // Instantiate circuit
    component P = PredictionProof();
    P.dataProofId <== dataProofId;
    P.prediction  <== prediction;
    P.confidence  <== confidence;
    P.modelHash   <== modelHash;
    P.timestamp   <== timestamp;
    P.nonce       <== nonce;

    // Expose only 3 outputs as public signals (metadata)
    signal output out_dataProofId;
    signal output out_modelHash;
    signal output out_timestamp;

    out_dataProofId <== P.dataProofId;
    out_modelHash   <== P.modelHash;
    out_timestamp   <== P.timestamp;
}

component main = Main();
