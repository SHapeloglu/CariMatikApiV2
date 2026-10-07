# CLAUDE.md — CariMatik API v2 (FastAPI + JWT)

> 🗄️ **ARŞİV (2026-10-07):** Bu repo artık geliştirilmiyor. Kod (`api.py` + `auth.py`) ve bu belge **[CariMatik](https://github.com/SHapeloglu/CariMatik)** reposuna taşındı (kökte `api.py`/`auth.py`, belge `API.md`); açık görevler CariMatik `task.md`'de.

CariMatik (FinansApp) MySQL şemasını REST olarak açan FastAPI katmanı. V1'in tüm CRUD endpoint'lerine ek olarak **API kaynağı (ApiYetki) yönetimi** ve **kaynak başına secret ile JWT** tasarımı (`auth.py`) içerir.

- GitHub: https://github.com/SHapeloglu/CariMatikApiV2 (tek yükleme, 2026-05-06)
- Bu dosyaların birebir kopyası **CariMatik** reposunun kökünde (`api.py`, `auth.py`) duruyor; `CariMatik/api/` altındaki sürüm farklı.
- Mimari: `architect.md` · Görevler: `task.md` · Fikirler: `backlog.md` · Günlük: `session.md`

## Çalıştırma

```bash
pip install fastapi uvicorn sqlalchemy pymysql cryptography pydantic "python-jose[cryptography]" "passlib[bcrypt]"
# CariMatik config.py'yi buraya kopyala (yoksa DATABASE_URL ortam değişkeni)
uvicorn api:app --reload --port 8000    # /docs, /redoc, /health
```

## Durum — dikkat

- **`auth.py` henüz `api.py`'ye bağlanmamış.** `auth.py` `from api import get_db, Kullanici, ApiYetki` yapıyor ama `api.py` auth'u import etmiyor; `Depends(admin_gerekli)` satırları yorumda, login endpoint'i yok (sadece `TokenYanit` şeması var). Şu an **tüm endpoint'ler korumasız**, `ApiYetki` yönetim uçları dahil (`api_key`/`secret_key` döndürüyor).
- **Şifre hash uyumsuzluğu:** `auth.py` passlib **bcrypt** ile doğruluyor; CariMatik Flask uygulaması kullanıcıları werkzeug `generate_password_hash` (pbkdf2/scrypt) ile kaydediyor. Entegrasyon yapılınca web'den açılmış kullanıcılar API'ye giriş yapamaz — `werkzeug.security.check_password_hash` kullanılmalı.
- Döngüsel import riski: `auth` → `api` ve ileride `api` → `auth`. Ortak modelleri/`get_db`'yi ayrı modüle (`db.py`) almak gerekir.

## Kurallar

- Modeller CariMatik `app.py` tablolarının elle kopyası; şema değişince ikisini birlikte güncelle.
- `secret_key` asla yanıtta/logda dönmemeli (rotate uç noktası şu an tüm nesneyi dönüyor — kontrol et).
- CORS `*` — üretimde kısıtla.
- Oturum sonunda `session.md`'ye kayıt düş, `task.md`'yi güncelle.
