# architect.md — CariMatik API v2 Mimarisi

```
İstemci (web/mobil/entegrasyon)
   │ 1) POST /login  X-API-Key + email/şifre   (tasarlandı, henüz bağlı değil)
   │ 2) Authorization: Bearer <JWT>
   ▼
FastAPI api.py ──► auth.py (JWT doğrulama, rol kontrolü)
   │
   └─SQLAlchemy──► CariMatik MySQL (Flask uygulamasıyla ortak şema + api_yetki tablosu)
```

## Dosyalar

| Dosya | İçerik |
|---|---|
| `api.py` (~2.400 satır) | Engine/`get_db`, CariMatik tablolarının modelleri, Pydantic şemaları, `/api/v2/*` CRUD (~58 GET, 26 POST, 15 PUT, 23 DELETE), `/api/v2/ozet`, `/health`, `ApiYetki` modeli ve yönetim uçları (`/api/v2/api-yetkiler`, rotate, soft delete) |
| `auth.py` (~565 satır) | `pwd_context` (bcrypt), `api_yetki_getir`, `ip_kontrol`, `token_olustur` / `token_coz` (HS256, kaynak başına `secret_key`), `aktif_kullanici`, `admin_gerekli` / `yazma_gerekli` / `okuma_gerekli`, `login_isle` |

## Kimlik Doğrulama Tasarımı (auth.py)

- Her istemci türü bir **ApiYetki** kaydıdır: `api_key` (istemci tanımlayıcısı), `secret_key` (JWT imzası, DB dışına çıkmaz), token süresi (ör. web 8 saat, mobil 24 saat), izinli roller, IP kısıtı, `son_kullanim`.
- Kaynağı pasife almak (`aktif=False`) o kaynağın tüm token'larını anında geçersiz kılar; rotate yeni anahtar üretir.
- Roller CariMatik ile aynı: `ADMIN`, `STANDART`, `SADECE_OKUMA`.

## Mimari Kararlar

- **Tek global SECRET_KEY yerine kaynak başına secret** — bir istemcinin sızması diğerlerini etkilemesin, anında iptal edilebilsin.
- **Soft delete** — denetim izi kalsın.
- **Ayrı süreç, ortak DB** — Flask uygulamasına dokunmadan.
