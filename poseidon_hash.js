#!/usr/bin/env node
/**
 * GERÇEK Poseidon Hash Utility
 * circomlibjs kullanarak - Circom ile %100 uyumlu
 */

const circomlibjs = require("circomlibjs");

// Singleton Poseidon instance
let poseidonInstance = null;

async function getPoseidon() {
    if (!poseidonInstance) {
        poseidonInstance = await circomlibjs.buildPoseidon();
    }
    return poseidonInstance;
}

async function hashSensorData(machineId, timestamp, airTemp, processTemp, rotationalSpeed, torque, toolWear, machineType) {
    const poseidon = await getPoseidon();
    // Float değerleri integer'a çevir (x100 precision)
    const airTempInt = Math.floor(airTemp * 100);
    const processTempInt = Math.floor(processTemp * 100);
    const torqueInt = Math.floor(torque * 100);
    
    // Machine type string'i integer'a çevir
    const machineTypeMap = { "L": 1, "M": 2, "H": 3 };
    const machineTypeInt = machineTypeMap[machineType] || machineType;
    
    const inputs = [
        BigInt(machineId),
        BigInt(timestamp),
        BigInt(airTempInt),
        BigInt(processTempInt),
        BigInt(rotationalSpeed),
        BigInt(torqueInt),
        BigInt(toolWear),
        BigInt(machineTypeInt)
    ];
    
    const hashResult = poseidon(inputs);
    
    // Convert Uint8Array to BigInt (field element)
    if (hashResult instanceof Uint8Array) {
        let bigIntValue = 0n;
        for (let i = 0; i < hashResult.length; i++) {
            bigIntValue = (bigIntValue << 8n) + BigInt(hashResult[i]);
        }
        
        // Reduce to BN254 field (Baby Jubjub prime)
        const BN254_FIELD_SIZE = 21888242871839275222246405745257275088548364400416034343698204186575808495617n;
        return bigIntValue % BN254_FIELD_SIZE;
    }
    
    return hashResult;
}

async function hashPredictionData(dataId, prediction, probabilityInt, modelVersionHash, timestamp) {
    const poseidon = await getPoseidon();
    const inputs = [
        BigInt(dataId),
        BigInt(prediction),
        BigInt(probabilityInt),
        BigInt(modelVersionHash),
        BigInt(timestamp)
    ];
    
    const hashResult = poseidon(inputs);
    
    // Convert Uint8Array to BigInt (field element)
    if (hashResult instanceof Uint8Array) {
        let bigIntValue = 0n;
        for (let i = 0; i < hashResult.length; i++) {
            bigIntValue = (bigIntValue << 8n) + BigInt(hashResult[i]);
        }
        
        // Reduce to BN254 field (Baby Jubjub prime)
        const BN254_FIELD_SIZE = 21888242871839275222246405745257275088548364400416034343698204186575808495617n;
        return bigIntValue % BN254_FIELD_SIZE;
    }
    
    return hashResult;
}

async function hashMaintenanceData(predictionId, taskType, priority, timestamp) {
    const poseidon = await getPoseidon();
    const inputs = [
        BigInt(predictionId),
        BigInt(taskType),
        BigInt(priority),
        BigInt(timestamp)
    ];
    
    const hashResult = poseidon(inputs);
    
    // Convert Uint8Array to BigInt (field element)
    if (hashResult instanceof Uint8Array) {
        let bigIntValue = 0n;
        for (let i = 0; i < hashResult.length; i++) {
            bigIntValue = (bigIntValue << 8n) + BigInt(hashResult[i]);
        }
        
        // Reduce to BN254 field (Baby Jubjub prime)
        const BN254_FIELD_SIZE = 21888242871839275222246405745257275088548364400416034343698204186575808495617n;
        return bigIntValue % BN254_FIELD_SIZE;
    }
    
    return hashResult;
}

