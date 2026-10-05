# backlog.md — CariMatik API v2 Fikir Havuzu

- Modelleri CariMatik ile paylaşılan bir pakete çıkar (şema kaymasını bitirmek için) ya da `automap`/reflection kullan.
- Sayfalama standardı (`limit`/`offset` + toplam sayı başlığı) tüm liste uçlarında.
- Belge dönüşümü (sipariş → irsaliye → fatura) için iş mantığı uçları — şu an sadece CRUD; stok/cari hareketi üretmiyor.
- Rate limit (slowapi) ve istek logu.
- Mobil uygulama için OpenAPI'den istemci üretimi.
- Docker imajı + systemd/nginx örneği.

## Ekleme Şablonu

```markdown
### Başlık
- **Kategori:** yeni özellik / iyileştirme / teknik borç / araştırma
- **Neden:** kısa gerekçe
- **Notlar:** büyüklük, bağımlılıklar, riskler
```
