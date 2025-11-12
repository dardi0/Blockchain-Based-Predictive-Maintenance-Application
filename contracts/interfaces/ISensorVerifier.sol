// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface ISensorVerifier {
    function verifySensorDataProof(
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory public_inputs
    ) external view returns (bool);
}