// Command line interface
async function main() {
    // Filter out format flags from arguments
    const allArgs = process.argv.slice(2);
    const args = allArgs.filter(arg => !arg.startsWith('--format'));
    
    if (args.length === 0) {
        console.log("Usage: node poseidon_hash.js <command> <args...> [--format=<type>]");
        console.log("Commands:");
        console.log("  sensor <machineId> <timestamp> <airTemp> <processTemp> <rotationalSpeed> <torque> <toolWear> <machineType>");
        console.log("  prediction <dataId> <prediction> <probabilityInt> <modelVersionHash> <timestamp>");
        console.log("  maintenance <predictionId> <taskType> <priority> <timestamp>");
        console.log("  hash <n1> <n2> ... <nk>    (generic Poseidon over k inputs)");
        console.log("Format Options:");
        console.log("  --format=field    Field element (default)");
        console.log("  --format=hex      Hexadecimal (0x...)");
        console.log("  --format=json     JSON object");
        console.log("  --format=all      All formats");
        process.exit(1);
    }
    
    const command = args[0];
    
    try {
        let result;
        
        switch (command) {
            case "sensor":
                if (args.length !== 9) {
                    throw new Error("Sensor command requires 8 arguments");
                }
                result = await hashSensorData(
                    parseInt(args[1]), // machineId
                    parseInt(args[2]), // timestamp
                    parseFloat(args[3]), // airTemp
                    parseFloat(args[4]), // processTemp
                    parseInt(args[5]), // rotationalSpeed
                    parseFloat(args[6]), // torque
                    parseInt(args[7]), // toolWear
                    args[8] // machineType
                );
                break;
                
            case "prediction":
                if (args.length !== 6) {
                    throw new Error("Prediction command requires 5 arguments");
                }
                result = await hashPredictionData(
                    parseInt(args[1]), // dataId
                    parseInt(args[2]), // prediction
                    parseInt(args[3]), // probabilityInt
                    parseInt(args[4]), // modelVersionHash
                    parseInt(args[5])  // timestamp
                );
                break;
                
            case "maintenance":
                if (args.length !== 5) {
                    throw new Error("Maintenance command requires 4 arguments");
                }
                result = await hashMaintenanceData(
                    parseInt(args[1]), // predictionId
                    parseInt(args[2]), // taskType
                    parseInt(args[3]), // priority
                    parseInt(args[4])  // timestamp
                );
                break;

            case "hash":
                if (args.length < 2) {
                    throw new Error("Hash command requires at least 1 argument");
                }
                {
                    const poseidon = await getPoseidon();
                    const inputs = args.slice(1).map((v) => BigInt(parseInt(v)));
                    const hash = poseidon(inputs);
                    let res = 0n;
                    if (hash instanceof Uint8Array) {
                        for (let i = 0; i < hash.length; i++) {
                            res = (res << 8n) + BigInt(hash[i]);
                        }
                        const FIELD_SIZE = 21888242871839275222246405745257275088548364400416034343698204186575808495617n;
                        res = res % FIELD_SIZE;
                    } else {
                        res = hash;
                    }
                    result = res;
                }
                break;

            default:
                throw new Error(`Unknown command: ${command}`);
        }
        
        // Multiple output formats for different use cases
        if (process.argv.includes("--format=json")) {
            // JSON format for programmatic use
            console.log(JSON.stringify({
                decimal: result.toString(),
                hex: "0x" + result.toString(16),
                bigint: result.toString(),
                field_element: result.toString()
            }));
        } else if (process.argv.includes("--format=hex")) {
            // Hex format for Circom/Solidity
            console.log("0x" + result.toString(16));
        } else if (process.argv.includes("--format=field")) {
            // Field element format for ZK circuits
            console.log(result.toString());
        } else if (process.argv.includes("--format=all")) {
            // All formats for debugging
            console.log("Decimal:", result.toString());
            console.log("Hex:", "0x" + result.toString(16));
            console.log("BigInt:", result.toString() + "n");
            console.log("Field Element:", result.toString());
        } else {
            // Default: field element format
            console.log(result.toString());
        }
        
    } catch (error) {
        console.error("Error:", error.message);
        process.exit(1);
    }
}

// Run main if called directly
if (require.main === module) {
    main().catch(error => {
        console.error("Fatal error:", error.message);
        process.exit(1);
    });
}

module.exports = {
    hashSensorData,
    hashPredictionData,
    hashMaintenanceData
};
