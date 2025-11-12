// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./SensorDataVerifier.sol"; // provides Groth16Verifier (snarkjs) for sensor circuit

/**
 * Tek doğrulayıcı: Sensör kanıtı için snarkjs tarzı (sabit VK),
 * Prediction/Bakım için dinamik VK + pairing precompile.
 */

library PairingU {
    struct G1Point { uint256 X; uint256 Y; }
    struct G2Point { uint256[2] X; uint256[2] Y; }

    function G1_add(G1Point memory p1, G1Point memory p2) internal view returns (G1Point memory r) {
        uint256[4] memory input = [p1.X, p1.Y, p2.X, p2.Y];
        assembly { if iszero(staticcall(gas(), 0x06, input, 0x80, r, 0x40)) { revert(0, 0) } }
    }
    function G1_mul(G1Point memory p, uint256 s) internal view returns (G1Point memory r) {
        uint256[3] memory input = [p.X, p.Y, s];
        assembly { if iszero(staticcall(gas(), 0x07, input, 0x60, r, 0x40)) { revert(0, 0) } }
    }
    function G1_neg(G1Point memory p) internal pure returns (G1Point memory) {
        if (p.X == 0 && p.Y == 0) return p;
        uint256 FIELD_PRIME = 21888242871839275222246405745257275088696311157297823662689037894645226208583;
        return G1Point(p.X, FIELD_PRIME - p.Y);
    }
}

