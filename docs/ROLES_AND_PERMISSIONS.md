# 🔐 PDM Sistem - Roller ve Yetkiler

**Tarih:** 8 Ekim 2025  
**Durum:** ✅ Güncel

---

## 📊 **1. NODE TİPLERİ ve OTOMATIK YETKİLER**

### **Tablo 1: Node Tipi → Otomatik İzinler ve Roller**

| **Node Type** | **Enum Value** | **Kullanıcı Rolü** | **Otomatik Erişim Kaynakları** | **Otomatik Atanan Rol** | **AccessLevel** |
|---------------|----------------|-------------------|--------------------------------|------------------------|-----------------|
| `UNDEFINED` | 0 | - | Yok | - | `NO_ACCESS` |
| `DATA_PROCESSOR` | 1 | Operator | `SENSOR_DATA` (Write) | - | `WRITE_LIMITED` |
| `FAILURE_ANALYZER` | 2 | Engineer | `PREDICTION` (Write)<br/>`SENSOR_DATA` (Read) | - | `WRITE_LIMITED` |
| `MANAGER` | 3 | Manager | `SENSOR_DATA` (Read/Write)<br/>`PREDICTION` (Read/Write)<br/>`CONFIG` (Read/Write)<br/>`AUDIT_LOGS` (Read) | `SYSTEM_ADMIN_ROLE` 👑 | `FULL_ACCESS` / `ADMIN_ACCESS` |

### **Açıklamalar:**

#### **🔹 UNDEFINED (0)**
- **Kullanım:** Tanımlanmamış/geçici node'lar
- **Erişim:** Manuel izin gerekli
- **Özel Durum:** Sistem tarafından otomatik izin verilmez

#### **🔹 DATA_PROCESSOR (1)**
- **Kullanım:** Operatör rolü, sensör veri toplama
- **Ana Fonksiyon:** `submitSensorDataProof()`
- **Erişim:** Sadece sensör verisi gönderebilir
- **Kısıtlama:** Prediction veya config erişimi yok

#### **🔹 FAILURE_ANALYZER (2)**
- **Kullanım:** Mühendis rolü, arıza analizi
- **Ana Fonksiyon:** `submitPredictionProof()`
- **Erişim:** Tahmin verisi gönderebilir + Sensör verisi okuyabilir (analiz için)
- **Özellik:** Engineer'ın analiz yapabilmesi için sensor data'ya read access gerekli

#### **🔹 MANAGER (3)** 🆕
- **Kullanım:** Yönetici rolü, sistem administrasyonu
- **Ana Fonksiyonlar:** `registerNode()`, `approveAccessRequest()`, `blacklistNode()`, vb.
- **Erişim:** Tüm kaynaklara tam erişim
- **Özellik:** Node kaydı sırasında otomatik olarak `SYSTEM_ADMIN_ROLE` verilir
- **Güç:** Diğer node'ları kaydedebilir, erişim izinlerini yönetebilir

---

## 👑 **2. ROLLER ve YETKİLER**

### **Tablo 2: Rol → Yetkiler Matrisi**

