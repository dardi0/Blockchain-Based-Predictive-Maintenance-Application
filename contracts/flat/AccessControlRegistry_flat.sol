// Sources flattened with hardhat v2.26.3 https://hardhat.org

// SPDX-License-Identifier: MIT

// File @openzeppelin/contracts/utils/Context.sol@v4.9.6

// Original license: SPDX_License_Identifier: MIT
// OpenZeppelin Contracts (last updated v4.9.4) (utils/Context.sol)

pragma solidity ^0.8.0;

/**
 * @dev Provides information about the current execution context, including the
 * sender of the transaction and its data. While these are generally available
 * via msg.sender and msg.data, they should not be accessed in such a direct
 * manner, since when dealing with meta-transactions the account sending and
 * paying for execution may not be the actual sender (as far as an application
 * is concerned).
 *
 * This contract is only required for intermediate, library-like contracts.
 */
abstract contract Context {
    function _msgSender() internal view virtual returns (address) {
        return msg.sender;
    }

    function _msgData() internal view virtual returns (bytes calldata) {
        return msg.data;
    }

    function _contextSuffixLength() internal view virtual returns (uint256) {
        return 0;
    }
}


// File @openzeppelin/contracts/access/Ownable.sol@v4.9.6

// Original license: SPDX_License_Identifier: MIT
// OpenZeppelin Contracts (last updated v4.9.0) (access/Ownable.sol)

pragma solidity ^0.8.0;

/**
 * @dev Contract module which provides a basic access control mechanism, where
 * there is an account (an owner) that can be granted exclusive access to
 * specific functions.
 *
 * By default, the owner account will be the one that deploys the contract. This
 * can later be changed with {transferOwnership}.
 *
 * This module is used through inheritance. It will make available the modifier
 * `onlyOwner`, which can be applied to your functions to restrict their use to
 * the owner.
 */
abstract contract Ownable is Context {
    address private _owner;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    /**
     * @dev Initializes the contract setting the deployer as the initial owner.
     */
    constructor() {
        _transferOwnership(_msgSender());
    }

    /**
     * @dev Throws if called by any account other than the owner.
     */
    modifier onlyOwner() {
        _checkOwner();
        _;
    }

    /**
     * @dev Returns the address of the current owner.
     */
    function owner() public view virtual returns (address) {
        return _owner;
    }

    /**
     * @dev Throws if the sender is not the owner.
     */
    function _checkOwner() internal view virtual {
        require(owner() == _msgSender(), "Ownable: caller is not the owner");
    }

    /**
     * @dev Leaves the contract without owner. It will not be possible to call
     * `onlyOwner` functions. Can only be called by the current owner.
     *
     * NOTE: Renouncing ownership will leave the contract without an owner,
     * thereby disabling any functionality that is only available to the owner.
     */
    function renounceOwnership() public virtual onlyOwner {
        _transferOwnership(address(0));
    }

    /**
     * @dev Transfers ownership of the contract to a new account (`newOwner`).
     * Can only be called by the current owner.
     */
    function transferOwnership(address newOwner) public virtual onlyOwner {
        require(newOwner != address(0), "Ownable: new owner is the zero address");
        _transferOwnership(newOwner);
    }

    /**
     * @dev Transfers ownership of the contract to a new account (`newOwner`).
     * Internal function without access restriction.
     */
    function _transferOwnership(address newOwner) internal virtual {
        address oldOwner = _owner;
        _owner = newOwner;
        emit OwnershipTransferred(oldOwner, newOwner);
    }
}


// File @openzeppelin/contracts/security/Pausable.sol@v4.9.6

// Original license: SPDX_License_Identifier: MIT
// OpenZeppelin Contracts (last updated v4.7.0) (security/Pausable.sol)

pragma solidity ^0.8.0;

/**
 * @dev Contract module which allows children to implement an emergency stop
 * mechanism that can be triggered by an authorized account.
 *
 * This module is used through inheritance. It will make available the
 * modifiers `whenNotPaused` and `whenPaused`, which can be applied to
 * the functions of your contract. Note that they will not be pausable by
 * simply including this module, only once the modifiers are put in place.
 */
abstract contract Pausable is Context {
    /**
     * @dev Emitted when the pause is triggered by `account`.
     */
    event Paused(address account);

    /**
     * @dev Emitted when the pause is lifted by `account`.
     */
    event Unpaused(address account);

    bool private _paused;

    /**
     * @dev Initializes the contract in unpaused state.
     */
    constructor() {
        _paused = false;
    }

    /**
     * @dev Modifier to make a function callable only when the contract is not paused.
     *
     * Requirements:
     *
     * - The contract must not be paused.
     */
    modifier whenNotPaused() {
        _requireNotPaused();
        _;
    }

    /**
     * @dev Modifier to make a function callable only when the contract is paused.
     *
     * Requirements:
     *
     * - The contract must be paused.
     */
    modifier whenPaused() {
        _requirePaused();
        _;
    }

    /**
     * @dev Returns true if the contract is paused, and false otherwise.
     */
    function paused() public view virtual returns (bool) {
        return _paused;
    }

    /**
     * @dev Throws if the contract is paused.
     */
    function _requireNotPaused() internal view virtual {
        require(!paused(), "Pausable: paused");
    }

    /**
     * @dev Throws if the contract is not paused.
     */
    function _requirePaused() internal view virtual {
        require(paused(), "Pausable: not paused");
    }

    /**
     * @dev Triggers stopped state.
     *
     * Requirements:
     *
     * - The contract must not be paused.
     */
    function _pause() internal virtual whenNotPaused {
        _paused = true;
        emit Paused(_msgSender());
    }

    /**
     * @dev Returns to normal state.
     *
     * Requirements:
     *
     * - The contract must be paused.
     */
    function _unpause() internal virtual whenPaused {
        _paused = false;
        emit Unpaused(_msgSender());
    }
}