contract UnifiedGroth16Verifier is Ownable, Groth16Verifier {
    using PairingU for *;

    // ----------------- Dinamik VK Yapısı (Prediction/Maintenance) -----------------
    enum CircuitType { SENSOR_DATA, PREDICTION, MAINTENANCE, LEGACY }
    struct DynVK {
        PairingU.G1Point alpha;
        PairingU.G2Point beta;
        PairingU.G2Point gamma;
        PairingU.G2Point delta;
        PairingU.G1Point[] IC;
        bool isSet;
    }
    mapping(CircuitType => DynVK) public circuitKeys;

    function setCircuitVerifyingKey(
        CircuitType circuitType,
        PairingU.G1Point memory alpha,
        PairingU.G2Point memory beta,
        PairingU.G2Point memory gamma,
        PairingU.G2Point memory delta,
        PairingU.G1Point[] memory IC
    ) external onlyOwner {
        require(IC.length > 0, "IC empty");
        delete circuitKeys[circuitType].IC;
        circuitKeys[circuitType].alpha = alpha;
        circuitKeys[circuitType].beta = beta;
        circuitKeys[circuitType].gamma = gamma;
        circuitKeys[circuitType].delta = delta;
        for (uint i=0;i<IC.length;i++){ circuitKeys[circuitType].IC.push(IC[i]); }
        circuitKeys[circuitType].isSet = true;
    }

    function verifyPredictionProof(
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory public_inputs
    ) public view returns (bool) {
        return _baseVerify(circuitKeys[CircuitType.PREDICTION], a, b, c, public_inputs);
    }

    function verifyMaintenanceProof(
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory public_inputs
    ) public view returns (bool) {
        return _baseVerify(circuitKeys[CircuitType.MAINTENANCE], a, b, c, public_inputs);
    }

    function _swapG2(PairingU.G2Point memory g) internal pure returns (PairingU.G2Point memory) {
        return PairingU.G2Point([g.X[1], g.X[0]], [g.Y[1], g.Y[0]]);
    }

    function _baseVerify(
        DynVK storage vk,
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory public_inputs
    ) internal view returns (bool) {
        require(vk.isSet, "VK not set");
        require(public_inputs.length == vk.IC.length - 1, "bad inputs");

        PairingU.G1Point memory pA = PairingU.G1Point(a[0], a[1]);
        // pB: EVM precompile sırasına göre swap
        // Use proof's native G2 ordering; swap only VK constants to precompile order
        PairingU.G2Point memory pB = PairingU.G2Point([b[0][0], b[0][1]],[b[1][0], b[1][1]]);
        PairingU.G1Point memory pC = PairingU.G1Point(c[0], c[1]);

        PairingU.G1Point memory vk_x = vk.IC[0];
        for (uint i=0;i<public_inputs.length;i++) {
            vk_x = PairingU.G1_add(vk_x, PairingU.G1_mul(vk.IC[i+1], public_inputs[i]));
        }

        // Try multiple ordering variants for maximum compatibility across clients
        PairingU.G2Point memory pB_swap = PairingU.G2Point([pB.X[1], pB.X[0]],[pB.Y[1], pB.Y[0]]);

        // Variant 1: proof native B, VK swapped
        if (_pairingCheck(
            PairingU.G1_neg(pA), pB,
            vk.alpha, _swapG2(vk.beta),
            vk_x, _swapG2(vk.gamma),
            pC, _swapG2(vk.delta)
        )) { return true; }

        // Variant 2: proof swapped B, VK swapped
        if (_pairingCheck(
            PairingU.G1_neg(pA), pB_swap,
            vk.alpha, _swapG2(vk.beta),
            vk_x, _swapG2(vk.gamma),
            pC, _swapG2(vk.delta)
        )) { return true; }

        // Variant 3: proof native B, VK native
        if (_pairingCheck(
            PairingU.G1_neg(pA), pB,
            vk.alpha, vk.beta,
            vk_x, vk.gamma,
            pC, vk.delta
        )) { return true; }

        // Variant 4: proof swapped B, VK native
        if (_pairingCheck(
            PairingU.G1_neg(pA), pB_swap,
            vk.alpha, vk.beta,
            vk_x, vk.gamma,
            pC, vk.delta
        )) { return true; }

        return false;
    }

    function _pairingCheck(
        PairingU.G1Point memory nA,
        PairingU.G2Point memory pB,
        PairingU.G1Point memory alpha,
        PairingU.G2Point memory beta,
        PairingU.G1Point memory vk_x,
        PairingU.G2Point memory gamma,
        PairingU.G1Point memory pC,
        PairingU.G2Point memory delta
    ) internal view returns (bool) {
        uint256 inputSize = 4 * 6 * 32; // 4 pairs * (G1(2) + G2(4)) * 32 bytes
        bytes memory input = new bytes(inputSize);
        assembly {
            let base := add(input, 0x20)
            // (-A, B)
            mstore(base, mload(nA))
            mstore(add(base, 32), mload(add(nA, 32)))
            mstore(add(base, 64), mload(pB))
            mstore(add(base, 96), mload(add(pB, 32)))
            mstore(add(base, 128), mload(add(pB, 64)))
            mstore(add(base, 160), mload(add(pB, 96)))
            // (alpha, beta)
            let off1 := add(base, 192)
            mstore(off1, mload(alpha))
            mstore(add(off1, 32), mload(add(alpha, 32)))
            mstore(add(off1, 64), mload(beta))
            mstore(add(off1, 96), mload(add(beta, 32)))
            mstore(add(off1, 128), mload(add(beta, 64)))
            mstore(add(off1, 160), mload(add(beta, 96)))
            // (vk_x, gamma)
            let off2 := add(base, 384)
            mstore(off2, mload(vk_x))
            mstore(add(off2, 32), mload(add(vk_x, 32)))
            mstore(add(off2, 64), mload(gamma))
            mstore(add(off2, 96), mload(add(gamma, 32)))
            mstore(add(off2, 128), mload(add(gamma, 64)))
            mstore(add(off2, 160), mload(add(gamma, 96)))
            // (C, delta)
            let off3 := add(base, 576)
            mstore(off3, mload(pC))
            mstore(add(off3, 32), mload(add(pC, 32)))
            mstore(add(off3, 64), mload(delta))
            mstore(add(off3, 96), mload(add(delta, 32)))
            mstore(add(off3, 128), mload(add(delta, 64)))
            mstore(add(off3, 160), mload(add(delta, 96)))
        }
        bool ok;
        bytes memory outBuf = new bytes(32);
        assembly {
            ok := staticcall(gas(), 0x08, add(input, 0x20), inputSize, add(outBuf, 0x20), 0x20)
        }
        if (!ok) return false;
        uint256 res;
        assembly { res := mload(add(outBuf, 0x20)) }
        return res == 1;
    }

    function debugVerifyPrediction(
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory public_inputs
    ) public view returns (
        bool native_vkSwap,
        bool swapB_vkSwap,
        bool native_vkNoSwap,
        bool swapB_vkNoSwap
    ) {
        DynVK storage vk = circuitKeys[CircuitType.PREDICTION];
        require(vk.isSet, "VK not set");
        require(public_inputs.length == vk.IC.length - 1, "bad inputs");

        PairingU.G1Point memory pA = PairingU.G1Point(a[0], a[1]);
        PairingU.G2Point memory pB_native = PairingU.G2Point([b[0][0], b[0][1]],[b[1][0], b[1][1]]);
        PairingU.G2Point memory pB_swap   = PairingU.G2Point([b[0][1], b[0][0]],[b[1][1], b[1][0]]);
        PairingU.G1Point memory pC = PairingU.G1Point(c[0], c[1]);

        PairingU.G1Point memory vk_x = vk.IC[0];
        for (uint i=0;i<public_inputs.length;i++) {
            vk_x = PairingU.G1_add(vk_x, PairingU.G1_mul(vk.IC[i+1], public_inputs[i]));
        }

        // VK swapped (to precompile order)
        native_vkSwap  = _pairingCheck(PairingU.G1_neg(pA), pB_native, vk.alpha, _swapG2(vk.beta), vk_x, _swapG2(vk.gamma), pC, _swapG2(vk.delta));
        swapB_vkSwap   = _pairingCheck(PairingU.G1_neg(pA), pB_swap,   vk.alpha, _swapG2(vk.beta), vk_x, _swapG2(vk.gamma), pC, _swapG2(vk.delta));
        // VK not swapped
        native_vkNoSwap = _pairingCheck(PairingU.G1_neg(pA), pB_native, vk.alpha, vk.beta, vk_x, vk.gamma, pC, vk.delta);
        swapB_vkNoSwap  = _pairingCheck(PairingU.G1_neg(pA), pB_swap,   vk.alpha, vk.beta, vk_x, vk.gamma, pC, vk.delta);
    }

    function verifySensorDataProof(
        uint[2] memory a,
        uint[2][2] memory b,
        uint[2] memory c,
        uint[] memory input
    ) public view returns (bool) {
        // Prefer dynamic VK if set (supports variable public input length, e.g., 3)
        if (circuitKeys[CircuitType.SENSOR_DATA].isSet) {
            return _baseVerify(circuitKeys[CircuitType.SENSOR_DATA], a, b, c, input);
        }
        // Fallback to legacy snarkjs verifier path which expects exactly 8 public inputs
        if (input.length != 8) return false;
        uint[8] memory pub;
        for (uint i=0;i<8;i++){ pub[i]=input[i]; }
        bytes memory data = abi.encodeWithSignature(
            "verifyProof(uint256[2],uint256[2][2],uint256[2],uint256[8])",
            a, b, c, pub
        );
        (bool ok, bytes memory ret) = address(this).staticcall(data);
        if (!ok || ret.length == 0) return false;
        return abi.decode(ret, (bool));
    }

    // --- Diagnostics: IC size and points ---
    function getICLength(CircuitType circuitType) external view returns (uint256) {
        DynVK storage vk = circuitKeys[circuitType];
        require(vk.isSet, "VK not set");
        return vk.IC.length;
    }

    function getICPoint(
        CircuitType circuitType,
        uint256 index
    ) external view returns (uint256 X, uint256 Y) {
        DynVK storage vk = circuitKeys[circuitType];
        require(vk.isSet, "VK not set");
        require(index < vk.IC.length, "IC idx");
        PairingU.G1Point storage p = vk.IC[index];
        return (p.X, p.Y);
    }
}
