# session.md — CariMatik API v2 Oturum Günlüğü

---

## 2026-10-05

**Yapılanlar:**
- Şablondan üretilmiş çalışma dosyaları kod okunarak yeniden yazıldı.

**Tespitler:**
- `auth.py` api.py'ye bağlı değil → tüm uçlar korumasız (ApiYetki yönetimi dahil).
- bcrypt (passlib) ↔ werkzeug hash uyumsuzluğu.
- Dosyalar CariMatik kökündeki `api.py`/`auth.py` ile birebir aynı.

**Sıradaki adım:** `task.md` → "Sıradaki".

---

## 2026-05-06

- V2 tek commit ile yüklendi (JWT tasarımı + ApiYetki). Ayrıntılı kayıt yok.

---

### Kayıt Şablonu

```markdown
## YYYY-AA-GG
**Yapılanlar:** ...
**Kararlar / neden:** ...
**Açık sorunlar:** ...
**Sıradaki adım:** ...
```
