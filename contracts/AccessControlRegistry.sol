// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title AccessControlRegistry
 * @dev Merkezi erişim kontrolü sağlayan ana sözleşme
 * @notice Tüm sistem düğümlerinin erişim haklarını yöneten merkezi otorite
 *
 * Özellikler:
 * - Düğüm tabanlı erişim kontrolü
 * - Hiyerarşik rol sistemi
 * - Zaman bazlı erişim hakları
 * - Audit trail (erişim geçmişi)
 * - Toplu işlem desteği
 * - Acil durum müdahale mekanizmaları
 */
contract AccessControlRegistry is Ownable, Pausable, ReentrancyGuard {

    // --- ROLE DEFINITIONS ---
    bytes32 public constant SUPER_ADMIN_ROLE = keccak256("SUPER_ADMIN_ROLE");
    bytes32 public constant SYSTEM_ADMIN_ROLE = keccak256("SYSTEM_ADMIN_ROLE");
    bytes32 public constant ENGINEER_ROLE = keccak256("ENGINEER_ROLE");
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");

    // --- RESOURCE DEFINITIONS ---
    bytes32 public constant SENSOR_DATA_RESOURCE = keccak256("SENSOR_DATA");
    bytes32 public constant PREDICTION_RESOURCE = keccak256("PREDICTION");
    bytes32 public constant MAINTENANCE_RESOURCE = keccak256("MAINTENANCE");
    bytes32 public constant CONFIG_RESOURCE = keccak256("CONFIG");
    bytes32 public constant AUDIT_LOGS_RESOURCE = keccak256("AUDIT_LOGS");

    // --- NODE STATUS DEFINITIONS ---
    enum NodeStatus {
        INACTIVE,        // 0 - Pasif düğüm (geçici olarak kullanım dışı)
        ACTIVE,          // 1 - Aktif düğüm (çalışıyor)
        SUSPENDED        // 2 - Askıya alınmış (blacklist, güvenlik ihlali)
    }


    enum NodeType {
        UNDEFINED,           // 0 - Tanımlanmamış
        DATA_PROCESSOR,      // 1 - Veri işleme düğümü (Operator - sensor data)
        FAILURE_ANALYZER,    // 2 - Arıza analiz düğümü (Engineer - predictions)
        MANAGER              // 3 - Yönetici düğümü (Manager - system administration)

    }

    // --- ACCESS LEVEL DEFINITIONS ---
    enum AccessLevel {
        NO_ACCESS,      // 0 - Erişim yok
        READ_ONLY,      // 1 - Sadece okuma
        WRITE_LIMITED,  // 2 - Sınırlı yazma
        FULL_ACCESS,    // 3 - Tam erişim
        ADMIN_ACCESS    // 4 - Yönetici erişimi
    }

    // --- STRUCTS ---
    struct Node {
        bytes32 nodeId;              // Benzersiz düğüm ID'si
        string nodeName;             // Düğüm adı
        address nodeAddress;         // Düğümün blockchain adresi
        NodeType nodeType;           // Düğüm türü
        NodeStatus status;           // Mevcut durum
        AccessLevel accessLevel;     // Erişim seviyesi
        address owner;               // Düğüm sahibi
        uint256 createdAt;           // Oluşturulma zamanı
        uint256 lastActiveAt;        // Son aktif olma zamanı
        uint256 accessExpiresAt;     // Erişim sona erme zamanı (0 = süresiz)
        bytes32[] assignedRoles;     // Atanmış roller
        bool isBlacklisted;          // Kara liste durumu
        string metadata;             // Ek bilgiler (JSON formatında)
    }

    struct AccessRequest {
        bytes32 requestId;          // İstek ID'si
        bytes32 nodeId;             // İstekte bulunan düğüm
        bytes32 targetResource;     // Erişim istenen kaynak
        AccessLevel requestedLevel; // İstenen erişim seviyesi
        address requester;          // İstekte bulunan adres
        uint256 requestedAt;        // İstek zamanı
        uint256 expiresAt;          // İstek sona erme zamanı
        bool isApproved;            // Onay durumu
        address approvedBy;         // Onaylayan adres
        string justification;       // Gerekçe
    }

    struct AuditLog {
        bytes32 logId;             // Log ID'si
        bytes32 nodeId;            // İlgili düğüm
        address actor;             // İşlemi yapan
        string action;             // Yapılan işlem
        bytes32 targetResource;    // Hedef kaynak
        bool success;              // İşlem başarılı mı
        uint256 timestamp;         // İşlem zamanı
        string details;            // Detaylar
    }

    // --- STATE VARIABLES ---
    uint256 public nodeCounter;
    uint256 public requestCounter;
    uint256 public auditLogCounter;

    // Active node counter (gaz açısından O(1) sorgulama)
    uint256 public activeNodeCount;

    // Mappings
    mapping(bytes32 => Node) public nodes;                    // nodeId => Node
    mapping(address => bytes32[]) public addressToNodes;      // address => nodeId[]
    mapping(bytes32 => bool) public nodeExists;               // nodeId => exists
    mapping(bytes32 => AccessRequest) public accessRequests;  // requestId => AccessRequest
    mapping(bytes32 => AuditLog) public auditLogs;            // logId => AuditLog
    mapping(address => bool) public authorizedCallers;        // Yetkili çağırıcılar
    mapping(bytes32 => mapping(bytes32 => bool)) public nodePermissions; // nodeId => resource => hasPermission
    mapping(bytes32 => mapping(address => AccessLevel)) public nodeAddressPermissions; // nodeId => address => AccessLevel

    // Role mappings
    mapping(bytes32 => bool) public roles;                    // Mevcut roller
    mapping(address => mapping(bytes32 => bool)) public hasRole; // address => role => hasRole
    mapping(bytes32 => address[]) public roleMembers;         // role => addresses[]

    // System settings
    uint256 public defaultAccessDuration = 30 days;           // Varsayılan erişim süresi
    uint256 public maxNodesPerAddress = 10;                   // Adres başına max düğüm sayısı
    bool public requireApprovalForAccess = true;              // Erişim için onay gerekli mi

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
        // Adresin sahip olduğu düğümlerden herhangi biri kara listede mi kontrol et
        bytes32[] memory userNodes = addressToNodes[account];
        for (uint i = 0; i < userNodes.length; i++) {
            require(!nodes[userNodes[i]].isBlacklisted, "AccessControl: Address is blacklisted");
        }
        _;
    }

    // --- CONSTRUCTOR ---
    constructor(address _initialAdmin) {
        require(_initialAdmin != address(0), "AccessControl: Invalid admin");
        _transferOwnership(_initialAdmin);

        // İlk rolleri oluştur
        _createRole(SUPER_ADMIN_ROLE);
        _createRole(SYSTEM_ADMIN_ROLE);
        _createRole(ENGINEER_ROLE);
        _createRole(OPERATOR_ROLE);

        // Initial admin'e süper admin rolü ver
        _grantRole(SUPER_ADMIN_ROLE, _initialAdmin);
        _grantRole(SYSTEM_ADMIN_ROLE, _initialAdmin);

        // Contract'ı yetkili çağırıcı olarak ekle
        authorizedCallers[address(this)] = true;

        nodeCounter = 1;
        requestCounter = 1;
        auditLogCounter = 1;
        activeNodeCount = 0;
    }

    // --- NODE MANAGEMENT FUNCTIONS ---

    /**
     * @dev Yeni düğüm kaydetme
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

        // Benzersiz node ID oluştur
        nodeId = keccak256(abi.encodePacked(msg.sender, nodeAddress, nodeName, block.timestamp, nodeCounter));
        require(!nodeExists[nodeId], "AccessControl: Node ID collision");

        // Erişim süresi hesapla
        uint256 expiresAt = accessDuration > 0 ? block.timestamp + accessDuration : 0;

        // Düğüm oluştur
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

        // Active counter güncelle
        activeNodeCount++;

        // 🚀 AUTO-GRANT: Node tipine göre otomatik erişim izinleri ver
        _autoGrantPermissionsByNodeType(nodeId, nodeType);

        // Audit log oluştur
        _createAuditLog(nodeId, msg.sender, "NODE_REGISTERED", bytes32(0), true,
            string(abi.encodePacked("Node registered: ", nodeName)));

        emit NodeRegistered(nodeId, nodeAddress, nodeType, msg.sender);

        return nodeId;
    }

    /**
     * @dev Düğüm bilgilerini güncelleme
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

        // Audit log oluştur
        _createAuditLog(nodeId, msg.sender, "NODE_UPDATED", bytes32(0), true, "Node information updated");

        emit NodeUpdated(nodeId, oldStatus, node.status, msg.sender);
    }

    /**
     * @dev Düğüm durumunu değiştirme
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

        // Audit log oluştur
        string memory action = string(abi.encodePacked("STATUS_CHANGED_TO_", _statusToString(newStatus)));
        _createAuditLog(nodeId, msg.sender, action, bytes32(0), true, "Node status changed");

        emit NodeStatusChanged(nodeId, oldStatus, newStatus, msg.sender);
    }

    /**
     * @dev Düğümü silme
     */
    function removeNode(
        bytes32 nodeId,
        string calldata reason
    ) external whenNotPaused onlyValidNode(nodeId) onlyNodeOwnerOrAdmin(nodeId) {
        Node storage node = nodes[nodeId];
        address nodeOwner = node.owner;

        // Eğer aktifse sayaç azalt
        if (node.status == NodeStatus.ACTIVE) {
            if (activeNodeCount > 0) {
                activeNodeCount--;
            }
        }

        // Düğümü pasif yap (defansif)
        node.status = NodeStatus.INACTIVE;

        // Address mapping'den çıkar
        _removeNodeFromAddress(nodeOwner, nodeId);

        // Node'u sil
        delete nodes[nodeId];
        nodeExists[nodeId] = false;

        // Audit log oluştur
        _createAuditLog(nodeId, msg.sender, "NODE_REMOVED", bytes32(0), true, reason);

        emit NodeRemoved(nodeId, msg.sender, reason);
    }

    // --- ACCESS CONTROL FUNCTIONS ---

    /**
     * @dev Ana erişim kontrolü fonksiyonu - Diğer sözleşmeler tarafından çağrılır
     */
    function checkAccess(
        address caller,
        bytes32 resource,
        AccessLevel requiredLevel
    ) external view returns (bool hasAccess, string memory reason) {
        // Caller'ın düğümlerini kontrol et
        bytes32[] memory callerNodes = addressToNodes[caller];

        if (callerNodes.length == 0) {
            return (false, "No registered nodes for caller");
        }

        // Her düğüm için erişim kontrolü
        for (uint i = 0; i < callerNodes.length; i++) {
            bytes32 nodeId = callerNodes[i];
            Node storage node = nodes[nodeId];

            // Temel kontroller
            if (node.status != NodeStatus.ACTIVE) {
                continue; // Aktif olmayan düğümleri atla
            }

            if (node.isBlacklisted) {
                return (false, "Node is blacklisted");
            }

            // Erişim süresi kontrolü
            if (node.accessExpiresAt > 0 && block.timestamp > node.accessExpiresAt) {
                continue; // Süresi dolmuş düğümleri atla
            }

            // Erişim seviyesi kontrolü
            if (node.accessLevel >= requiredLevel) {
                // Kaynak bazlı izin kontrolü
                if (nodePermissions[nodeId][resource] || resource == bytes32(0)) {
                    return (true, "Access granted");
                }
            }
        }

        return (false, "Insufficient access level or permissions");
    }

    /**
     * @dev Erişim isteği oluşturma
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

        // Audit log oluştur
        _createAuditLog(nodeId, msg.sender, "ACCESS_REQUESTED", targetResource, true, justification);

        emit AccessRequested(requestId, nodeId, targetResource, requestedLevel, msg.sender);

        return requestId;
    }

    /**
     * @dev Erişim isteğini onaylama
     */
    function approveAccessRequest(
        bytes32 requestId
    ) external whenNotPaused onlyRole(SYSTEM_ADMIN_ROLE) {
        AccessRequest storage request = accessRequests[requestId];
        require(request.requestId != bytes32(0), "AccessControl: Request does not exist");
        require(!request.isApproved, "AccessControl: Request already approved");

        require(block.timestamp <= request.expiresAt, "AccessControl: Request expired");

        // İsteği onayla
        request.isApproved = true;
        request.approvedBy = msg.sender;

        // Düğüme izin ver
        nodePermissions[request.nodeId][request.targetResource] = true;

        // Düğümün erişim seviyesini güncelle (gerekirse)
        if (nodes[request.nodeId].accessLevel < request.requestedLevel) {
            nodes[request.nodeId].accessLevel = request.requestedLevel;
        }

        // Audit log oluştur
        _createAuditLog(request.nodeId, msg.sender, "ACCESS_APPROVED", request.targetResource, true, "Access request approved");

        emit AccessApproved(requestId, request.nodeId, msg.sender);
    }

    /**
     * @dev Erişim isteğini reddetme
     */
    function denyAccessRequest(
        bytes32 requestId,
        string calldata reason
    ) external whenNotPaused onlyRole(SYSTEM_ADMIN_ROLE) {
        AccessRequest storage request = accessRequests[requestId];
        require(request.requestId != bytes32(0), "AccessControl: Request does not exist");
        require(!request.isApproved, "AccessControl: Request already approved");
        // Silmeden önce gerekli alanları kopyala
        bytes32 nodeId = request.nodeId;
        bytes32 targetResource = request.targetResource;

        // İsteği sil

        // İsteği sil
        delete accessRequests[requestId];

        // Audit log oluştur
        _createAuditLog(nodeId, msg.sender, "ACCESS_DENIED", targetResource, false, reason);

        emit AccessDenied(requestId, nodeId, msg.sender, reason);
    }

    /**
     * @dev Erişim iznini iptal etme
     */
    function revokeAccess(
        bytes32 nodeId,
        bytes32 targetResource
    ) external whenNotPaused onlyValidNode(nodeId) onlyRole(SYSTEM_ADMIN_ROLE) {
        nodePermissions[nodeId][targetResource] = false;

        // Audit log oluştur
        _createAuditLog(nodeId, msg.sender, "ACCESS_REVOKED", targetResource, true, "Access revoked by admin");

        emit AccessRevoked(nodeId, targetResource, msg.sender);
    }

    // --- ROLE MANAGEMENT FUNCTIONS ---

    /**
     * @dev Yeni rol oluşturma
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

        // Role members array'den çıkar
        address[] storage members = roleMembers[role];
        for (uint i = 0; i < members.length; i++) {
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
     * @dev Acil durum erişimi verme
     */
    function grantEmergencyAccess(
        bytes32 nodeId,
        bytes32 targetResource,
        string calldata reason
    ) external onlyRole(SUPER_ADMIN_ROLE) {
        require(nodeExists[nodeId], "AccessControl: Node does not exist");

        // Önce mevcut status al
        NodeStatus oldStatus = nodes[nodeId].status;

        // Düğümü aktif yap ve tam erişim ver
        nodes[nodeId].status = NodeStatus.ACTIVE;
        nodes[nodeId].accessLevel = AccessLevel.ADMIN_ACCESS;
        nodes[nodeId].isBlacklisted = false;
        nodePermissions[nodeId][targetResource] = true;

        // Eğer eskiden aktif değilse sayaç artır
        if (oldStatus != NodeStatus.ACTIVE) {
            activeNodeCount++;
        }

        // Audit log oluştur
        _createAuditLog(nodeId, msg.sender, "EMERGENCY_ACCESS_GRANTED", targetResource, true, reason);

        emit EmergencyAccessGranted(nodeId, msg.sender, reason);
    }

    /**
     * @dev Güvenlik ihlali bildirimi
     */
    function reportSecurityBreach(
        bytes32 nodeId,
        address suspiciousAddress,
        string calldata details
    ) external onlyAuthorizedCaller {
        // Düğümü askıya al
        if (nodeExists[nodeId]) {
            // Eğer önceden aktifse sayaç azalt
            if (nodes[nodeId].status == NodeStatus.ACTIVE) {
                if (activeNodeCount > 0) {
                    activeNodeCount--;
                }
            }
            nodes[nodeId].status = NodeStatus.SUSPENDED;
        }

        // Audit log oluştur
        _createAuditLog(nodeId, msg.sender, "SECURITY_BREACH_REPORTED", bytes32(0), false, details);

        emit SecurityBreach(nodeId, suspiciousAddress, details);
    }

    /**
     * @dev Düğümü kara listeye alma
     */
    function blacklistNode(
        bytes32 nodeId,
        string calldata reason
    ) external onlyRole(SYSTEM_ADMIN_ROLE) onlyValidNode(nodeId) {
        // Eğer aktifse sayaç azalt
        if (nodes[nodeId].status == NodeStatus.ACTIVE) {
            if (activeNodeCount > 0) {
                activeNodeCount--;
            }
        }

        nodes[nodeId].isBlacklisted = true;
        nodes[nodeId].status = NodeStatus.SUSPENDED;

        // Audit log oluştur
        _createAuditLog(nodeId, msg.sender, "NODE_BLACKLISTED", bytes32(0), true, reason);
    }

    /**
     * @dev Düğümü kara listeden çıkarma
     */
    function unblacklistNode(
        bytes32 nodeId,
        string calldata reason
    ) external onlyRole(SUPER_ADMIN_ROLE) onlyValidNode(nodeId) {
        // Eğer şu an blacklisted ise ve status ACTIVE değilse active yap ve sayaç arttır
        bool wasBlacklisted = nodes[nodeId].isBlacklisted;
        NodeStatus oldStatus = nodes[nodeId].status;

        nodes[nodeId].isBlacklisted = false;
        nodes[nodeId].status = NodeStatus.ACTIVE;

        if (wasBlacklisted && oldStatus != NodeStatus.ACTIVE) {
            activeNodeCount++;
        }

        // Audit log oluştur
        _createAuditLog(nodeId, msg.sender, "NODE_UNBLACKLISTED", bytes32(0), true, reason);
    }

    // --- AUDIT FUNCTIONS ---

    /**
     * @dev Audit log oluşturma
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
     * @dev Düğüm bilgilerini getirme
     */
    function getNode(bytes32 nodeId) external view returns (Node memory) {
        require(nodeExists[nodeId], "AccessControl: Node does not exist");
        return nodes[nodeId];
    }

    /**
     * @dev Adresin düğümlerini getirme
     */
    function getNodesByAddress(address nodeOwner) external view returns (bytes32[] memory) {
        return addressToNodes[nodeOwner];
    }

    /**
     * @dev Aktif düğüm sayısını getirme
     * @notice O(1) — sayaç üzerinden döndürülür
     */
    function getActiveNodeCount() external view returns (uint256) {
        return activeNodeCount;
    }

    /**
     * @dev Rol üyelerini getirme
     */
    function getRoleMembers(bytes32 role) external view returns (address[] memory) {
        return roleMembers[role];
    }

    // --- ADMIN FUNCTIONS ---

    /**
     * @dev Yetkili çağırıcı ekleme
     */
    function addAuthorizedCaller(address caller) external onlyRole(SUPER_ADMIN_ROLE) {
        authorizedCallers[caller] = true;
    }

    /**
     * @dev Yetkili çağırıcı çıkarma
     */
    function removeAuthorizedCaller(address caller) external onlyRole(SUPER_ADMIN_ROLE) {
        authorizedCallers[caller] = false;
    }

    /**
     * @dev Sistem ayarlarını güncelleme
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
     * @dev Sistemi tekrar başlatma
     */
    function unpause() external onlyRole(SUPER_ADMIN_ROLE) {
        _unpause();
    }

    // --- UTILITY FUNCTIONS ---

    function _removeNodeFromAddress(address nodeOwner, bytes32 nodeId) internal {
        bytes32[] storage userNodes = addressToNodes[nodeOwner];
        for (uint i = 0; i < userNodes.length; i++) {
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
        return "UNKNOWN";
    }

    // --- BATCH OPERATIONS ---

    /**
     * @dev Toplu düğüm durumu güncelleme
     */
    function batchUpdateNodeStatus(
        bytes32[] calldata nodeIds,
        NodeStatus newStatus
    ) external onlyRole(SYSTEM_ADMIN_ROLE) {
        for (uint i = 0; i < nodeIds.length; i++) {
            bytes32 id = nodeIds[i];
            if (nodeExists[id]) {
                NodeStatus oldStatus = nodes[id].status;
                // Sayaç güncellemesi
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
     * @dev Toplu erişim iptal etme
     */
    function batchRevokeAccess(
        bytes32[] calldata nodeIds,
        bytes32 targetResource
    ) external onlyRole(SYSTEM_ADMIN_ROLE) {
        for (uint i = 0; i < nodeIds.length; i++) {
            if (nodeExists[nodeIds[i]]) {
                nodePermissions[nodeIds[i]][targetResource] = false;
                emit AccessRevoked(nodeIds[i], targetResource, msg.sender);
            }
        }
    }

    // --- INTERNAL HELPER FUNCTIONS ---

    /**
     * @dev Node tipine göre otomatik kaynak erişim izinleri ver
     * @notice Bu fonksiyon registerNode sırasında otomatik çağrılır
     */
    function _autoGrantPermissionsByNodeType(bytes32 nodeId, NodeType nodeType) internal {
        address nodeOwner = nodes[nodeId].owner;
        
        if (nodeType == NodeType.DATA_PROCESSOR) {
            // Operator: Sensör verisi gönderebilir
            nodePermissions[nodeId][SENSOR_DATA_RESOURCE] = true;
            // Düğüm sahibine OPERATOR_ROLE rolünü otomatik olarak ata
            if (!hasRole[nodeOwner][OPERATOR_ROLE]) {
                _grantRole(OPERATOR_ROLE, nodeOwner);
            }
            emit AccessApproved(bytes32(0), nodeId, address(this));
            
        } else if (nodeType == NodeType.FAILURE_ANALYZER) {
            // Engineer: Tahmin verisi gönderebilir + Sensör verisi okuyabilir
            nodePermissions[nodeId][PREDICTION_RESOURCE] = true;
            nodePermissions[nodeId][SENSOR_DATA_RESOURCE] = true; // Read access for analysis
            // Düğüm sahibine ENGINEER_ROLE rolünü otomatik olarak ata
            if (!hasRole[nodeOwner][ENGINEER_ROLE]) {
                _grantRole(ENGINEER_ROLE, nodeOwner);
            }
            emit AccessApproved(bytes32(0), nodeId, address(this));
            
        } else if (nodeType == NodeType.MANAGER) {
            // Manager: Tüm kaynaklara erişim + SYSTEM_ADMIN rolü
            nodePermissions[nodeId][SENSOR_DATA_RESOURCE] = true;
            nodePermissions[nodeId][PREDICTION_RESOURCE] = true;
            nodePermissions[nodeId][CONFIG_RESOURCE] = true;
            nodePermissions[nodeId][AUDIT_LOGS_RESOURCE] = true;
            
            // Otomatik olarak SYSTEM_ADMIN rolü ver
            if (!hasRole[nodeOwner][SYSTEM_ADMIN_ROLE]) {
                _grantRole(SYSTEM_ADMIN_ROLE, nodeOwner);
            }
            
            emit AccessApproved(bytes32(0), nodeId, address(this));
        }
    }
}