// File @openzeppelin/contracts/security/ReentrancyGuard.sol@v4.9.6

// Original license: SPDX_License_Identifier: MIT
// OpenZeppelin Contracts (last updated v4.9.0) (security/ReentrancyGuard.sol)

pragma solidity ^0.8.0;

/**
 * @dev Contract module that helps prevent reentrant calls to a function.
 *
 * Inheriting from `ReentrancyGuard` will make the {nonReentrant} modifier
 * available, which can be applied to functions to make sure there are no nested
 * (reentrant) calls to them.
 *
 * Note that because there is a single `nonReentrant` guard, functions marked as
 * `nonReentrant` may not call one another. This can be worked around by making
 * those functions `private`, and then adding `external` `nonReentrant` entry
 * points to them.
 *
 * TIP: If you would like to learn more about reentrancy and alternative ways
 * to protect against it, check out our blog post
 * https://blog.openzeppelin.com/reentrancy-after-istanbul/[Reentrancy After Istanbul].
 */
abstract contract ReentrancyGuard {
    // Booleans are more expensive than uint256 or any type that takes up a full
    // word because each write operation emits an extra SLOAD to first read the
    // slot's contents, replace the bits taken up by the boolean, and then write
    // back. This is the compiler's defense against contract upgrades and
    // pointer aliasing, and it cannot be disabled.

    // The values being non-zero value makes deployment a bit more expensive,
    // but in exchange the refund on every call to nonReentrant will be lower in
    // amount. Since refunds are capped to a percentage of the total
    // transaction's gas, it is best to keep them low in cases like this one, to
    // increase the likelihood of the full refund coming into effect.
    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;

    uint256 private _status;

    constructor() {
        _status = _NOT_ENTERED;
    }

    /**
     * @dev Prevents a contract from calling itself, directly or indirectly.
     * Calling a `nonReentrant` function from another `nonReentrant`
     * function is not supported. It is possible to prevent this from happening
     * by making the `nonReentrant` function external, and making it call a
     * `private` function that does the actual work.
     */
    modifier nonReentrant() {
        _nonReentrantBefore();
        _;
        _nonReentrantAfter();
    }

    function _nonReentrantBefore() private {
        // On the first call to nonReentrant, _status will be _NOT_ENTERED
        require(_status != _ENTERED, "ReentrancyGuard: reentrant call");

        // Any calls to nonReentrant after this point will fail
        _status = _ENTERED;
    }

    function _nonReentrantAfter() private {
        // By storing the original value once again, a refund is triggered (see
        // https://eips.ethereum.org/EIPS/eip-2200)
        _status = _NOT_ENTERED;
    }

    /**
     * @dev Returns true if the reentrancy guard is currently set to "entered", which indicates there is a
     * `nonReentrant` function in the call stack.
     */
    function _reentrancyGuardEntered() internal view returns (bool) {
        return _status == _ENTERED;
    }
}


// File contracts/AccessControlRegistry.sol

// Original license: SPDX_License_Identifier: MIT
pragma solidity ^0.8.20;
/**
 * @title AccessControlRegistry
 * @dev Merkezi eri┼şim kontrol├╝ sa─şlayan ana s├Âzle┼şme
 * @notice T├╝m sistem d├╝─ş├╝mlerinin eri┼şim haklar─▒n─▒ y├Âneten merkezi otorite
 *
 * ├ûzellikler:
 * - D├╝─ş├╝m tabanl─▒ eri┼şim kontrol├╝
 * - Hiyerar┼şik rol sistemi
 * - Zaman bazl─▒ eri┼şim haklar─▒
 * - Audit trail (eri┼şim ge├ğmi┼şi)
 * - Toplu i┼şlem deste─şi
 * - Acil durum m├╝dahale mekanizmalar─▒
 */
