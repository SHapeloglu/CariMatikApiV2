# 📊 Muhasebe API v2

> 🗄️ **ARŞİV (2026-10-07):** Bu repo artık geliştirilmiyor. Kod (`api.py` + `auth.py`) ve bu belge **[CariMatik](https://github.com/SHapeloglu/CariMatik)** reposuna taşındı (kökte `api.py`/`auth.py`, belge `API.md`); açık görevler CariMatik `task.md`'de.

Flask tabanlı muhasebe uygulamasının tüm tablolarını dışarıya açan **FastAPI** REST katmanı.
Mevcut Flask uygulamasına (`app.py`) hiç dokunmadan, aynı MySQL veritabanı üzerinde çalışır.

---

## 🗂️ Proje Yapısı

```
muhasebe/
├── app.py       # Mevcut Flask uygulaması (değiştirilmedi)
├── api.py       # ← FastAPI katmanı — tüm modeller, şemalar ve endpoint'ler
├── auth.py      # ← JWT kimlik doğrulama — DB tabanlı secret yönetimi
├── config.py    # Veritabanı bağlantı ayarları (Flask ile paylaşılır)
└── requirements.txt
```

---

## ⚙️ Kurulum

```bash
pip install fastapi uvicorn sqlalchemy pymysql cryptography pydantic \
            python-jose[cryptography] passlib[bcrypt]
```

| Komut | Açıklama |
|-------|----------|
| `uvicorn api:app --reload --port 8000` | Geliştirme modu |
| `uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4` | Üretim modu |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |
| `http://localhost:8000/health` | Sağlık kontrolü |

---

## 🔐 Kimlik Doğrulama

### Neden DB Tabanlı Secret?

`SECRET_KEY` kodda sabit değildir. Her API kaynağı (web arayüzü, mobil, entegrasyon) `api_yetki` tablosundan kendi `secret_key`'ini alır. Avantajlar:

- Bir kaynak sızdırılsa diğerleri güvende kalır
- Anlık iptal: `aktif=False` → tüm token'lar geçersiz
- Kaynak bazlı token süresi, rol kısıtı ve IP kısıtı
- Son kullanım takibi ile denetim

### Login Akışı

```
POST /login
  Header: X-API-Key: <api_key>      ← api_yetki tablosundan alınan anahtar
  Body:   username=email&password=sifre

Adım 1: api_key → api_yetki tablosunda doğrula
Adım 2: IP kısıtı kontrol et
Adım 3: email + şifre → kullanici tablosunda doğrula
Adım 4: Kullanıcı rolü kaynağın izin listesinde mi?
Adım 5: JWT token üret (kaynağın secret_key'i ile imzala)

Yanıt: { "access_token": "eyJ...", "token_type": "bearer", ... }

Sonraki istekler: Authorization: Bearer <token>
```

### İlk Kurulum

**1. API kaynağı oluştur:**
```bash
curl -X POST http://localhost:8000/api/v2/api-yetkiler \
  -H "Content-Type: application/json" \
  -d '{
    "ad": "Web Arayüzü",
    "token_sure": 8,
    "izin_verilen_roller": "ADMIN,STANDART,SADECE_OKUMA"
  }'
# Yanıttaki api_key değerini kaydedin!
```

**2. İlk kullanıcı şifresini hashle:**
```python
from auth import sifreyi_hashle
print(sifreyi_hashle("guclu_sifre_123!"))
# Çıktıyı kullanici.sifre_hash alanına kaydedin
```

**3. Login:**
```bash
curl -X POST http://localhost:8000/login \
  -H "X-API-Key: buraya_api_key" \
  -d "username=admin@firma.com&password=sifre"
```

**4. Korumalı endpoint:**
```bash
curl http://localhost:8000/api/v2/cariler \
  -H "Authorization: Bearer buraya_token"
```

### Swagger'dan Test

`/docs` sayfasında **Authorize** butonuna basın → `X-API-Key`, `username`, `password` girin.

---

## 🔑 API Yetki Yönetimi `/api/v2/api-yetkiler`

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/api/v2/api-yetkiler` | Kaynakları listele (secret_key gizli) |
| GET | `/api/v2/api-yetkiler/{id}` | Tekil kaynak |
| POST | `/api/v2/api-yetkiler` | Yeni kaynak oluştur (key'ler otomatik üretilir) |
| PUT | `/api/v2/api-yetkiler/{id}` | Güncelle |
| POST | `/api/v2/api-yetkiler/{id}/rotate` | api_key + secret_key yenile |
| DELETE | `/api/v2/api-yetkiler/{id}` | Pasife al |

> ⚠️ **rotate** sonrası eski key ile alınan tüm token'lar geçersiz olur.

---

## 📡 API Versiyonları

| Versiyon | Prefix | Durum |
|----------|--------|-------|
| v1 | `/api/v1/` | Destekleniyor (geriye dönük uyumlu) |
| v2 | `/api/v2/` | Güncel — yeni özellikler burada |

---

## 🆕 v2 Endpoint'leri

### 🏢 Şirket — `/api/v2/sirketler`
`GET` `GET/{id}` `POST` `PUT/{id}` `DELETE/{id}` | Filtre: `?aktif=true`

### 🏭 Depo — `/api/v2/depolar`
`GET` `GET/{id}` `POST` `PUT/{id}` `DELETE/{id}` | Filtre: `?sirket_id=1&aktif=true`

### 🔢 Numara Sıra — `/api/v2/numara-siralar`
`GET` `POST` + `GET /sonraki` → otomatik belge no üretimi
> ⚠️ `/sonraki` her çağrıda sayacı kalıcı artırır — belge kaydederken çağırın.

### 💱 Döviz — `/api/v2/dovizler`
`GET` `GET/{id}` `POST` `PUT/{id}`

### 🏦 Banka — `/api/v2/banka-hesaplari` & `/api/v2/banka-hareketler`
`GET` `GET/{id}` `GET/{id}/bakiye` `POST` `PUT/{id}` `DELETE/{id}`
Hareketler: `GET` `GET/{id}` `POST` `DELETE/{id}` | Filtre: `?hesap_id=1&yon=GIRIS`

### 💰 Kasa — `/api/v2/kasa-hesaplari` & `/api/v2/kasa-hareketler`
`GET` `GET/{id}` `GET/{id}/bakiye` `POST` `PUT/{id}` `DELETE/{id}`
Hareketler: `GET` `POST` `DELETE/{id}` | Filtre: `?hesap_id=1&yon=CIKIS`

### 📋 Cari Fiş — `/api/v2/cari-fisler`
`GET` `GET/{id}` `POST` `DELETE/{id}` | Fiş + satırlar tek istekte oluşturulur

### 📜 Çek/Senet — `/api/v2/cek-senetler`
`GET` `GET/{id}` `POST` `PUT/{id}` `DELETE/{id}`
Filtre: `?tip=CEK&yon=ALACAK&durum=PORTFOY`
Durum: `PORTFOY` → `TAHSILDE` → `TAHSIL_EDILDI` | `CIRO_EDILDI` | `PROTESTO` | `IPTAL`

### 📅 Taksit — `/api/v2/taksitler`
`GET` `POST` `PUT/{id}/odendi` `DELETE/{id}` | Filtre: `?belge_id=5&odendi=false`

### 📂 Hesap Grubu — `/api/v2/hesap-gruplari`
`GET` `GET/{id}` `POST` `PUT/{id}` `DELETE/{id}`
Filtre: `?tip=CARI|STOK&seviye=1&parent_id=5`

### 📊 Rapor — `/api/v2/raporlar`
`GET` `GET/{id}` `POST` `DELETE/{id}` + `GET/{id}/calistir`
> ⚠️ Yalnızca `SELECT` sorguları çalışır. `DROP/DELETE/UPDATE` reddedilir.

### 🗺️ Adres (Cascade Select) — `/api/v2/adres`
`GET /ulkeler` → `GET /iller?ulke_id=1` → `GET /ilceler?il_id=34` → `GET /mahalleler?ilce_id=12`

### 📮 Cari Adres — `/api/v2/cari-adresler`
`GET` `POST` `PUT/{id}` `DELETE/{id}` | Filtre: `?cari_id=1`
Tip: `MERKEZ` | `SUBE` | `FATURA` | `SEVKIYAT` | `DIGER`

### 📞 Cari İletişim — `/api/v2/cari-iletisimler`
`GET` `POST` `DELETE/{id}` | Tip: `TELEFON` | `CEP` | `FAX` | `EMAIL` | `WEB` | `DIGER`

### 🏦 Cari Banka — `/api/v2/cari-banka-hesaplari`
`GET` `POST` `DELETE/{id}` | Filtre: `?cari_id=1`

### 👤 Kullanıcı — `/api/v2/kullanicilar`
`GET` `GET/{id}` `DELETE/{id}` `GET/{id}/yetkiler`

### 📈 Dashboard — `/api/v2/ozet`
```json
GET /api/v2/ozet?sirket_id=1
→ { "acik_fatura": 7, "banka_net_bakiye": 125000.0, "vadesi_gelen_cek": 2, ... }
```

---

## 📋 v1 Endpoint'leri

| Grup | Prefix |
|------|--------|
| Birim Grubu | `/api/v1/birim-gruplari` |
| Birim | `/api/v1/birimler` |
| Birim Dönüşüm | `/api/v1/birim-donusumleri` |
| Birim Çevirme | `/api/v1/birim-cevirme?kaynak_id=1&hedef_id=2&miktar=5` |
| Cari | `/api/v1/cariler` |
| Cari Hareket | `/api/v1/cari-hareketler` |
| Stok | `/api/v1/stoklar` |
| Stok Hareket | `/api/v1/stok-hareketler` |
| Belge | `/api/v1/belgeler` |
| Belge Satır | `/api/v1/belge-satirlari` |
| Özet | `/api/v1/ozet` |

---

## 📝 Örnek İstekler

### Banka hareketi
```bash
curl -X POST http://localhost:8000/api/v2/banka-hareketler \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"banka_hesap_id":1,"tarih":"2025-05-01","fis_tipi":"TAHSILAT","yon":"GIRIS","tutar":15000}'
```

### Fatura oluştur
```bash
curl -X POST http://localhost:8000/api/v1/belgeler \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "belge_tip":"FATURA","belge_no":"FAT2500001","tarih":"2025-05-01",
    "cari_id":1,"cari_tip":"SATIS","durum":"ACIK",
    "satirlar":[{"sira_no":1,"stok_id":1,"miktar":10,"birim_fiyat":100,
                 "kdv_orani":20,"kdvsiz_tutar":1000,"kdv_tutar":200,"kdvli_tutar":1200}]
  }'
```

---

## 🔒 Üretim Güvenlik Kontrol Listesi

- [ ] `allow_origins=["*"]` → `allow_origins=["https://sizin-domain.com"]`
- [ ] Tüm yönetim endpoint'lerine `Depends(admin_gerekli)` ekle
- [ ] Sunucu entegrasyonları için `api_yetki.ip_listesi` doldur
- [ ] `config.py` dosyasını `.gitignore`'a ekle
- [ ] Üretimde `--reload` kullanma
- [ ] HTTPS zorunlu kıl (Nginx/Caddy ile SSL)
- [ ] Periyodik api_key rotasyonu (90 günde bir önerilir)

---

## 🛠️ Teknolojiler

| Katman | Teknoloji |
|--------|-----------|
| API Framework | FastAPI |
| ASGI Sunucu | Uvicorn |
| ORM | SQLAlchemy |
| Şema Doğrulama | Pydantic v2 |
| JWT | python-jose |
| Şifre Hash | passlib bcrypt |
| Veritabanı | MySQL 8.0+ |
| MySQL Sürücü | PyMySQL |
| Web Arayüzü | Flask (değiştirilmedi) |

---

## 📄 Lisans

MIT
