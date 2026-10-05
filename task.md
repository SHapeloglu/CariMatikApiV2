# task.md — CariMatik API v2 Görevleri

## 🔜 Sıradaki

- [ ] `auth.py`'yi bağla: `get_db` + modelleri ayrı modüle taşı (döngüsel importu kır), `POST /login` ekle, tüm `/api/v2/*` uçlarına rol bağımlılığı ekle
  - Kabul: token'sız istek 401; `SADECE_OKUMA` token'ıyla POST/PUT/DELETE 403; `api-yetkiler` uçları sadece ADMIN.
- [ ] Şifre doğrulamayı CariMatik ile uyumlu yap (`werkzeug.security.check_password_hash`)
- [ ] Rotate / listeleme yanıtlarından `secret_key`'i çıkar
- [ ] `requirements.txt` ve `.gitignore` (`config.py`) ekle
- [ ] CariMatik'teki kopyalarla (kök `api.py`/`auth.py`, `api/` klasörü) tek kaynak belirle

## 🚧 Devam Eden

_(şu anda boş)_

## ✅ Tamamlanan

- [x] 2026-10-05 — Çalışma dosyaları kod okunarak yeniden yazıldı
- [x] 2026-05-06 — V2 (api.py + auth.py + README) yüklendi