contract AccessControlRegistry is Ownable, Pausable, ReentrancyGuard {

    // --- ROLE DEFINITIONS ---
    bytes32 public constant SUPER_ADMIN_ROLE = keccak256("SUPER_ADMIN_ROLE");
    bytes32 public constant SYSTEM_ADMIN_ROLE = keccak256("SYSTEM_ADMIN_ROLE");
    bytes32 public constant NODE_MANAGER_ROLE = keccak256("NODE_MANAGER_ROLE");
    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");

    // --- NODE STATUS DEFINITIONS ---
    enum NodeStatus {
        INACTIVE,        // 0 - Pasif d├╝─ş├╝m
        ACTIVE,          // 1 - Aktif d├╝─ş├╝m
        SUSPENDED,       // 2 - Ask─▒ya al─▒nm─▒┼ş
        MAINTENANCE,     // 3 - Bak─▒m modunda
        DEPRECATED       // 4 - Kullan─▒mdan kald─▒r─▒lm─▒┼ş
    }

    enum NodeType {
        UNDEFINED,           // 0 - Tan─▒mlanmam─▒┼ş
        VERIFICATION_NODE,   // 1 - ZK Proof do─şrulama d├╝─ş├╝m├╝
        FAILURE_ANALYZER,    // 2 - Ar─▒za analiz d├╝─ş├╝m├╝
        DATA_PROCESSOR,      // 3 - Veri i┼şleme d├╝─ş├╝m├╝
        MAINTENANCE_MANAGER, // 4 - Bak─▒m y├Ânetimi d├╝─ş├╝m├╝
        AUDIT_NODE,          // 5 - Denetim d├╝─ş├╝m├╝
        GATEWAY_NODE         // 6 - API Gateway d├╝─ş├╝m├╝
    }

    // --- ACCESS LEVEL DEFINITIONS ---
    enum AccessLevel {
        NO_ACCESS,      // 0 - Eri┼şim yok
        READ_ONLY,      // 1 - Sadece okuma
        WRITE_LIMITED,  // 2 - S─▒n─▒rl─▒ yazma
        FULL_ACCESS,    // 3 - Tam eri┼şim
        ADMIN_ACCESS    // 4 - Y├Ânetici eri┼şimi
    }

    // --- STRUCTS ---
    struct Node {
        bytes32 nodeId;              // Benzersiz d├╝─ş├╝m ID'si
        string nodeName;             // D├╝─ş├╝m ad─▒
        address nodeAddress;         // D├╝─ş├╝m├╝n blockchain adresi
        NodeType nodeType;           // D├╝─ş├╝m t├╝r├╝
        NodeStatus status;           // Mevcut durum
        AccessLevel accessLevel;     // Eri┼şim seviyesi
        address owner;               // D├╝─ş├╝m sahibi
        uint256 createdAt;           // Olu┼şturulma zaman─▒
        uint256 lastActiveAt;        // Son aktif olma zaman─▒
        uint256 accessExpiresAt;     // Eri┼şim sona erme zaman─▒ (0 = s├╝resiz)
        bytes32[] assignedRoles;     // Atanm─▒┼ş roller
        bool isBlacklisted;          // Kara liste durumu
        string metadata;             // Ek bilgiler (JSON format─▒nda)
    }

    struct AccessRequest {
        bytes32 requestId;          // ─░stek ID'si
        bytes32 nodeId;             // ─░stekte bulunan d├╝─ş├╝m
        bytes32 targetResource;     // Eri┼şim istenen kaynak
        AccessLevel requestedLevel; // ─░stenen eri┼şim seviyesi
        address requester;          // ─░stekte bulunan adres
        uint256 requestedAt;        // ─░stek zaman─▒
        uint256 expiresAt;          // ─░stek sona erme zaman─▒
        bool isApproved;            // Onay durumu
        address approvedBy;         // Onaylayan adres
        string justification;       // Gerek├ğe
    }

    struct AuditLog {
        bytes32 logId;             // Log ID'si
        bytes32 nodeId;            // ─░lgili d├╝─ş├╝m
        address actor;             // ─░┼şlemi yapan
        string action;             // Yap─▒lan i┼şlem
        bytes32 targetResource;    // Hedef kaynak
        bool success;              // ─░┼şlem ba┼şar─▒l─▒ m─▒
        uint256 timestamp;         // ─░┼şlem zaman─▒
        string details;            // Detaylar
    }

    // --- STATE VARIABLES ---
    uint256 public nodeCounter;
    uint256 public requestCounter;
    uint256 public auditLogCounter;

    // Active node counter (gaz a├ğ─▒s─▒ndan O(1) sorgulama)
    uint256 public activeNodeCount;

    // Mappings
    mapping(bytes32 => Node) public nodes;                    // nodeId => Node
    mapping(address => bytes32[]) public addressToNodes;      // address => nodeId[]
    mapping(bytes32 => bool) public nodeExists;               // nodeId => exists
    mapping(bytes32 => AccessRequest) public accessRequests;  // requestId => AccessRequest
    mapping(bytes32 => AuditLog) public auditLogs;            // logId => AuditLog
    mapping(address => bool) public authorizedCallers;        // Yetkili ├ğa─ş─▒r─▒c─▒lar
    mapping(bytes32 => mapping(bytes32 => bool)) public nodePermissions; // nodeId => resource => hasPermission
    mapping(bytes32 => mapping(address => AccessLevel)) public nodeAddressPermissions; // nodeId => address => AccessLevel

    // Role mappings
    mapping(bytes32 => bool) public roles;                    // Mevcut roller
    mapping(address => mapping(bytes32 => bool)) public hasRole; // address => role => hasRole
    mapping(bytes32 => address[]) public roleMembers;         // role => addresses[]

    // System settings
    uint256 public defaultAccessDuration = 30 days;           // Varsay─▒lan eri┼şim s├╝resi
    uint256 public maxNodesPerAddress = 10;                   // Adres ba┼ş─▒na max d├╝─ş├╝m say─▒s─▒
    bool public requireApprovalForAccess = true;              // Eri┼şim i├ğin onay gerekli mi

    // --- EVENTS ---
    event NodeRegistered(bytes32 indexed nodeId, address indexed nodeAddress, NodeType nodeType, address indexed owner);
    event NodeUpdated(bytes32 indexed nodeId, NodeStatus oldStatus, NodeStatus newStatus, address indexed updatedBy);
    event NodeRemoved(bytes32 indexed nodeId, address indexed removedBy, string reason);
    event NodeStatusChanged(bytes32 indexed nodeId, NodeStatus oldStatus, NodeStatus newStatus, address indexed changedBy);

    event AccessRequested(bytes32 indexed requestId, bytes32 indexed nodeId, bytes32 indexed targetResource, AccessLevel level, address requester);
    event AccessApproved(bytes32 indexed requestId, bytes32 indexed nodeId, address indexed approvedBy);
    event AccessDenied(bytes32 indexed requestId, bytes32 indexed nodeId, address indexed deniedBy, string reason);
    event AccessRevoked(bytes32 indexed nodeId, bytes32 indexed targetResource, address indexed revokedBy);

    event RoleGranted(bytes32 indexed role, address indexed account, address indexed sender);
    event RoleRevoked(bytes32 indexed role, address indexed account, address indexed sender);
    event RoleCreated(bytes32 indexed role, address indexed creator);

    event AuditLogCreated(bytes32 indexed logId, bytes32 indexed nodeId, address indexed actor, string action);
    event EmergencyAccessGranted(bytes32 indexed nodeId, address indexed grantedBy, string reason);
    event SecurityBreach(bytes32 indexed nodeId, address indexed suspiciousAddress, string details);

    // --- MODIFIERS ---
    modifier onlyAuthorizedCaller() {
        require(authorizedCallers[msg.sender] || owner() == msg.sender, "AccessControl: Unauthorized caller");
        _;
    }

    modifier onlyValidNode(bytes32 nodeId) {
        require(nodeExists[nodeId], "AccessControl: Node does not exist");
        _;
    }

    modifier onlyActiveNode(bytes32 nodeId) {
        require(nodes[nodeId].status == NodeStatus.ACTIVE, "AccessControl: Node is not active");
        _;
    }

    modifier onlyNodeOwnerOrAdmin(bytes32 nodeId) {
        require(
            nodes[nodeId].owner == msg.sender ||
            hasRole[msg.sender][SYSTEM_ADMIN_ROLE] ||
            hasRole[msg.sender][SUPER_ADMIN_ROLE] ||
            owner() == msg.sender,
            "AccessControl: Not node owner or admin"
        );
        _;
    }

    modifier onlyRole(bytes32 role) {
        require(hasRole[msg.sender][role] || owner() == msg.sender, "AccessControl: Missing required role");
        _;
    }

    modifier notBlacklisted(address account) {
        // Adresin sahip oldu─şu d├╝─ş├╝mlerden herhangi biri kara listede mi kontrol et
        bytes32[] memory userNodes = addressToNodes[account];
        for (uint i = 0; i < userNodes.length; ++i) {
            require(!nodes[userNodes[i]].isBlacklisted, "AccessControl: Address is blacklisted");
        }
        _;
    }

    // --- CONSTRUCTOR ---
    constructor(address _initialAdmin) {
        _transferOwnership(_initialAdmin);

        // ─░lk rolleri olu┼ştur
        _createRole(SUPER_ADMIN_ROLE);
        _createRole(SYSTEM_ADMIN_ROLE);
        _createRole(NODE_MANAGER_ROLE);
        _createRole(AUDITOR_ROLE);

        // Initial admin'e s├╝per admin rol├╝ ver
        _grantRole(SUPER_ADMIN_ROLE, _initialAdmin);
        _grantRole(SYSTEM_ADMIN_ROLE, _initialAdmin);

        // Contract'─▒ yetkili ├ğa─ş─▒r─▒c─▒ olarak ekle
        authorizedCallers[address(this)] = true;

        nodeCounter = 1;
        requestCounter = 1;
        auditLogCounter = 1;
        activeNodeCount = 0;
    }

    // --- NODE MANAGEMENT FUNCTIONS ---

    /**
     * @dev Yeni d├╝─ş├╝m kaydetme
     */
    function registerNode(
        string calldata nodeName,
        address nodeAddress,
        NodeType nodeType,
        AccessLevel accessLevel,
        uint256 accessDuration,
        string calldata metadata
    ) external whenNotPaused nonReentrant notBlacklisted(msg.sender) returns (bytes32 nodeId) {
        require(nodeAddress != address(0), "AccessControl: Invalid node address");
        require(bytes(nodeName).length > 0, "AccessControl: Node name required");
        require(addressToNodes[msg.sender].length < maxNodesPerAddress, "AccessControl: Max nodes per address exceeded");

        // Benzersiz node ID olu┼ştur
        nodeId = keccak256(abi.encodePacked(msg.sender, nodeAddress, nodeName, block.timestamp, nodeCounter));
        require(!nodeExists[nodeId], "AccessControl: Node ID collision");

        // Eri┼şim s├╝resi hesapla
        uint256 expiresAt = accessDuration > 0 ? block.timestamp + accessDuration : 0;

        // D├╝─ş├╝m olu┼ştur
        nodes[nodeId] = Node({
            nodeId: nodeId,
            nodeName: nodeName,
            nodeAddress: nodeAddress,
            nodeType: nodeType,
            status: NodeStatus.ACTIVE,
            accessLevel: accessLevel,
            owner: msg.sender,
            createdAt: block.timestamp,
            lastActiveAt: block.timestamp,
            accessExpiresAt: expiresAt,
            assignedRoles: new bytes32[](0),
            isBlacklisted: false,
            metadata: metadata
        });

        nodeExists[nodeId] = true;
        addressToNodes[msg.sender].push(nodeId);
        nodeCounter++;

        // Active counter g├╝ncelle
        activeNodeCount++;

        // Audit log olu┼ştur
        _createAuditLog(nodeId, msg.sender, "NODE_REGISTERED", bytes32(0), true,
            string(abi.encodePacked("Node registered: ", nodeName)));

        emit NodeRegistered(nodeId, nodeAddress, nodeType, msg.sender);

        return nodeId;
    }

    /**
     * @dev D├╝─ş├╝m bilgilerini g├╝ncelleme
     */
    function updateNode(
        bytes32 nodeId,
        string calldata nodeName,
        NodeType nodeType,
        AccessLevel accessLevel,
        string calldata metadata
    ) external whenNotPaused onlyValidNode(nodeId) onlyNodeOwnerOrAdmin(nodeId) {
        Node storage node = nodes[nodeId];

        NodeStatus oldStatus = node.status;

        node.nodeName = nodeName;
        node.nodeType = nodeType;
        node.accessLevel = accessLevel;
        node.metadata = metadata;
        node.lastActiveAt = block.timestamp;

        // Audit log olu┼ştur
        _createAuditLog(nodeId, msg.sender, "NODE_UPDATED", bytes32(0), true, "Node information updated");

        emit NodeUpdated(nodeId, oldStatus, node.status, msg.sender);
    }

    /**
     * @dev D├╝─ş├╝m durumunu de─şi┼ştirme
     */
    function changeNodeStatus(
        bytes32 nodeId,
        NodeStatus newStatus
    ) external whenNotPaused onlyValidNode(nodeId) onlyNodeOwnerOrAdmin(nodeId) {
        Node storage node = nodes[nodeId];
        NodeStatus oldStatus = node.status;

        require(oldStatus != newStatus, "AccessControl: Status already set");

        node.status = newStatus;
        node.lastActiveAt = block.timestamp;

        // Active counter ayarla
        if (oldStatus != NodeStatus.ACTIVE && newStatus == NodeStatus.ACTIVE) {
            activeNodeCount++;
        } else if (oldStatus == NodeStatus.ACTIVE && newStatus != NodeStatus.ACTIVE) {
            if (activeNodeCount > 0) {
                activeNodeCount--;
            }
        }

        // Audit log olu┼ştur
        string memory action = string(abi.encodePacked("STATUS_CHANGED_TO_", _statusToString(newStatus)));
        _createAuditLog(nodeId, msg.sender, action, bytes32(0), true, "Node status changed");

        emit NodeStatusChanged(nodeId, oldStatus, newStatus, msg.sender);
    }

    /**
     * @dev D├╝─ş├╝m├╝ silme
     */
    function removeNode(
        bytes32 nodeId,
        string calldata reason
    ) external whenNotPaused onlyValidNode(nodeId) onlyNodeOwnerOrAdmin(nodeId) {
        Node storage node = nodes[nodeId];
        address nodeOwner = node.owner;

        // E─şer aktifse saya├ğ azalt
        if (node.status == NodeStatus.ACTIVE) {
            if (activeNodeCount > 0) {
                activeNodeCount--;
            }
        }

        // D├╝─ş├╝m├╝ pasif yap (defansif)
        node.status = NodeStatus.INACTIVE;

        // Address mapping'den ├ğ─▒kar
        _removeNodeFromAddress(nodeOwner, nodeId);

        // Node'u sil
        delete nodes[nodeId];
        nodeExists[nodeId] = false;

        // Audit log olu┼ştur
        _createAuditLog(nodeId, msg.sender, "NODE_REMOVED", bytes32(0), true, reason);

        emit NodeRemoved(nodeId, msg.sender, reason);
    }

    // --- ACCESS CONTROL FUNCTIONS ---

    /**
     * @dev Ana eri┼şim kontrol├╝ fonksiyonu - Di─şer s├Âzle┼şmeler taraf─▒ndan ├ğa─şr─▒l─▒r
     */
    function checkAccess(
        address caller,
        bytes32 resource,
        AccessLevel requiredLevel
    ) external view returns (bool hasAccess, string memory reason) {
        // Caller'─▒n d├╝─ş├╝mlerini kontrol et
        bytes32[] memory callerNodes = addressToNodes[caller];

        if (callerNodes.length == 0) {
            return (false, "No registered nodes for caller");
        }

        // Her d├╝─ş├╝m i├ğin eri┼şim kontrol├╝
        for (uint i = 0; i < callerNodes.length; ++i ){
            bytes32 nodeId = callerNodes[i];
            Node storage node = nodes[nodeId];

            // Temel kontroller
            if (node.status != NodeStatus.ACTIVE) {
                continue; // Aktif olmayan d├╝─ş├╝mleri atla
            }

            if (node.isBlacklisted) {
                return (false, "Node is blacklisted");
            }

            // Eri┼şim s├╝resi kontrol├╝
            if (node.accessExpiresAt > 0 && block.timestamp > node.accessExpiresAt) {
                continue; // S├╝resi dolmu┼ş d├╝─ş├╝mleri atla
            }

            // Eri┼şim seviyesi kontrol├╝
            if (node.accessLevel >= requiredLevel) {
                // Kaynak bazl─▒ izin kontrol├╝
                if (nodePermissions[nodeId][resource] || resource == bytes32(0)) {
                    return (true, "Access granted");
                }
            }
        }

        return (false, "Insufficient access level or permissions");
    }

    /**
     * @dev Eri┼şim iste─şi olu┼şturma
     */
    function requestAccess(
        bytes32 nodeId,
        bytes32 targetResource,
        AccessLevel requestedLevel,
        uint256 duration,
        string calldata justification
    ) external whenNotPaused onlyValidNode(nodeId) returns (bytes32 requestId) {
        require(nodes[nodeId].owner == msg.sender, "AccessControl: Not node owner");

        requestId = keccak256(abi.encodePacked(nodeId, targetResource, msg.sender, block.timestamp, requestCounter));

        accessRequests[requestId] = AccessRequest({
            requestId: requestId,
            nodeId: nodeId,
            targetResource: targetResource,
            requestedLevel: requestedLevel,
            requester: msg.sender,
            requestedAt: block.timestamp,
            expiresAt: block.timestamp + duration,
            isApproved: false,
            approvedBy: address(0),
            justification: justification
        });

        requestCounter++;

        // Audit log olu┼ştur
        _createAuditLog(nodeId, msg.sender, "ACCESS_REQUESTED", targetResource, true, justification);

        emit AccessRequested(requestId, nodeId, targetResource, requestedLevel, msg.sender);

        return requestId;
    }

    /**
     * @dev Eri┼şim iste─şini onaylama
     */
    function approveAccessRequest(
        bytes32 requestId
    ) external whenNotPaused onlyRole(SYSTEM_ADMIN_ROLE) {
        AccessRequest storage request = accessRequests[requestId];
        require(request.requestId != bytes32(0), "AccessControl: Request does not exist");
        require(!request.isApproved, "AccessControl: Request already approved");
        require(block.timestamp <= request.expiresAt, "AccessControl: Request expired");

        // ─░ste─şi onayla
        request.isApproved = true;
        request.approvedBy = msg.sender;

        // D├╝─ş├╝me izin ver
        nodePermissions[request.nodeId][request.targetResource] = true;

        // D├╝─ş├╝m├╝n eri┼şim seviyesini g├╝ncelle (gerekirse)
        if (nodes[request.nodeId].accessLevel < request.requestedLevel) {
            nodes[request.nodeId].accessLevel = request.requestedLevel;
        }

        // Audit log olu┼ştur
        _createAuditLog(request.nodeId, msg.sender, "ACCESS_APPROVED", request.targetResource, true, "Access request approved");

        emit AccessApproved(requestId, request.nodeId, msg.sender);
    }

    /**
     * @dev Eri┼şim iste─şini reddetme
     */
    function denyAccessRequest(
        bytes32 requestId,
        string calldata reason
    ) external whenNotPaused onlyRole(SYSTEM_ADMIN_ROLE) {
        AccessRequest storage request = accessRequests[requestId];
        require(request.requestId != bytes32(0), "AccessControl: Request does not exist");
        require(!request.isApproved, "AccessControl: Request already approved");

        // ─░ste─şi sil
        delete accessRequests[requestId];

        // Audit log olu┼ştur
        _createAuditLog(request.nodeId, msg.sender, "ACCESS_DENIED", request.targetResource, false, reason);

        emit AccessDenied(requestId, request.nodeId, msg.sender, reason);
    }

    /**
     * @dev Eri┼şim iznini iptal etme
     */
    function revokeAccess(
        bytes32 nodeId,
        bytes32 targetResource
    ) external whenNotPaused onlyValidNode(nodeId) onlyRole(SYSTEM_ADMIN_ROLE) {
        nodePermissions[nodeId][targetResource] = false;

        // Audit log olu┼ştur
        _createAuditLog(nodeId, msg.sender, "ACCESS_REVOKED", targetResource, true, "Access revoked by admin");

        emit AccessRevoked(nodeId, targetResource, msg.sender);
    }

    // --- ROLE MANAGEMENT FUNCTIONS ---

    /**
     * @dev Yeni rol olu┼şturma
     */
    function createRole(bytes32 role) external onlyRole(SUPER_ADMIN_ROLE) {
        _createRole(role);
    }

    function _createRole(bytes32 role) internal {
        require(!roles[role], "AccessControl: Role already exists");
        roles[role] = true;
        emit RoleCreated(role, msg.sender);
    }

    /**
     * @dev Rol verme
     */
    function grantRole(bytes32 role, address account) external onlyRole(SUPER_ADMIN_ROLE) {
        _grantRole(role, account);
    }

    function _grantRole(bytes32 role, address account) internal {
        require(account != address(0), "AccessControl: Role cannot be granted to the zero address");
        
        require(roles[role], "AccessControl: Role does not exist");
        require(!hasRole[account][role], "AccessControl: Account already has role");

        hasRole[account][role] = true;
        roleMembers[role].push(account);

        emit RoleGranted(role, account, msg.sender);
    }

    /**
     * @dev Rol iptal etme
     */
    function revokeRole(bytes32 role, address account) external onlyRole(SUPER_ADMIN_ROLE) {
        require(hasRole[account][role], "AccessControl: Account does not have role");

        hasRole[account][role] = false;

        // Role members array'den ├ğ─▒kar
        address[] storage members = roleMembers[role];
        for (uint i = 0; i < members.length; ++i) {
            if (members[i] == account) {
                members[i] = members[members.length - 1];
                members.pop();
                break;
            }
        }

        emit RoleRevoked(role, account, msg.sender);
    }

    // --- EMERGENCY FUNCTIONS ---

    /**
     * @dev Acil durum eri┼şimi verme
     */
    function grantEmergencyAccess(
        bytes32 nodeId,
        bytes32 targetResource,
        string calldata reason
    ) external onlyRole(SUPER_ADMIN_ROLE) {
        require(nodeExists[nodeId], "AccessControl: Node does not exist");

        // ├ûnce mevcut status al
        NodeStatus oldStatus = nodes[nodeId].status;

        // D├╝─ş├╝m├╝ aktif yap ve tam eri┼şim ver
        nodes[nodeId].status = NodeStatus.ACTIVE;
        nodes[nodeId].accessLevel = AccessLevel.ADMIN_ACCESS;
        nodes[nodeId].isBlacklisted = false;
        nodePermissions[nodeId][targetResource] = true;

        // E─şer eskiden aktif de─şilse saya├ğ art─▒r
        if (oldStatus != NodeStatus.ACTIVE) {
            activeNodeCount++;
        }

        // Audit log olu┼ştur
        _createAuditLog(nodeId, msg.sender, "EMERGENCY_ACCESS_GRANTED", targetResource, true, reason);

        emit EmergencyAccessGranted(nodeId, msg.sender, reason);
    }

    /**
     * @dev G├╝venlik ihlali bildirimi
     */
    function reportSecurityBreach(
        bytes32 nodeId,
        address suspiciousAddress,
        string calldata details
    ) external onlyAuthorizedCaller {
        // D├╝─ş├╝m├╝ ask─▒ya al
        if (nodeExists[nodeId]) {
            // E─şer ├Ânceden aktifse saya├ğ azalt
            if (nodes[nodeId].status == NodeStatus.ACTIVE) {
                if (activeNodeCount > 0) {
                    activeNodeCount--;
                }
            }
            nodes[nodeId].status = NodeStatus.SUSPENDED;
        }

        // Audit log olu┼ştur
        _createAuditLog(nodeId, msg.sender, "SECURITY_BREACH_REPORTED", bytes32(0), false, details);

        emit SecurityBreach(nodeId, suspiciousAddress, details);
    }

    /**
     * @dev D├╝─ş├╝m├╝ kara listeye alma
     */
    function blacklistNode(
        bytes32 nodeId,
        string calldata reason
    ) external onlyRole(SYSTEM_ADMIN_ROLE) onlyValidNode(nodeId) {
        // E─şer aktifse saya├ğ azalt
        if (nodes[nodeId].status == NodeStatus.ACTIVE) {
            if (activeNodeCount > 0) {
                activeNodeCount--;
            }
        }

        nodes[nodeId].isBlacklisted = true;
        nodes[nodeId].status = NodeStatus.SUSPENDED;

        // Audit log olu┼ştur
        _createAuditLog(nodeId, msg.sender, "NODE_BLACKLISTED", bytes32(0), true, reason);
    }

    /**
     * @dev D├╝─ş├╝m├╝ kara listeden ├ğ─▒karma
     */
    function unblacklistNode(
        bytes32 nodeId,
        string calldata reason
    ) external onlyRole(SUPER_ADMIN_ROLE) onlyValidNode(nodeId) {
        // E─şer ┼şu an blacklisted ise ve status ACTIVE de─şilse active yap ve saya├ğ artt─▒r
        bool wasBlacklisted = nodes[nodeId].isBlacklisted;
        NodeStatus oldStatus = nodes[nodeId].status;

        nodes[nodeId].isBlacklisted = false;
        nodes[nodeId].status = NodeStatus.ACTIVE;

        if (wasBlacklisted && oldStatus != NodeStatus.ACTIVE) {
            activeNodeCount++;
        }

        // Audit log olu┼ştur
        _createAuditLog(nodeId, msg.sender, "NODE_UNBLACKLISTED", bytes32(0), true, reason);
    }

    // --- AUDIT FUNCTIONS ---

    /**
     * @dev Audit log olu┼şturma
     */
    function _createAuditLog(
        bytes32 nodeId,
        address actor,
        string memory action,
        bytes32 targetResource,
        bool success,
        string memory details
    ) internal {
        bytes32 logId = keccak256(abi.encodePacked(nodeId, actor, action, block.timestamp, auditLogCounter));

        auditLogs[logId] = AuditLog({
            logId: logId,
            nodeId: nodeId,
            actor: actor,
            action: action,
            targetResource: targetResource,
            success: success,
            timestamp: block.timestamp,
            details: details
        });

        auditLogCounter++;

        emit AuditLogCreated(logId, nodeId, actor, action);
    }

    // --- VIEW FUNCTIONS ---

    /**
     * @dev D├╝─ş├╝m bilgilerini getirme
     */
    function getNode(bytes32 nodeId) external view returns (Node memory) {
        require(nodeExists[nodeId], "AccessControl: Node does not exist");
        return nodes[nodeId];
    }

    /**
     * @dev Adresin d├╝─ş├╝mlerini getirme
     */
    function getNodesByAddress(address nodeOwner) external view returns (bytes32[] memory) {
        return addressToNodes[nodeOwner];
    }

    /**
     * @dev Aktif d├╝─ş├╝m say─▒s─▒n─▒ getirme
     * @notice O(1) ÔÇö saya├ğ ├╝zerinden d├Ând├╝r├╝l├╝r
     */
    function getActiveNodeCount() external view returns (uint256) {
        return activeNodeCount;
    }

    /**
     * @dev Rol ├╝yelerini getirme
     */
    function getRoleMembers(bytes32 role) external view returns (address[] memory) {
        return roleMembers[role];
    }

    // --- ADMIN FUNCTIONS ---

    /**
     * @dev Yetkili ├ğa─ş─▒r─▒c─▒ ekleme
     */
    function addAuthorizedCaller(address caller) external onlyRole(SUPER_ADMIN_ROLE) {
        authorizedCallers[caller] = true;
    }

    /**
     * @dev Yetkili ├ğa─ş─▒r─▒c─▒ ├ğ─▒karma
     */
    function removeAuthorizedCaller(address caller) external onlyRole(SUPER_ADMIN_ROLE) {
        authorizedCallers[caller] = false;
    }

    /**
     * @dev Sistem ayarlar─▒n─▒ g├╝ncelleme
     */
    function updateSystemSettings(
        uint256 _defaultAccessDuration,
        uint256 _maxNodesPerAddress,
        bool _requireApprovalForAccess
    ) external onlyRole(SUPER_ADMIN_ROLE) {
        defaultAccessDuration = _defaultAccessDuration;
        maxNodesPerAddress = _maxNodesPerAddress;
        requireApprovalForAccess = _requireApprovalForAccess;
    }

    /**
     * @dev Acil durum durdurma
     */
    function emergencyPause() external onlyRole(SUPER_ADMIN_ROLE) {
        _pause();
    }

    /**
     * @dev Sistemi tekrar ba┼şlatma
     */
    function unpause() external onlyRole(SUPER_ADMIN_ROLE) {
        _unpause();
    }

    // --- UTILITY FUNCTIONS ---

    function _removeNodeFromAddress(address nodeOwner, bytes32 nodeId) internal {
        bytes32[] storage userNodes = addressToNodes[nodeOwner];
        for (uint i = 0; i < userNodes.length; ++i) {
            if (userNodes[i] == nodeId) {
                userNodes[i] = userNodes[userNodes.length - 1];
                userNodes.pop();
                break;
            }
        }
    }

    function _statusToString(NodeStatus status) internal pure returns (string memory) {
        if (status == NodeStatus.INACTIVE) return "INACTIVE";
        if (status == NodeStatus.ACTIVE) return "ACTIVE";
        if (status == NodeStatus.SUSPENDED) return "SUSPENDED";
        if (status == NodeStatus.MAINTENANCE) return "MAINTENANCE";
        if (status == NodeStatus.DEPRECATED) return "DEPRECATED";
        return "UNKNOWN";
    }

    // --- BATCH OPERATIONS ---

    /**
     * @dev Toplu d├╝─ş├╝m durumu g├╝ncelleme
     */
    function batchUpdateNodeStatus(
        bytes32[] calldata nodeIds,
        NodeStatus newStatus
    ) external onlyRole(SYSTEM_ADMIN_ROLE) {
        for (uint i = 0; i < nodeIds.length; ++i) {
            bytes32 id = nodeIds[i];
            if (nodeExists[id]) {
                NodeStatus oldStatus = nodes[id].status;
                // Saya├ğ g├╝ncellemesi
                if (oldStatus != NodeStatus.ACTIVE && newStatus == NodeStatus.ACTIVE) {
                    activeNodeCount++;
                } else if (oldStatus == NodeStatus.ACTIVE && newStatus != NodeStatus.ACTIVE) {
                    if (activeNodeCount > 0) {
                        activeNodeCount--;
                    }
                }
                nodes[id].status = newStatus;
                emit NodeStatusChanged(id, oldStatus, newStatus, msg.sender);
            }
        }
    }

    /**
     * @dev Toplu eri┼şim iptal etme
     */
    function batchRevokeAccess(
        bytes32[] calldata nodeIds,
        bytes32 targetResource
    ) external onlyRole(SYSTEM_ADMIN_ROLE) {
        for (uint i = 0; i < nodeIds.length; ++i) {
            if (nodeExists[nodeIds[i]]) {
                nodePermissions[nodeIds[i]][targetResource] = false;
                emit AccessRevoked(nodeIds[i], targetResource, msg.sender);
            }
        }
    }
}