| **Fonksiyon** | **Açıklama** | **SUPER_ADMIN** | **SYSTEM_ADMIN** | **NODE_MANAGER** | **AUDITOR** |
|---------------|--------------|-----------------|------------------|------------------|-------------|
| **Rol Yönetimi** |  |  |  |  |  |
| `createRole()` | Yeni rol oluştur | ✅ | ❌ | ❌ | ❌ |
| `grantRole()` | Rol ata | ✅ | ❌ | ❌ | ❌ |
| `revokeRole()` | Rolü kaldır | ✅ | ❌ | ❌ | ❌ |
| **Node Yönetimi** |  |  |  |  |  |
| `registerNode()` | Yeni node kaydet | ✅ | ✅ | ⚠️ Sınırlı | ❌ |
| `updateNode()` | Node güncelle | ✅ | ✅ | ✅ (kendi) | ❌ |
| `removeNode()` | Node sil | ✅ | ✅ | ✅ (kendi) | ❌ |
| `activateNode()` | Node'u aktif et | ✅ | ❌ | ❌ | ❌ |
| `blacklistNode()` | Blacklist'e al | ✅ | ✅ | ❌ | ❌ |
| `whitelistNode()` | Blacklist'ten çıkar | ✅ | ❌ | ❌ | ❌ |
| **Erişim Kontrolü** |  |  |  |  |  |
| `approveAccessRequest()` | Erişim onayla | ✅ | ✅ | ❌ | ❌ |
| `denyAccessRequest()` | Erişim reddet | ✅ | ✅ | ❌ | ❌ |
| `revokeAccess()` | Erişimi iptal et | ✅ | ✅ | ❌ | ❌ |
| `requestAccess()` | Erişim iste | ✅ | ✅ | ✅ | ❌ |
| **Toplu İşlemler** |  |  |  |  |  |
| `batchUpdateNodeStatus()` | Toplu status güncelle | ✅ | ✅ | ❌ | ❌ |
| `batchRevokeAccess()` | Toplu erişim iptal | ✅ | ✅ | ❌ | ❌ |
| **Sistem Ayarları** |  |  |  |  |  |
| `updateSystemSettings()` | Sistem parametreleri | ✅ | ❌ | ❌ | ❌ |
| `addAuthorizedCaller()` | Yetkili caller ekle | ✅ | ❌ | ❌ | ❌ |
| `removeAuthorizedCaller()` | Yetkili caller kaldır | ✅ | ❌ | ❌ | ❌ |
| **Acil Durum** |  |  |  |  |  |
| `emergencyPause()` | Sistemi durdur | ✅ | ❌ | ❌ | ❌ |
| `unpause()` | Sistemi devam ettir | ✅ | ❌ | ❌ | ❌ |
| **Sorgulama** |  |  |  |  |  |
| `getNode()` | Node bilgisi | ✅ | ✅ | ✅ | ✅ |
| `checkAccess()` | Erişim kontrolü | ✅ | ✅ | ✅ | ✅ |
| `getAuditLogs()` | Audit log görüntüleme | ✅ | ✅ | ✅ | ✅ |

### **Açıklamalar:**

- ✅ **Tam Yetki:** Fonksiyonu çağırabilir
- ❌ **Yetki Yok:** Fonksiyonu çağıramaz
- ⚠️ **Sınırlı Yetki:** Belirli koşullarda çağırabilir

---

## 🎯 **3. ROL DETAYLARI**

### **👑 SUPER_ADMIN_ROLE**

**Yetki Seviyesi:** En Yüksek (God Mode)

**Yetkiler:**
- ✅ Tüm rolleri yönetebilir (create, grant, revoke)
- ✅ Tüm node işlemlerini yapabilir
- ✅ Sistem parametrelerini değiştirebilir
- ✅ Acil durum müdahalesi (pause/unpause)
- ✅ Yetkili caller'ları yönetebilir
- ✅ Blacklist'ten çıkarabilir (whitelist)
- ✅ Node'ları aktif edebilir

**Kullanım Alanı:**
- Sistem deployer
- Fabrika/Şirket sahibi
- Son karar mercii

**Güvenlik:**
- Multi-sig wallet önerilir
- Cold storage'da saklanmalı
- Sadece kritik durumlarda kullanılmalı

**Örnek:**
```javascript
// Deployer otomatik olarak SUPER_ADMIN olur
constructor(address _initialAdmin) {
    _grantRole(SUPER_ADMIN_ROLE, _initialAdmin);
    _grantRole(SYSTEM_ADMIN_ROLE, _initialAdmin);
}
```

---

### **🛠️ SYSTEM_ADMIN_ROLE**

**Yetki Seviyesi:** Yüksek (Operasyonel Yönetim)

**Yetkiler:**
- ✅ Node kayıt/güncelleme/silme
- ✅ Erişim isteklerini onaylama/reddetme
- ✅ Node'ları blacklist'e alma
- ✅ Toplu işlemler (batch operations)
- ❌ Rol yönetimi yapamaz
- ❌ Sistem ayarlarını değiştiremez
- ❌ Acil durdurma yapamaz

**Kullanım Alanı:**
- Sistem yöneticisi (IT Manager, Operations Manager)
- Günlük node yönetimi
- Erişim kontrolü
- Güvenlik izleme

**Nasıl Atanır:**
1. **Manuel:** `grantRole(SYSTEM_ADMIN_ROLE, address)`
2. **Otomatik:** `registerNode(..., NodeType.MANAGER, ...)` (MANAGER node kaydı)

**Örnek:**
```javascript
// Yöntem 1: Manuel atama (SUPER_ADMIN tarafından)
await accessRegistry.grantRole(SYSTEM_ADMIN_ROLE, managerAddress);

// Yöntem 2: MANAGER node oluşturma (otomatik rol ataması)
await accessRegistry.registerNode(
    "Manager-Node",
    managerAddress,
    NodeType.MANAGER, // 3
    AccessLevel.ADMIN_ACCESS,
    0,
    "{}"
);
// ✅ managerAddress → SYSTEM_ADMIN_ROLE otomatik atandı!
```

