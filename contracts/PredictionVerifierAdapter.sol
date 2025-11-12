// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./PredictionGroth16Verifier.sol";

interface IPredictionVerifierAdapter {
    function verifyPredictionProof(
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory public_inputs
    ) external view returns (bool);
}

contract PredictionVerifierAdapter is PredictionGroth16Verifier, IPredictionVerifierAdapter {
    function verifyPredictionProof(
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory public_inputs
    ) external view override returns (bool) {
        require(public_inputs.length == 5, "prediction inputs len");
        uint[5] memory pi;
        for (uint i = 0; i < 5; i++) { pi[i] = public_inputs[i]; }
        return this.verifyProofRaw(a, b, c, pi);
    }

    // Direct wrapper with calldata types to avoid memory->calldata issues
    function verifyProofRaw(
        uint[2] calldata a,
        uint[2][2] calldata b,
        uint[2] calldata c,
        uint[5] calldata pi
    ) external view returns (bool) {
        return verifyProof(a, b, c, pi);
    }
}
