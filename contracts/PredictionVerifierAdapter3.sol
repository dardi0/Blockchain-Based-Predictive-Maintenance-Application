// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./PredictionVerifier3.sol";

interface IPredictionVerifierAdapter3 {
    function verifyPredictionProof(
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory public_inputs
    ) external view returns (bool);
}

contract PredictionVerifierAdapter3 is PredictionGroth16Verifier3, IPredictionVerifierAdapter3 {
    function verifyPredictionProof(
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory public_inputs
    ) external view override returns (bool) {
        require(public_inputs.length == 3, "prediction inputs len 3");
        uint[3] memory pi;
        for (uint i = 0; i < 3; i++) { pi[i] = public_inputs[i]; }
        // Swap G2 coordinates to match precompile ordering expected by snarkjs verifier
        uint[2][2] memory bs;
        bs[0][0] = b[0][1];
        bs[0][1] = b[0][0];
        bs[1][0] = b[1][1];
        bs[1][1] = b[1][0];
        return this.verifyProof(a, bs, c, pi);
    }
}