---

### **📋 NODE_MANAGER_ROLE**

**Yetki Seviyesi:** Orta (Kendi Node'ları)

**Yetkiler:**
- ✅ Kendi node'larını güncelleyebilir
- ✅ Kendi node'larını silebilir
- ✅ Erişim istekleri oluşturabilir
- ❌ Başka node'ları yönetemez
- ❌ Erişim onayı veremez

**Kullanım Alanı:**
- Node sahibi kullanıcılar
- Self-service yönetim
- Metadata güncelleme

**Notlar:**
- Şu anda sistemde çok kullanılmıyor
- Gelecekte self-service portal için kullanılabilir
- Çoğu işlem node owner kontrolü ile yapılıyor

---

### **👁️ AUDITOR_ROLE**

**Yetki Seviyesi:** Düşük (Sadece Okuma)

**Yetkiler:**
- ✅ Tüm audit logları görüntüleme
- ✅ Node bilgilerini sorgulama
- ✅ Sistem istatistikleri görüntüleme
- ❌ Hiçbir değişiklik yapamaz
- ❌ Node kaydedemez
- ❌ Erişim onayı veremez

**Kullanım Alanı:**
- Güvenlik denetçileri
- Compliance görevlileri
- Harici denetim firmaları
- Raporlama ve analiz

**Örnek:**
```javascript
await accessRegistry.grantRole(AUDITOR_ROLE, auditorAddress);

// Auditor sadece sorgulama yapabilir
const logs = await accessRegistry.getAuditLogs();
const nodeInfo = await accessRegistry.getNode(nodeId);
```

---

## 🔄 **4. ROL HİYERARŞİSİ**

```
┌─────────────────────────────────────────┐
│  👑 SUPER_ADMIN_ROLE                   │  ← Sistem Sahibi
│  - Tüm yetkiler                        │
│  - Rol yönetimi                        │
│  - Acil durum                          │
└─────────────────────────────────────────┘
           │
           ├─ grant/revoke
           ▼
┌─────────────────────────────────────────┐
│  🛠️ SYSTEM_ADMIN_ROLE                  │  ← Sistem Yöneticisi
│  - Node yönetimi                       │
│  - Erişim kontrolü                     │
│  - Günlük operasyonlar                 │
└─────────────────────────────────────────┘
           │
           ├─ (parallel roles)
           ▼
┌─────────────────────────────────────────┐
│  📋 NODE_MANAGER_ROLE                   │  ← Node Sahibi
│  - Kendi node'ları                     │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  👁️ AUDITOR_ROLE                        │  ← Denetçi
│  - Sadece okuma                        │
└─────────────────────────────────────────┘
```

---

## 📊 **5. KAYNAK ERİŞİM MATRİSİ**

### **Tablo 3: Node Type → Resource Access**

| **Kaynak** | **DATA_PROCESSOR** | **FAILURE_ANALYZER** | **MANAGER** |
|------------|-------------------|---------------------|------------|
| `SENSOR_DATA` | ✅ Write | ✅ Read | ✅ Read/Write |
| `PREDICTION` | ❌ | ✅ Write | ✅ Read/Write |
| `MAINTENANCE` | ❌ | ❌ | ✅ Read/Write |
| `CONFIG` | ❌ | ❌ | ✅ Read/Write |
| `AUDIT_LOGS` | ❌ | ❌ | ✅ Read |

### **Kaynak Açıklamaları:**

- **SENSOR_DATA:** Sensör verisi ZK proof'ları
- **PREDICTION:** Arıza tahmin ZK proof'ları
- **MAINTENANCE:** Bakım kayıtları (gelecek özellik)
- **CONFIG:** Sistem konfigürasyon ayarları
- **AUDIT_LOGS:** Denetim kayıtları (tüm işlemler)

---

## 🎯 **6. GERÇEK DÜNYA SENARYOSU**

### **Senaryo: Fabrika PDM Sistemi Kurulumu**

```
🏭 Fabrika (PDM Sistemi)
│
├─ 👑 Fabrika Sahibi (SUPER_ADMIN)
│   └─ Deployment sırasında otomatik atandı
│   └─ Cold wallet'ta saklanıyor
│
├─ 👨‍💼 IT Manager (SYSTEM_ADMIN + MANAGER Node)
│   ├─ registerNode("IT-Manager", itManagerAddr, MANAGER, ...)
│   └─ Otomatik olarak SYSTEM_ADMIN_ROLE aldı ✅
│
├─ 👨‍💼 Production Manager (SYSTEM_ADMIN + MANAGER Node)
│   ├─ registerNode("Prod-Manager", prodManagerAddr, MANAGER, ...)
│   └─ Otomatik olarak SYSTEM_ADMIN_ROLE aldı ✅
│
├─ 👷 Operator-1 (DATA_PROCESSOR Node)
│   ├─ IT Manager tarafından kaydedildi
│   └─ Sadece SENSOR_DATA erişimi var
│   └─ submitSensorDataProof() yapabilir
│
├─ 👷 Operator-2 (DATA_PROCESSOR Node)
│   ├─ Production Manager tarafından kaydedildi
│   └─ Sadece SENSOR_DATA erişimi var
│
├─ 👨‍🔧 Engineer-1 (FAILURE_ANALYZER Node)
│   ├─ IT Manager tarafından kaydedildi
│   └─ PREDICTION + SENSOR_DATA (read) erişimi var
│   └─ submitPredictionProof() yapabilir
│
└─ 👁️ External Auditor (AUDITOR_ROLE)
    ├─ Fabrika sahibi tarafından atandı
    └─ Sadece audit log ve node bilgilerini görebilir
```

---

## 📋 **7. ROL ATAMA ÖRNEKLERİ**

### **A) Manuel Rol Atama (SUPER_ADMIN tarafından)**

```javascript
// SYSTEM_ADMIN atama
await accessRegistry.grantRole(
    ethers.utils.id("SYSTEM_ADMIN_ROLE"),
    managerAddress
);

// AUDITOR atama
await accessRegistry.grantRole(
    ethers.utils.id("AUDITOR_ROLE"),
    auditorAddress
);
```

### **B) Otomatik Rol Atama (MANAGER Node ile)**

```javascript
// MANAGER node oluştur → Otomatik SYSTEM_ADMIN!
await accessRegistry.registerNode(
    "IT-Manager-Node",
    managerAddress,
    3, // NodeType.MANAGER
    4, // AccessLevel.ADMIN_ACCESS
    0,
    "{}"
);

// ✅ managerAddress artık SYSTEM_ADMIN yetkilerine sahip!
// ✅ Tüm kaynaklara (SENSOR_DATA, PREDICTION, CONFIG, AUDIT_LOGS) erişim var!
```

### **C) Rol İptali**

```javascript
// Sadece SUPER_ADMIN yapabilir
await accessRegistry.revokeRole(
    ethers.utils.id("SYSTEM_ADMIN_ROLE"),
    managerAddress
);
```

---

## 🔐 **8. GÜVENLİK ÖNERİLERİ**

### **SUPER_ADMIN için:**
```
✅ Multi-signature wallet kullan (Gnosis Safe)
✅ Hardware wallet (Ledger/Trezor)
✅ Cold storage'da sakla
✅ Sadece kritik işlemler için kullan
✅ Time-lock mechanism ekle (öneri)
✅ Backup private key'i güvenli yerde sakla
```

### **SYSTEM_ADMIN için:**
```
✅ Birden fazla admin ata (yedeklilik)
✅ Regular security audit yap
✅ Şüpheli aktiviteleri SUPER_ADMIN'e bildir
✅ Audit log'ları düzenli kontrol et
✅ Minimum yetki prensibi uygula
```

### **Node Owner için:**
```
✅ Private key'i güvenli sakla
✅ Node metadata'sını güncel tut
✅ Erişim izinlerini düzenli kontrol et
✅ Şüpheli aktivitelerde yöneticiye bildir
```

---

## 📊 **ÖZET TABLO**

| **Kategori** | **SUPER_ADMIN** | **SYSTEM_ADMIN** | **NODE_MANAGER** | **AUDITOR** |
|--------------|-----------------|------------------|------------------|-------------|
| **Sayı (Önerilen)** | 1-2 | 3-5 | Sınırsız | 1-3 |
| **Atama Yöntemi** | Deployment | Manual/Auto | - | Manual |
| **Kullanım Sıklığı** | Nadir | Sık | Orta | Sürekli |
| **Risk Seviyesi** | Çok Yüksek | Yüksek | Düşük | Çok Düşük |
| **Örnek** | CEO, CTO | IT Manager, Ops Manager | Node Owners | Auditor Firma |

---

**Bu dokümantasyon PDM sisteminin tüm rol ve yetki yapısını kapsar.** 🚀

