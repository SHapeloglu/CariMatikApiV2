"""
╔══════════════════════════════════════════════════════════════╗
║              Muhasebe API  v2.0                              ║
║  Flask muhasebe uygulamasının FastAPI REST katmanı           ║
╠══════════════════════════════════════════════════════════════╣
║  Kurulum  : pip install fastapi uvicorn sqlalchemy           ║
║                         pymysql cryptography pydantic        ║
║  Geliştirme: uvicorn api:app --reload --port 8000            ║
║  Üretim   : uvicorn api:app --host 0.0.0.0 --port 8000      ║
║                             --workers 4                      ║
║  Swagger  : http://localhost:8000/docs                       ║
║  ReDoc    : http://localhost:8000/redoc                      ║
╠══════════════════════════════════════════════════════════════╣
║  v1 tabloları: BirimGrubu, Birim, BirimDonusum               ║
║                Cari, CariHareket, StokKarti, StokHareket     ║
║                BelgeBaslik, BelgeSatir                       ║
║  v2 yeni    : Sirket, Depo, NumaraSira, DovizTuru            ║
║               BankaHesap/Hareket, KasaHesap/Hareket          ║
║               CariHesapFisi, CekSenet, TaksitPlan            ║
║               HesapGrubu, Rapor, Kullanici + yetki tabloları ║
║               Ulke/Il/Ilce/Mahalle, CariAdres                ║
║               CariIletisim, CariBankaHesap                   ║
╚══════════════════════════════════════════════════════════════╝
"""

# ── Standart kütüphane ───────────────────────────────────────
from __future__ import annotations        # Python 3.9 öncesi tip ipucu uyumu
from datetime import date, datetime       # Tarih (Date) ve tarih+saat (DateTime) tipleri
from decimal import Decimal               # Yüksek hassasiyetli ondalıklı sayı (import edildi)
from typing import Optional, List, Any, Dict  # Tip ipuçları
from enum import Enum as PyEnum  # Python Enum — SQLAlchemy Enum'dan ayırt etmek için alias
import secrets                    # API key ve secret_key üretmek için           # Python Enum (SQLAlchemy Enum'dan ayrımak için alias)

# ── FastAPI çerçevesi ────────────────────────────────────────
from fastapi import FastAPI, Depends, HTTPException, Query  # FastAPI: uygulama | Depends: DI | HTTPException: hata | Query: URL param
# FastAPI       → Ana uygulama sınıfı; tüm endpoint'lerin kayıtlandığı yer
# Depends       → Dependency Injection: get_db() gibi ortak bağımlılıkları enjekte eder
# HTTPException → HTTP hata yanıtı döndürür (404, 422, 500 vb.)
# Query         → URL sorgu parametresi tanımlar (?aktif=true, ?limit=50 gibi)

from fastapi.middleware.cors import CORSMiddleware  # Cross-Origin Resource Sharing: farklı domain'den gelen isteklere izin/ret
# Cross-Origin Resource Sharing: farklı domain/port'tan gelen
# tarayıcı isteklerine izin veren/reddeden politika

# ── Pydantic ─────────────────────────────────────────────────
from pydantic import BaseModel  # JSON şema tanımı, tip doğrulama ve Swagger belgelendirmesi
# JSON istek/yanıt şemalarını tanımlar, tip doğrulaması ve otomatik
# Swagger belgelendirmesi sağlar

# ── SQLAlchemy ORM ───────────────────────────────────────────
from sqlalchemy import (  # SQLAlchemy: motor, sütun tipleri, kısıtlar, fonksiyonlar
    create_engine,    # Veritabanı motorunu (bağlantı havuzunu) oluşturur
    Column,           # Tablo sütunu tanımı
    Integer,          # Tam sayı sütunu (INT)
    String,           # Karakter dizisi sütunu (VARCHAR)
    Boolean,          # Doğru/Yanlış sütunu (TINYINT 0/1)
    Numeric,          # Ondalıklı sayı — para tutarları için hassas tip (DECIMAL)
    Date,             # Yalnızca tarih: yıl-ay-gün (DATE)
    DateTime,         # Tarih + saat: oluşturma/güncelleme zamanları (DATETIME)
    Text,             # Sınırsız uzun metin: açıklama, SQL sorgusu vb. (TEXT)
    SmallInteger,     # Küçük tam sayı (SMALLINT, 0-32767): sıra numaraları için
    ForeignKey,       # Yabancı anahtar kısıtı — tablolar arası ilişki
    Enum,             # Sabit değer listesi (ENUM): BORC/ALACAK, GIRIS/CIKIS vb.
    func,             # SQL toplu fonksiyonları: SUM(), COUNT(), MAX(), MIN()
    Index,            # Veritabanı indeksi — sık sorgulanan sütunlara performans
    UniqueConstraint, # Çok sütunlu benzersizlik kısıtı
)
from sqlalchemy.orm import declarative_base, Session, sessionmaker, relationship  # ORM temeli, oturum, fabrika ve tablo ilişkileri
# declarative_base → ORM model sınıflarının kalıtım aldığı temel; __tablename__ tanımlar
# Session         → Bir veritabanı işlem oturumu; add/commit/rollback işlemleri
# sessionmaker    → Session nesnesi üreten fabrika; tek seferlik yapılandırma
# relationship    → Python nesneleri arası ilişki: backref, cascade, lazy loading


# ════════════════════════════════════════════════════════════
#  VERİTABANI BAĞLANTISI
#  Öncelik sırası:
#    1. config.py (projeyle birlikte gelir, Flask ile paylaşılır)
#    2. DATABASE_URL ortam değişkeni (Docker/prod ortamı)
#    3. Yerel MySQL geliştirme varsayılanı
# ════════════════════════════════════════════════════════════

try:
    import config as cfg  # DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME + havuz ayarları

    # mysql+pymysql sürücüsü: saf Python, derleme gerektirmez
    # charset=utf8mb4: Türkçe karakter + emoji tam desteği
    MYSQL_URI = (  # MySQL bağlantı URI'si
        f"mysql+pymysql://{cfg.DB_USER}:{cfg.DB_PASSWORD}"  # mysql+pymysql sürücüsü + kimlik bilgileri
        f"@{cfg.DB_HOST}:{cfg.DB_PORT}/{cfg.DB_NAME}?charset=utf8mb4"  # Sunucu, port, veritabanı ve charset
    )
    engine_kwargs = dict(  # Bağlantı havuzu yapılandırması
        pool_size=cfg.POOL_SIZE,        # Havuzda sürekli açık tutulan bağlantı sayısı
        max_overflow=cfg.MAX_OVERFLOW,  # Havuz dolunca açılabilecek ekstra bağlantı sayısı
        pool_timeout=cfg.POOL_TIMEOUT,  # Boş bağlantı için max bekleme süresi (saniye)
        pool_recycle=cfg.POOL_RECYCLE,  # Bağlantıyı N saniyede yenile (MySQL 8h limitini önler)
        pool_pre_ping=cfg.POOL_PRE_PING,# Kullanımdan önce bağlantıyı test et (kopuk bağlantı tespiti)
    )
except ImportError:  # config.py bulunamazsa ortam değişkenine düş
    # config.py bulunamazsa ortam değişkenine düş
    import os  # Ortam değişkenlerine erişim (DATABASE_URL)
    MYSQL_URI = os.environ.get(  # DATABASE_URL ortam değişkeninden al
        "DATABASE_URL",  # Ortam değişkeni adı
        # Son seçenek: yerel geliştirme ortamı varsayılanı
        "mysql+pymysql://root:sifrenizi_buraya_yazin@localhost:3306/muhasebe?charset=utf8mb4",  # Son seçenek: yerel geliştirme varsayılanı
    )
    engine_kwargs = {  # Minimal havuz yapılandırması (config.py yoksa)
        "pool_pre_ping": True,   # Kopuk bağlantıyı otomatik tespit et
        "pool_recycle": 1800,    # 30 dakikada bir bağlantıyı yenile
    }

# Veritabanı motoru: bağlantı havuzunu yönetir, uygulama boyunca tek örnek
engine = create_engine(MYSQL_URI, **engine_kwargs)  # Bağlantı havuzunu oluştur — uygulama boyunca tek örnek

# Session fabrikası:
# autocommit=False → her değişiklik commit() çağrılmadan veritabanına yazılmaz
# autoflush=False  → commit öncesi otomatik flush yapılmaz; kontrol bizdedir
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)  # Session fabrikası: autocommit=False, autoflush=False

# Tüm ORM model sınıflarının miras alacağı temel sınıf
Base = declarative_base()  # Tüm ORM model sınıflarının kalıtım alacağı temel sınıf


def get_db():
    """
    FastAPI Dependency Injection fonksiyonu.
    Her HTTP isteği için yeni bir DB oturumu (Session) açar.
    İstek tamamlanınca — başarı veya hata fark etmeksizin —
    finally bloğu oturumu kapatıp bağlantıyı havuza geri verir.

    Kullanım: db: Session = Depends(get_db)
    """
    db = SessionLocal()  # Yeni veritabanı oturumu aç
    try:
        yield db      # İstek süresince endpoint'e bu nesne enjekte edilir
    finally:
        db.close()    # İstek bittikten sonra bağlantıyı havuza geri ver


def d(v) -> Optional[float]:
    """
    SQLAlchemy Decimal tipini JSON serileştirilebilir float'a çevirir.
    Neden gerekli: Python'un json modülü ve Pydantic, Decimal tipini
    doğrudan işleyemez; float dönüşümü zorunludur.
    None güvenli: değer None ise None döner, hata fırlatmaz.
    Kullanım: d(obj.toplam_kdvli)  →  float veya None
    """
    return float(v) if v is not None else None  # None güvenli Decimal→float dönüşümü


# ════════════════════════════════════════════════════════════
#  SQLALCHEMY MODELLERİ
#  Her sınıf → veritabanındaki bir tablo.
#  Flask app.py ile birebir aynı şema; ortak MySQL'i paylaşır.
#  Silme stratejisi: fiziksel silme yerine aktif=False (soft delete).
#  ondelete davranışları:
#    CASCADE    → ebeveyn silinince ilişkili kayıtlar da silinir
#    SET NULL   → ebeveyn silinince FK alanı NULL'a çekilir (veri korunur)
#    RESTRICT   → bağlı kaydı olan ebeveyn silinemez
# ════════════════════════════════════════════════════════════

class Sirket(Base):
    """
    Çok şirketli yapının ana tablosu.
    Her belge, depo, banka/kasa hesabı bir şirkete bağlanır.
    Silme: aktif=False (soft delete) — bağlı veriler korunur.
    """
    __tablename__ = 'sirket'  # MySQL'deki tablo adı
    id               = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    kod              = Column(String(20), unique=True, nullable=False)   # Benzersiz kısa kod (S001)
    unvan            = Column(String(200), nullable=False)               # Resmi ticaret unvanı
    vergi_no         = Column(String(20))                               # VKN veya TC kimlik
    vergi_dairesi    = Column(String(100))  # DB sütunu
    telefon          = Column(String(20))  # DB sütunu
    email            = Column(String(100))  # DB sütunu
    adres            = Column(Text)  # DB sütunu
    logo_url         = Column(String(300))                              # Logo görsel URL'si
    aktif            = Column(Boolean, default=True, nullable=False)    # False = pasif/silindi
    olusturma_tarihi = Column(DateTime, default=datetime.now)           # Kayıt oluşturma zamanı


class Depo(Base):
    """
    Şirkete ait fiziksel depo / ambar lokasyonları.
    Belgeler (özellikle irsaliye) belirli bir depoya atanır.
    Aynı şirkette aynı kod tekrar kullanılamaz (unique constraint).
    CASCADE: şirket silinirse depoları da silinir.
    """
    __tablename__ = 'depo'  # MySQL'deki tablo adı
    id        = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    sirket_id = Column(Integer, ForeignKey('sirket.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    kod       = Column(String(20), nullable=False)     # Şirket içinde benzersiz depo kodu
    ad        = Column(String(100), nullable=False)    # Depo adı (Merkez Depo, B Ambarı...)
    adres     = Column(Text)                           # Fiziksel konum adresi
    aktif     = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (UniqueConstraint('sirket_id', 'kod', name='uq_depo_sirket_kod'),)  # Tablo düzeyinde kısıtlar ve indeksler


class NumaraSira(Base):
    """
    Belge numarası otomatik üretim tablosu.
    Her şirket + belge tipi + yön + yıl kombinasyonu için ayrı sayaç.
    Örnek: prefix='FAT', yil=2025, basamak=5, son_sayi=1 → 'FAT2500001'
    son_sayi her yeni belgede +1 artar; geri alınamaz — belge kaydederken çağırın.
    """
    __tablename__ = 'numara_sira'  # MySQL'deki tablo adı
    id        = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    sirket_id = Column(Integer, ForeignKey('sirket.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    belge_tip = Column(Enum('TALEP', 'SIPARIS', 'IRSALIYE', 'FATURA'), nullable=False)  # DB sütunu
    cari_tip  = Column(Enum('SATIS', 'ALIS'), nullable=False)  # Satış mı alış mı
    prefix    = Column(String(10), nullable=False)       # Numara öneki: FAT, SIP, IRS, TLP...
    yil       = Column(SmallInteger, nullable=False)     # Hangi yıla ait sayaç (2025)
    son_sayi  = Column(Integer, default=0, nullable=False)  # Son üretilen sıra numarası
    basamak   = Column(SmallInteger, default=5)          # Sayacın kaç basamak olacağı (5→00001)
    __table_args__ = (  # Tablo düzeyinde kısıtlar ve indeksler
        # Aynı şirket+tip+yön+yıl için tek seri olabilir
        UniqueConstraint('sirket_id', 'belge_tip', 'cari_tip', 'yil', name='uq_ns_sirket_tip_yil'),  # Benzersizlik kısıtı
    )


class DovizTuru(Base):
    """
    Para birimi referans tablosu.
    ISO 4217 standart kodları kullanılır: TRY, USD, EUR, GBP...
    Banka/kasa hesaplarına ve çek/senet kayıtlarına FK ile bağlanır.
    RESTRICT: kullanımda olan döviz türü silinemez.
    """
    __tablename__ = 'doviz_turu'  # MySQL'deki tablo adı
    id     = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    kod    = Column(String(5), unique=True, nullable=False)  # ISO kodu: TRY, USD, EUR...
    ad     = Column(String(50), nullable=False)              # Tam adı: Türk Lirası, Dolar...
    sembol = Column(String(5))                               # Para sembolü: ₺, $, €, £
    aktif  = Column(Boolean, default=True, nullable=False)  # DB sütunu


class BankaHesap(Base):
    """
    Şirkete ait banka hesapları.
    Bakiye = SUM(GIRIS hareketleri) - SUM(CIKIS hareketleri)
    IBAN: boşluksuz 34 karakter, TR ile başlar.
    ondelete=RESTRICT (doviz_id): kullanılan döviz silinemez.
    """
    __tablename__ = 'banka_hesap'  # MySQL'deki tablo adı
    id         = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    sirket_id  = Column(Integer, ForeignKey('sirket.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    kod        = Column(String(20), nullable=False)       # Şirket içinde benzersiz hesap kodu
    banka_adi  = Column(String(100), nullable=False)      # Banka adı (Ziraat, Garanti...)
    sube_adi   = Column(String(100))                      # Şube adı
    sube_kodu  = Column(String(20))                       # Şube numarası
    hesap_no   = Column(String(50))                       # Hesap numarası
    iban       = Column(String(34))                       # IBAN (boşluksuz, 26 karakter TR)
    doviz_id   = Column(Integer, ForeignKey('doviz_turu.id', ondelete='RESTRICT'))  # Para birimi
    aciklama   = Column(String(200))  # DB sütunu
    aktif      = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (UniqueConstraint('sirket_id', 'kod', name='uq_banka_hesap_kod'),)  # Tablo düzeyinde kısıtlar ve indeksler


class BankaHareket(Base):
    """
    Banka hesabı giriş/çıkış hareketleri.
    fis_tipi örnekleri: TAHSILAT, ODEME, HAVALE_GIRIS, HAVALE_CIKIS, TRANSFER
    karsit_hesap_id → bankadan bankaya havale: karşı banka hesabı
    karsit_kasa_id  → banka↔kasa transferi: karşı kasa hesabı
    SET NULL: ilişkili cari/hesap/kasa silinse de hareket kaydı korunur.
    """
    __tablename__ = 'banka_hareket'  # MySQL'deki tablo adı
    id               = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    banka_hesap_id   = Column(Integer, ForeignKey('banka_hesap.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    tarih            = Column(Date, nullable=False, default=date.today)   # Valör/işlem tarihi
    fisno            = Column(String(30))                  # Fiş / dekont numarası
    fis_tipi         = Column(String(20), nullable=False)  # Hareket tipi (serbest metin)
    yon              = Column(Enum('GIRIS', 'CIKIS'), nullable=False)  # Para yönü
    tutar            = Column(Numeric(15, 2), nullable=False)  # DB sütunu
    aciklama         = Column(String(500))  # DB sütunu
    cari_id          = Column(Integer, ForeignKey('cari.id', ondelete='SET NULL'))           # İlgili cari
    karsit_hesap_id  = Column(Integer, ForeignKey('banka_hesap.id', ondelete='SET NULL'))    # Havale karşı banka
    karsit_kasa_id   = Column(Integer, ForeignKey('kasa_hesap.id', ondelete='SET NULL'))     # Transfer karşı kasa
    olusturma_tarihi = Column(DateTime, default=datetime.now)  # DB sütunu
    __table_args__ = (  # Tablo düzeyinde kısıtlar ve indeksler
        Index('ix_banka_hrkt_hesap_tarih', 'banka_hesap_id', 'tarih'),  # Hesap ekstresi sorgusu
    )


class KasaHesap(Base):
    """
    Nakit kasalar. Her kasa farklı döviz cinsinden tutulabilir.
    Bakiye = SUM(GIRIS) - SUM(CIKIS)
    RESTRICT (doviz_id): kullanılan döviz türü silinemez.
    """
    __tablename__ = 'kasa_hesap'  # MySQL'deki tablo adı
    id        = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    sirket_id = Column(Integer, ForeignKey('sirket.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    kod       = Column(String(20), nullable=False)     # Şirket içinde benzersiz kasa kodu
    ad        = Column(String(100), nullable=False)    # Kasa adı (TL Kasası, USD Kasası...)
    doviz_id  = Column(Integer, ForeignKey('doviz_turu.id', ondelete='RESTRICT'))  # Döviz cinsi
    aciklama  = Column(String(200))  # DB sütunu
    aktif     = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (UniqueConstraint('sirket_id', 'kod', name='uq_kasa_hesap_kod'),)  # Tablo düzeyinde kısıtlar ve indeksler


class KasaHareket(Base):
    """
    Kasa giriş/çıkış hareketleri.
    fis_tipi örnekleri: TAHSILAT, ODEME, TRANSFER, DIGER
    karsit_kasa_id  → kasadan kasaya transfer (karşı kasa)
    karsit_banka_id → kasa↔banka transferi (karşı banka hesabı)
    """
    __tablename__ = 'kasa_hareket'  # MySQL'deki tablo adı
    id              = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    kasa_hesap_id   = Column(Integer, ForeignKey('kasa_hesap.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    tarih           = Column(Date, nullable=False, default=date.today)  # DB sütunu
    fisno           = Column(String(30))  # DB sütunu
    fis_tipi        = Column(String(20), nullable=False)  # DB sütunu
    yon             = Column(Enum('GIRIS', 'CIKIS'), nullable=False)  # DB sütunu
    tutar           = Column(Numeric(15, 2), nullable=False)  # DB sütunu
    aciklama        = Column(String(500))  # DB sütunu
    cari_id         = Column(Integer, ForeignKey('cari.id', ondelete='SET NULL'))  # DB sütunu
    karsit_kasa_id  = Column(Integer, ForeignKey('kasa_hesap.id', ondelete='SET NULL'))    # Transfer: karşı kasa
    karsit_banka_id = Column(Integer, ForeignKey('banka_hesap.id', ondelete='SET NULL'))   # Transfer: karşı banka
    olusturma_tarihi= Column(DateTime, default=datetime.now)  # DB sütunu
    __table_args__ = (Index('ix_kasa_hrkt_hesap_tarih', 'kasa_hesap_id', 'tarih'),)  # Tablo düzeyinde kısıtlar ve indeksler


class CariHesapFis(Base):
    """
    Manuel cari borç/alacak fişi.
    Fatura dışında elle girilen hareketler için kullanılır:
    açılış bakiyesi, ay sonu mutabakatı, düzeltme kaydı vb.
    cascade='all, delete-orphan' → fiş silinince satırları da silinir.
    """
    __tablename__ = 'cari_hesap_fis'  # MySQL'deki tablo adı
    id               = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    sirket_id        = Column(Integer, ForeignKey('sirket.id', ondelete='SET NULL'))  # Hangi şirkete ait
    fisno            = Column(String(30), unique=True, nullable=False)                 # Benzersiz fiş no
    tarih            = Column(Date, nullable=False, default=date.today)  # DB sütunu
    aciklama         = Column(String(500))  # DB sütunu
    olusturma_tarihi = Column(DateTime, default=datetime.now)  # DB sütunu
    satirlar         = relationship('CariHesapFisSatir', backref='fis',  # Ters ilişki: ilişkili nesneden bu nesneye erişim
                                    cascade='all, delete-orphan')  # Fiş silinince satırlar da silinir


class CariHesapFisSatir(Base):
    """
    Cari fişin her bir borç/alacak satırı.
    Bir fiş birden fazla cariye ait satır içerebilir.
    BORC   → cari bize borçlanıyor (mal sattık, alacak doğdu)
    ALACAK → biz cariye borçlanıyoruz (ödeme aldık, borç kapandı)
    RESTRICT: kayıtlı hareketi olan cari silinemez.
    """
    __tablename__ = 'cari_hesap_fis_satir'  # MySQL'deki tablo adı
    id           = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    fis_id       = Column(Integer, ForeignKey('cari_hesap_fis.id', ondelete='CASCADE'), nullable=False)  # Ebeveyn silinince ilişkili kayıtlar da silinir
    cari_id      = Column(Integer, ForeignKey('cari.id', ondelete='RESTRICT'), nullable=False)  # DB sütunu
    hareket_tipi = Column(Enum('BORC', 'ALACAK'), nullable=False)  # DB sütunu
    tutar        = Column(Numeric(15, 2), nullable=False)  # DB sütunu
    aciklama     = Column(String(300))  # DB sütunu


class CariBankaHesap(Base):
    """
    Cariye ait banka hesap bilgileri (ödeme IBAN'ı vb.).
    Şirketin kendi hesaplarından farklı; carinin hesap bilgileridir.
    Bir carinin birden fazla hesabı olabilir;
    varsayilan=True → birincil ödeme hesabı.
    """
    __tablename__ = 'cari_banka_hesap'  # MySQL'deki tablo adı
    id          = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    cari_id     = Column(Integer, ForeignKey('cari.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    banka_adi   = Column(String(100), nullable=False)  # DB sütunu
    sube_adi    = Column(String(100))  # DB sütunu
    hesap_no    = Column(String(50))  # DB sütunu
    iban        = Column(String(34))                                               # Carinin IBAN'ı
    doviz_id    = Column(Integer, ForeignKey('doviz_turu.id', ondelete='SET NULL'))  # DB sütunu
    aciklama    = Column(String(200))  # DB sütunu
    varsayilan  = Column(Boolean, default=False, nullable=False)  # True → birincil hesap
    aktif       = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (Index('ix_cari_banka_cari', 'cari_id'),)   # Cariye göre hızlı arama


class CariIletisim(Base):
    """
    Cari firmaya ait çok kanallı iletişim bilgileri.
    tip değerleri: TELEFON, CEP, FAX, EMAIL, WEB, DIGER
    varsayilan=True → o kanalın birincil iletişim noktası.
    Bir carinin farklı tiplerden birden fazla iletişimi olabilir.
    """
    __tablename__ = 'cari_iletisim'  # MySQL'deki tablo adı
    id         = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    cari_id    = Column(Integer, ForeignKey('cari.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    tip        = Column(Enum('TELEFON', 'CEP', 'FAX', 'EMAIL', 'WEB', 'DIGER'), nullable=False)  # DB sütunu
    deger      = Column(String(200), nullable=False)    # Numara, e-posta adresi, web URL'si
    aciklama   = Column(String(100))                    # Ek not (Muhasebe Hattı, Satış vb.)
    varsayilan = Column(Boolean, default=False, nullable=False)  # DB sütunu
    aktif      = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (Index('ix_ci_cari', 'cari_id'),)  # Tablo düzeyinde kısıtlar ve indeksler


class Kullanici(Base):
    """
    Sisteme giriş yapabilen kullanıcılar.
    rol:
      ADMIN        → tam yetki, tüm şirketlere erişim
      STANDART     → yetki tablolarına göre kısıtlı erişim
      SADECE_OKUMA → yalnızca görüntüleme
    sifre_hash: bcrypt ile hashlenmiş şifre (düz metin asla saklanmaz!).
    tema: kullanıcının tercih ettiği UI renk teması.
    """
    __tablename__ = 'kullanici'  # MySQL'deki tablo adı
    id               = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    ad_soyad         = Column(String(100), nullable=False)  # DB sütunu
    email            = Column(String(150), unique=True, nullable=False)   # Giriş için e-posta
    sifre_hash       = Column(String(256), nullable=False)                # bcrypt hash (düz şifre değil!)
    rol              = Column(Enum('ADMIN', 'STANDART', 'SADECE_OKUMA'), nullable=False, default='STANDART')  # DB sütunu
    tema             = Column(String(20), default='dark')                 # UI renk teması
    aktif            = Column(Boolean, default=True, nullable=False)      # False = hesap askıya alındı
    olusturma_tarihi = Column(DateTime, default=datetime.now)  # DB sütunu


class KullaniciSirketYetki(Base):
    """
    Kullanıcı → Şirket erişim yetkisi (STANDART rol için geçerli).
    ADMIN rolündeki kullanıcılar bu tabloya bakmaksızın tüm şirketlere erişir.
    Unique constraint: aynı kullanıcı-şirket çifti iki kez eklenemez.
    CASCADE: kullanıcı veya şirket silinince yetki kaydı da silinir.
    """
    __tablename__ = 'kullanici_sirket_yetki'  # MySQL'deki tablo adı
    id           = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    kullanici_id = Column(Integer, ForeignKey('kullanici.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    sirket_id    = Column(Integer, ForeignKey('sirket.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    __table_args__ = (UniqueConstraint('kullanici_id', 'sirket_id', name='uq_ksy'),)  # Tablo düzeyinde kısıtlar ve indeksler


class KullaniciDepoYetki(Base):
    """
    Kullanıcı → Depo erişim yetkisi.
    Belge oluştururken yalnızca yetkili depolar dropdown'da gösterilir.
    CASCADE: kullanıcı veya depo silinince yetki de silinir.
    """
    __tablename__ = 'kullanici_depo_yetki'  # MySQL'deki tablo adı
    id           = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    kullanici_id = Column(Integer, ForeignKey('kullanici.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    depo_id      = Column(Integer, ForeignKey('depo.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    __table_args__ = (UniqueConstraint('kullanici_id', 'depo_id', name='uq_kdy'),)  # Tablo düzeyinde kısıtlar ve indeksler


class KullaniciBelgeYetki(Base):
    """
    Kullanıcı → Belge tipi erişim yetkisi.
    yazma=True  → okuma + oluşturma/düzenleme yetkisi
    yazma=False → yalnızca görüntüleme yetkisi
    Her kullanıcı için belge_tip + cari_tip kombinasyonu benzersizdir.
    """
    __tablename__ = 'kullanici_belge_yetki'  # MySQL'deki tablo adı
    id           = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    kullanici_id = Column(Integer, ForeignKey('kullanici.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    belge_tip    = Column(Enum('TALEP', 'SIPARIS', 'IRSALIYE', 'FATURA'), nullable=False)  # DB sütunu
    cari_tip     = Column(Enum('SATIS', 'ALIS', 'HER_IKISI'), nullable=False, default='HER_IKISI')  # Zorunlu alan — NULL kabul etmez
    yazma        = Column(Boolean, default=True)   # True=okuma+yazma, False=sadece okuma
    __table_args__ = (UniqueConstraint('kullanici_id', 'belge_tip', 'cari_tip', name='uq_kbty'),)  # Tablo düzeyinde kısıtlar ve indeksler


class CekSenet(Base):
    __tablename__ = 'cek_senet'  # MySQL'deki tablo adı
    id               = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    sirket_id        = Column(Integer, ForeignKey('sirket.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    tip              = Column(Enum('CEK', 'SENET'), nullable=False)  # DB sütunu
    yon              = Column(Enum('ALACAK', 'BORC'), nullable=False)  # DB sütunu
    seri_no          = Column(String(50))  # DB sütunu
    banka            = Column(String(100))  # DB sütunu
    sube             = Column(String(100))  # DB sütunu
    kesideci         = Column(String(200))  # DB sütunu
    cari_id          = Column(Integer, ForeignKey('cari.id', ondelete='SET NULL'))  # DB sütunu
    tutar            = Column(Numeric(15, 2), nullable=False)  # DB sütunu
    doviz_id         = Column(Integer, ForeignKey('doviz_turu.id', ondelete='SET NULL'))  # DB sütunu
    vade_tarihi      = Column(Date, nullable=False)  # DB sütunu
    durum            = Column(Enum('PORTFOY', 'TAHSILDE', 'TAHSIL_EDILDI', 'CIRO_EDILDI', 'PROTESTO', 'IPTAL'),  # DB sütunu
                              nullable=False, default='PORTFOY')  # Zorunlu alan, varsayılan değeri var
    aciklama         = Column(String(300))  # DB sütunu
    olusturma_tarihi = Column(DateTime, default=datetime.now)  # DB sütunu
    __table_args__ = (  # Tablo düzeyinde kısıtlar ve indeksler
        Index('ix_ceksenet_sirket', 'sirket_id'),  # Şirkete göre çek/senet sorgusu
        Index('ix_ceksenet_vade', 'vade_tarihi'),  # Vadesi gelen çek sorgusu
    )


class TaksitPlan(Base):
    __tablename__ = 'taksit_plan'  # MySQL'deki tablo adı
    id           = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    belge_id     = Column(Integer, ForeignKey('belge_baslik.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    taksit_no    = Column(SmallInteger, nullable=False)  # DB sütunu
    vade_tarihi  = Column(Date, nullable=False)  # DB sütunu
    tutar        = Column(Numeric(15, 2), nullable=False)  # DB sütunu
    odendi       = Column(Boolean, default=False)  # DB sütunu
    odeme_tarihi = Column(Date)  # DB sütunu
    aciklama     = Column(String(200))  # DB sütunu
    __table_args__ = (Index('ix_taksit_belge', 'belge_id'),)  # Tablo düzeyinde kısıtlar ve indeksler


class HesapGrubu(Base):
    """
    Cari ve stok kartları için hiyerarşik gruplama sistemi.
    tip=CARI → müşteri/tedarikçi kategorileri (Yurt İçi Alıcılar vb.)
    tip=STOK → ürün kategorileri (Hammadde, Ticari Mal vb.)
    5 seviyeye kadar ağaç yapısı: parent_id self-referential join.
    RESTRICT: alt grubu veya bağlı kaydı olan grup silinemez.
    Kod benzersizliği tip bazlıdır: CARI+100 ve STOK+100 birlikte olabilir.
    """
    __tablename__ = 'hesap_grubu'  # MySQL'deki tablo adı
    id        = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    tip       = Column(Enum('CARI', 'STOK'), nullable=False)              # Hangi modüle ait
    seviye    = Column(SmallInteger, nullable=False, default=1)            # Ağaç derinliği (1=kök)
    parent_id = Column(Integer, ForeignKey('hesap_grubu.id', ondelete='RESTRICT'))  # Üst grup
    kod       = Column(String(20), nullable=False)    # Hesap kodu (100, 100.01, 100.01.A)
    ad        = Column(String(100), nullable=False)  # DB sütunu
    aciklama  = Column(String(200))  # DB sütunu
    aktif     = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (  # Tablo düzeyinde kısıtlar ve indeksler
        UniqueConstraint('tip', 'kod', name='uq_hesapgrubu_tip_kod'),  # Aynı tip içinde kod benzersiz
        Index('ix_hg_tip_seviye', 'tip', 'seviye'),                    # Seviyeye göre listeleme
        Index('ix_hg_parent', 'parent_id'),                            # Alt grup sorgusunu hızlandır
    )


class Rapor(Base):
    """
    Dinamik SQL rapor tanımları.
    sql_sorgu: ham SELECT ifadesi içerir.
    API katmanı güvenlik kontrolü uygular: DROP/DELETE/UPDATE reddedilir.
    Filtreler RaporFiltre tablosunda :parametre_adi biçiminde tanımlanır.
    """
    __tablename__ = 'rapor'  # MySQL'deki tablo adı
    id               = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    ad               = Column(String(100), nullable=False)  # DB sütunu
    aciklama         = Column(Text)  # DB sütunu
    sql_sorgu        = Column(Text, nullable=False)   # SELECT sorgusu (güvenlik kontrolü API'de)
    kategori         = Column(String(50))             # Cari, Stok, Finans, Genel...
    olusturma_tarihi = Column(DateTime, default=datetime.now)  # DB sütunu
    aktif            = Column(Boolean, default=True, nullable=False)  # DB sütunu


class RaporFiltre(Base):
    """
    Rapor parametreleri — SQL'deki :parametre_adi alanlarına karşılık gelir.
    tip=SECIM → secim_deger 'deger1:etiket1,deger2:etiket2' formatında listelenir.
    """
    __tablename__ = 'rapor_filtre'  # MySQL'deki tablo adı
    id           = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    rapor_id     = Column(Integer, ForeignKey('rapor.id', ondelete='CASCADE'), nullable=False)  # Ebeveyn silinince ilişkili kayıtlar da silinir
    sira         = Column(SmallInteger, default=1)          # Formda gösterim sırası
    etiket       = Column(String(50), nullable=False)       # Kullanıcıya gösterilen etiket
    parametre    = Column(String(30), nullable=False)       # SQL parametre adı (:tarih_bas)
    tip          = Column(Enum('TARIH', 'METIN', 'SAYI', 'SECIM'), nullable=False, default='METIN')  # DB sütunu
    secim_deger  = Column(String(500))                      # SECIM tipi için seçenek listesi
    varsayilan   = Column(String(100))                      # Parametrenin varsayılan değeri


class Ulke(Base):
    """
    Adres sistemi — ülke referans tablosu.
    ISO 3166-1 alfa-3 formatı: TR, DEU, USA, GBR...
    Cascade: ülke silinirse bağlı iller de silinir.
    """
    __tablename__ = 'ulke'  # MySQL'deki tablo adı
    id    = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    kod   = Column(String(3), unique=True, nullable=False)  # ISO 3 harfli ülke kodu
    ad    = Column(String(100), nullable=False)  # DB sütunu
    aktif = Column(Boolean, default=True, nullable=False)  # DB sütunu


class Il(Base):
    """
    Adres sistemi — il / eyalet tablosu.
    plaka: Türkiye'ye özgü araç plaka kodu (01-81).
    CASCADE: ülke silinince iller de silinir.
    """
    __tablename__ = 'il'  # MySQL'deki tablo adı
    id      = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    ulke_id = Column(Integer, ForeignKey('ulke.id', ondelete='CASCADE'), nullable=False)  # Ebeveyn silinince ilişkili kayıtlar da silinir
    plaka   = Column(String(5))                   # TR plaka kodu: 35=İzmir, 06=Ankara
    ad      = Column(String(100), nullable=False)  # DB sütunu
    aktif   = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (Index('ix_il_ulke', 'ulke_id'),)  # Ülkeye göre il listesi indeksi


class Ilce(Base):
    """Adres sistemi — ilçe tablosu. Cascade select: il seçiminden sonra gelir."""
    __tablename__ = 'ilce'  # MySQL'deki tablo adı
    id    = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    il_id = Column(Integer, ForeignKey('il.id', ondelete='CASCADE'), nullable=False)  # Ebeveyn silinince ilişkili kayıtlar da silinir
    ad    = Column(String(100), nullable=False)  # DB sütunu
    aktif = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (Index('ix_ilce_il', 'il_id'),)  # Tablo düzeyinde kısıtlar ve indeksler


class Mahalle(Base):
    """
    Adres sistemi — mahalle / köy tablosu.
    posta_kodu bu seviyede tutulur (5 haneli Türkiye posta kodu).
    Cascade select sırası: Ülke → İl → İlçe → Mahalle.
    """
    __tablename__ = 'mahalle'  # MySQL'deki tablo adı
    id         = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    ilce_id    = Column(Integer, ForeignKey('ilce.id', ondelete='CASCADE'), nullable=False)  # Ebeveyn silinince ilişkili kayıtlar da silinir
    ad         = Column(String(100), nullable=False)  # DB sütunu
    posta_kodu = Column(String(10))   # 5 haneli Türkiye posta kodu
    aktif      = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (Index('ix_mahalle_ilce', 'ilce_id'),)  # Tablo düzeyinde kısıtlar ve indeksler


class CariAdres(Base):
    """
    Cari firmaya ait yapılandırılmış adres kayıtları.
    adres_tipi: MERKEZ, SUBE, FATURA, SEVKIYAT, DIGER
    varsayilan=True → o tipteki birincil adres.
    Ülke/İl/İlçe/Mahalle ayrı FK olarak tutulur — cascade dropdown için.
    SET NULL: referans silinse bile adres kaydı korunur (FK NULL olur).
    """
    __tablename__ = 'cari_adres'  # MySQL'deki tablo adı
    id          = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    cari_id     = Column(Integer, ForeignKey('cari.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    adres_tipi  = Column(Enum('MERKEZ', 'SUBE', 'FATURA', 'SEVKIYAT', 'DIGER'),  # DB sütunu
                         nullable=False, default='MERKEZ')  # Zorunlu alan, varsayılan değeri var
    ulke_id     = Column(Integer, ForeignKey('ulke.id', ondelete='SET NULL'))     # Ülke seçimi
    il_id       = Column(Integer, ForeignKey('il.id', ondelete='SET NULL'))       # İl seçimi
    ilce_id     = Column(Integer, ForeignKey('ilce.id', ondelete='SET NULL'))     # İlçe seçimi
    mahalle_id  = Column(Integer, ForeignKey('mahalle.id', ondelete='SET NULL'))  # Mahalle seçimi
    sokak       = Column(String(200))   # Cadde / sokak adı ve numarası
    bina_no     = Column(String(20))    # Kapı / bina numarası
    daire_no    = Column(String(20))    # Daire / ofis numarası
    posta_kodu  = Column(String(10))    # Manuel posta kodu (mahalle seçilmemişse kullanılır)
    aciklama    = Column(String(300))   # Yön tarifi, ek notlar
    varsayilan  = Column(Boolean, default=False, nullable=False)  # Bu tip için birincil adres
    aktif       = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (Index('ix_cari_adres_cari', 'cari_id'),)  # Tablo düzeyinde kısıtlar ve indeksler


class BirimGrubu(Base):
    """
    Ölçü birimi kategorileri: Uzunluk, Ağırlık, Hacim, Adet, Paket...
    Grup içindeki birimler taban birim üzerinden birbirine dönüştürülür.
    lazy='dynamic' → birimler listesi talep üzerine yüklenir (büyük listeler için verimli).
    """
    __tablename__ = 'birim_grubu'  # MySQL'deki tablo adı
    id       = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    ad       = Column(String(50), unique=True, nullable=False)   # Grup adı (benzersiz)
    aciklama = Column(String(200))  # DB sütunu
    aktif    = Column(Boolean, default=True, nullable=False)  # DB sütunu
    birimler = relationship('Birim', backref='grup', lazy='dynamic', foreign_keys='Birim.grup_id')  # Ters ilişki: ilişkili nesneden bu nesneye erişim


class Birim(Base):
    """
    Ölçü birimleri. Her birim bir gruba aittir.
    katsayi: grubun taban birimine göre çevrim oranı.
    Örnek — Uzunluk grubu (taban birim=MT):
      KM  → katsayi=1000  (1 KM = 1000 MT)
      MT  → katsayi=1     (taban birim, katsayi=1)
      CM  → katsayi=0.01  (1 CM = 0.01 MT)
    taban_mi=True → grubun referans birimi; her grupta en az 1 adet olmalı.
    RESTRICT: stok kartlarında kullanılan birim silinemez.
    """
    __tablename__ = 'birim'  # MySQL'deki tablo adı
    id       = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    grup_id  = Column(Integer, ForeignKey('birim_grubu.id', ondelete='RESTRICT'), nullable=False)  # Bağlı kaydı olan ebeveyn silinemez
    kod      = Column(String(20), unique=True, nullable=False)    # Kısa kod: MT, KG, ADET, KUTU
    ad       = Column(String(50), nullable=False)                 # Tam adı: Metre, Kilogram...
    katsayi  = Column(Numeric(20, 10), nullable=False, default=1.0)  # Taban birime çevrim oranı
    taban_mi = Column(Boolean, default=False, nullable=False)     # Grubun referans birimi mi?
    aktif    = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (Index('ix_birim_grup', 'grup_id'),)  # Tablo düzeyinde kısıtlar ve indeksler


class BirimDonusum(Base):
    """
    Farklı gruplar arası veya özel birim dönüşüm kuralları.
    Formül: 1 kaynak_birim = carpan × hedef_birim
    Örnek: 1 KUTU = 12 ADET → kaynak=KUTU, hedef=ADET, carpan=12

    API dönüşüm öncelik sırası (/birim-cevirme endpoint'i):
      1. Aynı birim → katsayi=1 döner
      2. Doğrudan BirimDonusum kaydı var → carpan kullan
      3. Ters yön kaydı var → 1/carpan kullan
      4. Aynı gruptaysa → katsayi oranını hesapla
      5. Hiçbiri → 422 Unprocessable Entity hatası
    """
    __tablename__ = 'birim_donusum'  # MySQL'deki tablo adı
    id              = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    kaynak_birim_id = Column(Integer, ForeignKey('birim.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    hedef_birim_id  = Column(Integer, ForeignKey('birim.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    carpan          = Column(Numeric(20, 10), nullable=False)   # 1 kaynak = carpan × hedef
    aciklama        = Column(String(200))  # DB sütunu
    aktif           = Column(Boolean, default=True, nullable=False)  # DB sütunu
    __table_args__ = (  # Tablo düzeyinde kısıtlar ve indeksler
        UniqueConstraint('kaynak_birim_id', 'hedef_birim_id', name='uq_donusum_kh'),  # Çift kural yok
        Index('ix_donusum_kaynak', 'kaynak_birim_id'),  # Kaynak birime göre dönüşüm sorgusu
    )


class Cari(Base):
    """
    Müşteri ve tedarikçi kayıtları (cari hesaplar).
    tip değerleri:
      ALICI     → yalnızca müşteri (satış yapılan)
      SATICI    → yalnızca tedarikçi (alım yapılan)
      HER_IKISI → hem müşteri hem tedarikçi

    Bakiye = SUM(BORC) - SUM(ALACAK)
      Pozitif → cari bize borçlu (alacaklıyız)
      Negatif → biz cariye borçluyuz

    sehir alanı hızlı filtreleme için ayrı tutulur (adres serbest metinden arama yavaş).
    hesap_grubu_id → muhasebe hesap planı entegrasyonu için.
    """
    __tablename__ = 'cari'  # MySQL'deki tablo adı
    id               = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    kod              = Column(String(20), unique=True, nullable=False)   # Benzersiz cari kodu
    unvan            = Column(String(200), nullable=False)               # Firma/kişi adı
    tip              = Column(Enum('ALICI', 'SATICI', 'HER_IKISI'), nullable=False)  # DB sütunu
    vergi_no         = Column(String(20))        # VKN (10 hane) veya TCKN (11 hane)
    vergi_dairesi    = Column(String(100))  # DB sütunu
    telefon          = Column(String(20))        # Kısa erişim için (detaylı → cari_iletisim)
    email            = Column(String(100))  # DB sütunu
    adres            = Column(Text)              # Kısa adres (detaylı → cari_adres)
    sehir            = Column(String(50))        # Şehir filtresi için ayrı alan
    hesap_grubu_id   = Column(Integer, ForeignKey('hesap_grubu.id', ondelete='SET NULL'))  # DB sütunu
    aktif            = Column(Boolean, default=True, nullable=False)  # DB sütunu
    olusturma_tarihi = Column(DateTime, default=datetime.now)  # DB sütunu


class CariHareket(Base):
    """
    Cari hesap ekstresi — tüm borç/alacak hareketleri.
    kaynak_tip + kaynak_id → hareketin izlenebilirliği:
      kaynak_tip='FATURA' → belge_baslik tablosundaki id
      kaynak_tip='FIS'    → cari_hesap_fis tablosundaki id
    İptal işlemlerinde kaynak_id'ye göre bağlı hareketler bulunup silinebilir.
    Bileşik indeks (cari_id, tarih) → cari ekstresi sorgusunu hızlandırır.
    """
    __tablename__ = 'cari_hareket'  # MySQL'deki tablo adı
    id           = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    cari_id      = Column(Integer, ForeignKey('cari.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    tarih        = Column(Date, nullable=False, default=date.today)  # DB sütunu
    belge_no     = Column(String(50))       # İlgili belge numarası (fatura, fiş vb.)
    aciklama     = Column(String(500))  # DB sütunu
    hareket_tipi = Column(Enum('BORC', 'ALACAK'), nullable=False)  # DB sütunu
    # BORC   → cari bize borçlanıyor (satış yaptık)
    # ALACAK → biz cariye borçlanıyoruz (ödeme aldık veya iade ettik)
    tutar        = Column(Numeric(15, 2), nullable=False)  # DB sütunu
    kaynak_tip   = Column(String(20))       # Hareket kaynağı tipi ('FATURA', 'FIS'...)
    kaynak_id    = Column(Integer)          # Kaynak tablodaki kayıt ID'si
    __table_args__ = (Index('ix_ch_cari_tarih', 'cari_id', 'tarih'),)  # Tablo düzeyinde kısıtlar ve indeksler


class StokKarti(Base):
    """
    Ürün ve hizmet kartları.
    tip=MALZEME → fiziksel ürün; stok miktarı takip edilir
    tip=HIZMET  → soyut hizmet; stok takibi yapılmaz (miktar=None döner)

    birim_id    → ana stok birimi (miktarlar bu birimde raporlanır)
    hesap_grubu_id → stok hesap planı entegrasyonu için
    RESTRICT (birim_id): kullanımda olan birim silinemez.
    """
    __tablename__ = 'stok_karti'  # MySQL'deki tablo adı
    id               = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    kod              = Column(String(50), unique=True, nullable=False)    # Stok kodu (benzersiz)
    ad               = Column(String(200), nullable=False)                # Ürün/hizmet adı
    tip              = Column(Enum('MALZEME', 'HIZMET'), nullable=False)  # DB sütunu
    birim_id         = Column(Integer, ForeignKey('birim.id', ondelete='RESTRICT'), nullable=False)  # DB sütunu
    kdv_orani        = Column(Numeric(5, 2), default=20.00)   # Varsayılan %20 KDV
    satis_fiyati     = Column(Numeric(15, 4), default=0.0)    # Liste satış fiyatı
    alis_fiyati      = Column(Numeric(15, 4), default=0.0)    # Son alış / maliyet fiyatı
    aciklama         = Column(Text)  # DB sütunu
    aktif            = Column(Boolean, default=True, nullable=False)  # DB sütunu
    hesap_grubu_id   = Column(Integer, ForeignKey('hesap_grubu.id', ondelete='SET NULL'))  # DB sütunu
    olusturma_tarihi = Column(DateTime, default=datetime.now)  # DB sütunu


class StokHareket(Base):
    """
    Stok giriş/çıkış hareketleri.
    miktar          → hareket birimindeki miktar (belgedeki gibi)
    cevrilen_miktar → ana stok birimine çevrilmiş miktar
    Örnek: 5 KUTU giriş, 1 KUTU=12 ADET → miktar=5, cevrilen_miktar=60

    Güncel stok = SUM(GIRIS cevrilen_miktar) - SUM(CIKIS cevrilen_miktar)
    birim_fiyat → o hareketteki birim maliyet fiyatı (FIFO/Ortalama için)
    """
    __tablename__ = 'stok_hareket'  # MySQL'deki tablo adı
    id              = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    stok_id         = Column(Integer, ForeignKey('stok_karti.id', ondelete='CASCADE'), nullable=False)  # DB sütunu
    tarih           = Column(Date, nullable=False, default=date.today)  # DB sütunu
    belge_no        = Column(String(50))           # Kaynak belge numarası
    hareket_tipi    = Column(Enum('GIRIS', 'CIKIS'), nullable=False)  # DB sütunu
    birim_id        = Column(Integer, ForeignKey('birim.id', ondelete='RESTRICT'))  # Hareket birimi
    miktar          = Column(Numeric(15, 4), nullable=False)    # Hareket birimindeki miktar
    cevrilen_miktar = Column(Numeric(15, 4))                    # Ana stok birimine çevrilmiş
    birim_fiyat     = Column(Numeric(15, 4))                    # Birim maliyet/satış fiyatı
    aciklama        = Column(String(500))  # DB sütunu
    __table_args__ = (Index('ix_sh_stok_tarih', 'stok_id', 'tarih'),)  # Tablo düzeyinde kısıtlar ve indeksler


class BelgeBaslik(Base):
    """
    Tüm ticari belgelerin başlık tablosu.
    Belge dönüşüm zinciri (kaynak_belge_id ile takip edilir):
      Talep → Sipariş → İrsaliye → Fatura

    evrak_no   → karşı tarafın sipariş/fatura numarası
    depo_id    → irsaliye/teslim deposu
    Toplam alanlar (kdvsiz/kdv/kdvli) satırlar eklendikten sonra güncellenir.

    İndeksler:
      (belge_tip, cari_tip, tarih) → liste/arama sayfaları
      (cari_id)                    → cariye ait belgeler
    """
    __tablename__ = 'belge_baslik'  # MySQL'deki tablo adı
    id               = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    belge_tip        = Column(Enum('TALEP', 'SIPARIS', 'IRSALIYE', 'FATURA'), nullable=False)  # DB sütunu
    belge_no         = Column(String(50), unique=True, nullable=False)    # Benzersiz belge numarası
    tarih            = Column(Date, nullable=False, default=date.today)  # DB sütunu
    vade_tarihi      = Column(Date)                              # Ödeme vadesi
    cari_id          = Column(Integer, ForeignKey('cari.id', ondelete='SET NULL'))  # DB sütunu
    cari_tip         = Column(Enum('SATIS', 'ALIS'), nullable=False, default='SATIS')  # Zorunlu alan — NULL kabul etmez
    aciklama         = Column(Text)  # DB sütunu
    durum            = Column(Enum('ACIK', 'ONAYLANDI', 'IPTAL'), default='ACIK')  # DB sütunu
    kaynak_belge_id  = Column(Integer, ForeignKey('belge_baslik.id', ondelete='SET NULL'))  # Dönüşüm zinciri
    toplam_kdvsiz    = Column(Numeric(15, 2), default=0.00)      # KDV hariç toplam
    toplam_kdv       = Column(Numeric(15, 2), default=0.00)      # Toplam KDV tutarı
    toplam_kdvli     = Column(Numeric(15, 2), default=0.00)      # KDV dahil genel toplam
    sirket_id        = Column(Integer, ForeignKey('sirket.id', ondelete='SET NULL'))  # Hangi şirkete ait
    depo_id          = Column(Integer, ForeignKey('depo.id', ondelete='SET NULL'))    # Sevkiyat deposu
    evrak_no         = Column(String(50))                        # Karşı taraf evrak numarası
    olusturma_tarihi = Column(DateTime, default=datetime.now)  # DB sütunu
    # order_by: satırlar sira_no'ya göre sıralı gelir
    # cascade='all, delete-orphan': belge silinince satırlar da silinir
    satirlar         = relationship('BelgeSatir', backref='baslik',  # Ters ilişki: ilişkili nesneden bu nesneye erişim
                                    cascade='all, delete-orphan', order_by='BelgeSatir.sira_no')  # Ebeveyn silinince tüm çocuk kayıtlar da silinir
    __table_args__ = (  # Tablo düzeyinde kısıtlar ve indeksler
        Index('ix_bb_tip_ctip_tarih', 'belge_tip', 'cari_tip', 'tarih'),  # Belge liste/arama sayfası indeksi
        Index('ix_bb_cari', 'cari_id'),  # Cariye ait belgeler indeksi
    )


class BelgeSatir(Base):
    """
    Belge ürün/hizmet satırları.
    Tutar hesaplama formülleri (API tarafı hesaplamaz; önceden hesaplanmış gönderilir):
      brut         = miktar × birim_fiyat
      kdvsiz_tutar = brut × (1 - iskonto_oran/100)
      kdv_tutar    = kdvsiz_tutar × (kdv_orani/100)
      kdvli_tutar  = kdvsiz_tutar + kdv_tutar

    stok_id=NULL → serbest metin satırı (katalog dışı ürün/hizmet açıklaması).
    birim_id → satırın birimi (stok kartının ana biriminden farklı olabilir).
    RESTRICT (birim_id): kullanımda olan birim silinemez.
    """
    __tablename__ = 'belge_satir'  # MySQL'deki tablo adı
    id           = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    baslik_id    = Column(Integer, ForeignKey('belge_baslik.id', ondelete='CASCADE'), nullable=False)  # Ebeveyn silinince ilişkili kayıtlar da silinir
    sira_no      = Column(SmallInteger, nullable=False)            # Satır sırası (1'den başlar)
    stok_id      = Column(Integer, ForeignKey('stok_karti.id', ondelete='SET NULL'))  # NULL=serbest satır
    aciklama     = Column(String(500))  # DB sütunu
    miktar       = Column(Numeric(15, 4), nullable=False, default=1.0)  # DB sütunu
    birim_id     = Column(Integer, ForeignKey('birim.id', ondelete='RESTRICT'))  # Satır birimi
    birim_fiyat  = Column(Numeric(15, 4), nullable=False, default=0.0)  # Birim satış/alış fiyatı
    iskonto_oran = Column(Numeric(5, 2), default=0.00)    # İskonto yüzdesi (10.00 = %10)
    kdv_orani    = Column(Numeric(5, 2), default=20.00)   # KDV yüzdesi (20.00 = %20)
    kdvsiz_tutar = Column(Numeric(15, 2), default=0.00)   # İskonto sonrası KDV hariç tutar
    kdv_tutar    = Column(Numeric(15, 2), default=0.00)   # Bu satırın KDV tutarı
    kdvli_tutar  = Column(Numeric(15, 2), default=0.00)   # Satır toplamı (KDV dahil)
    __table_args__ = (Index('ix_bs_baslik', 'baslik_id'),)  # Belgeye göre satır listesi


# ════════════════════════════════════════════════════════════
#  PYDANTIC ŞEMALARI
# ════════════════════════════════════════════════════════════

# ── Şirket ──────────────────────────────────────────────────
class SirketCreate(BaseModel):
    kod: str  # Benzersiz kısa kod
    unvan: str  # Ticaret unvanı
    vergi_no: Optional[str] = None  # VKN (10 hane) veya TCKN (11 hane)
    vergi_dairesi: Optional[str] = None  # Bağlı vergi dairesi
    telefon: Optional[str] = None  # Telefon numarası
    email: Optional[str] = None  # E-posta adresi
    adres: Optional[str] = None  # Adres metni
    logo_url: Optional[str] = None  # Logo görsel URL'si
    aktif: bool = True  # False = pasif/silindi

class SirketRead(SirketCreate):
    id: int
    olusturma_tarihi: Optional[datetime] = None  # Kayıt oluşturma zamanı
    class Config:
        from_attributes = True


# ── Depo ────────────────────────────────────────────────────
class DepoCreate(BaseModel):
    sirket_id: int  # Hangi şirkete ait
    kod: str  # Benzersiz kısa kod
    ad: str  # Ad/başlık
    adres: Optional[str] = None  # Adres metni
    aktif: bool = True  # False = pasif/silindi

class DepoRead(DepoCreate):
    id: int
    class Config:
        from_attributes = True


# ── NumaraSira ──────────────────────────────────────────────
class NumaraSiraCreate(BaseModel):
    sirket_id: int  # Hangi şirkete ait
    belge_tip: str  # TALEP | SIPARIS | IRSALIYE | FATURA
    cari_tip: str  # SATIS | ALIS
    prefix: str  # Numara öneki: FAT, SIP, IRS...
    yil: int  # Hangi yıl (örn. 2025)
    son_sayi: int = 0  # Başlangıç sayacı (0 → 00001'den başlar)
    basamak: int = 5  # Sayacın kaç basamak olacağı

class NumaraSiraRead(NumaraSiraCreate):
    id: int
    class Config:
        from_attributes = True


# ── DövizTürü ───────────────────────────────────────────────
class DovizTuruCreate(BaseModel):
    kod: str  # Benzersiz kısa kod
    ad: str  # Ad/başlık
    sembol: Optional[str] = None  # Para sembolü: ₺, $, €
    aktif: bool = True  # False = pasif/silindi

class DovizTuruRead(DovizTuruCreate):
    id: int
    class Config:
        from_attributes = True


# ── BankaHesap ──────────────────────────────────────────────
class BankaHesapCreate(BaseModel):
    sirket_id: int  # Hangi şirkete ait
    kod: str  # Benzersiz kısa kod
    banka_adi: str  # Banka adı
    sube_adi: Optional[str] = None  # Şube adı
    sube_kodu: Optional[str] = None  # Şube numarası
    hesap_no: Optional[str] = None  # Hesap numarası
    iban: Optional[str] = None  # IBAN (TR+24 karakter, boşluksuz)
    doviz_id: Optional[int] = None  # Para birimi FK (doviz_turu.id)
    aciklama: Optional[str] = None  # Ek açıklama
    aktif: bool = True  # False = pasif/silindi

class BankaHesapRead(BankaHesapCreate):
    id: int
    class Config:
        from_attributes = True


# ── BankaHareket ────────────────────────────────────────────
class BankaHareketCreate(BaseModel):
    banka_hesap_id: int  # Hangi banka hesabına ait
    tarih: date  # İşlem tarihi
    fisno: Optional[str] = None  # Fiş/dekont numarası
    fis_tipi: str  # TAHSILAT | ODEME | HAVALE_GIRIS | TRANSFER...
    yon: str  # GIRIS | CIKIS
    tutar: float  # İşlem tutarı
    aciklama: Optional[str] = None  # Ek açıklama
    cari_id: Optional[int] = None  # İlgili cari hesap (opsiyonel)
    karsit_hesap_id: Optional[int] = None  # Havale: karşı banka hesabı
    karsit_kasa_id: Optional[int] = None  # Transfer: karşı kasa

class BankaHareketRead(BankaHareketCreate):
    id: int
    olusturma_tarihi: Optional[datetime] = None  # Kayıt oluşturma zamanı
    class Config:
        from_attributes = True


# ── KasaHesap ───────────────────────────────────────────────
class KasaHesapCreate(BaseModel):
    sirket_id: int  # Hangi şirkete ait
    kod: str  # Benzersiz kısa kod
    ad: str  # Ad/başlık
    doviz_id: Optional[int] = None  # Para birimi FK (doviz_turu.id)
    aciklama: Optional[str] = None  # Ek açıklama
    aktif: bool = True  # False = pasif/silindi

class KasaHesapRead(KasaHesapCreate):
    id: int
    class Config:
        from_attributes = True


# ── KasaHareket ─────────────────────────────────────────────
class KasaHareketCreate(BaseModel):
    kasa_hesap_id: int  # Hangi kasaya ait
    tarih: date  # İşlem tarihi
    fisno: Optional[str] = None  # Fiş/dekont numarası
    fis_tipi: str  # TAHSILAT | ODEME | HAVALE_GIRIS | TRANSFER...
    yon: str  # GIRIS | CIKIS
    tutar: float  # İşlem tutarı
    aciklama: Optional[str] = None  # Ek açıklama
    cari_id: Optional[int] = None  # İlgili cari hesap (opsiyonel)
    karsit_kasa_id: Optional[int] = None  # Transfer: karşı kasa
    karsit_banka_id: Optional[int] = None  # Transfer: karşı banka

class KasaHareketRead(KasaHareketCreate):
    id: int
    olusturma_tarihi: Optional[datetime] = None  # Kayıt oluşturma zamanı
    class Config:
        from_attributes = True


# ── CariHesapFisSatir ───────────────────────────────────────
class CariHesapFisSatirCreate(BaseModel):
    cari_id: int  # Hangi cariye ait
    hareket_tipi: str  # BORC | ALACAK (cari için) | GIRIS | CIKIS (stok için)
    tutar: float  # İşlem tutarı
    aciklama: Optional[str] = None  # Ek açıklama

class CariHesapFisSatirRead(CariHesapFisSatirCreate):
    id: int
    fis_id: int  # Ait olduğu fiş ID'si
    class Config:
        from_attributes = True


# ── CariHesapFis ────────────────────────────────────────────
class CariHesapFisCreate(BaseModel):
    sirket_id: Optional[int] = None  # Şirket FK (opsiyonel)
    fisno: str  # Benzersiz fiş numarası
    tarih: date  # İşlem tarihi
    aciklama: Optional[str] = None  # Ek açıklama
    satirlar: List[CariHesapFisSatirCreate] = []  # Fiş satır listesi

class CariHesapFisRead(BaseModel):
    id: int
    sirket_id: Optional[int] = None  # Şirket FK (opsiyonel)
    fisno: str  # Benzersiz fiş numarası
    tarih: date  # İşlem tarihi
    aciklama: Optional[str] = None  # Ek açıklama
    olusturma_tarihi: Optional[datetime] = None  # Kayıt oluşturma zamanı
    satirlar: List[CariHesapFisSatirRead] = []  # Fiş satırları dahil
    class Config:
        from_attributes = True


# ── CariBankaHesap ──────────────────────────────────────────
class CariBankaHesapCreate(BaseModel):
    cari_id: int  # Hangi cariye ait
    banka_adi: str  # Banka adı
    sube_adi: Optional[str] = None  # Şube adı
    hesap_no: Optional[str] = None  # Hesap numarası
    iban: Optional[str] = None  # IBAN (TR+24 karakter, boşluksuz)
    doviz_id: Optional[int] = None  # Para birimi FK (doviz_turu.id)
    aciklama: Optional[str] = None  # Ek açıklama
    varsayilan: bool = False  # True = birincil kayıt olarak işaretle
    aktif: bool = True  # False = pasif/silindi

class CariBankaHesapRead(CariBankaHesapCreate):
    id: int
    class Config:
        from_attributes = True


# ── CariIletisim ────────────────────────────────────────────
class CariIletisimCreate(BaseModel):
    cari_id: int  # Hangi cariye ait
    tip: str  # Kayıt türü
    deger: str  # Numara, adres veya URL
    aciklama: Optional[str] = None  # Ek açıklama
    varsayilan: bool = False  # True = birincil kayıt olarak işaretle
    aktif: bool = True  # False = pasif/silindi

class CariIletisimRead(CariIletisimCreate):
    id: int
    class Config:
        from_attributes = True


# ── Kullanıcı ────────────────────────────────────────────────
class KullaniciCreate(BaseModel):
    ad_soyad: str  # Ad ve soyadı
    email: str  # Giriş için benzersiz e-posta
    rol: str = 'STANDART'  # ADMIN | STANDART | SADECE_OKUMA
    tema: str = 'dark'  # UI renk tercihi (dark, light...)
    aktif: bool = True  # False = pasif/silindi

class KullaniciRead(KullaniciCreate):
    id: int
    olusturma_tarihi: Optional[datetime] = None  # Kayıt oluşturma zamanı
    class Config:
        from_attributes = True


# ── CekSenet ────────────────────────────────────────────────
class CekSenetCreate(BaseModel):
    sirket_id: int  # Hangi şirkete ait
    tip: str  # Kayıt türü
    yon: str  # GIRIS | CIKIS
    seri_no: Optional[str] = None  # Çek/senet seri numarası
    banka: Optional[str] = None  # Keşidecinin bankası
    sube: Optional[str] = None  # Banka şubesi
    kesideci: Optional[str] = None  # Çeki düzenleyen kişi/firma
    cari_id: Optional[int] = None  # İlgili cari hesap (opsiyonel)
    tutar: float  # İşlem tutarı
    doviz_id: Optional[int] = None  # Para birimi FK (doviz_turu.id)
    vade_tarihi: date  # Ödeme/tahsil vadesi (zorunlu)
    durum: str = 'PORTFOY'
    aciklama: Optional[str] = None  # Ek açıklama

class CekSenetRead(CekSenetCreate):
    id: int
    olusturma_tarihi: Optional[datetime] = None  # Kayıt oluşturma zamanı
    class Config:
        from_attributes = True


# ── TaksitPlan ──────────────────────────────────────────────
class TaksitPlanCreate(BaseModel):
    belge_id: int  # Hangi belgeye ait
    taksit_no: int  # Sıra numarası (1, 2, 3...)
    vade_tarihi: date  # Ödeme/tahsil vadesi (zorunlu)
    tutar: float  # İşlem tutarı
    odendi: bool = False  # Ödeme gerçekleşti mi
    odeme_tarihi: Optional[date] = None  # Fiili ödeme tarihi
    aciklama: Optional[str] = None  # Ek açıklama

class TaksitPlanRead(TaksitPlanCreate):
    id: int
    class Config:
        from_attributes = True


# ── HesapGrubu ──────────────────────────────────────────────
class HesapGrubuCreate(BaseModel):
    tip: str  # Kayıt türü
    seviye: int = 1  # Ağaç derinliği (1=kök)
    parent_id: Optional[int] = None  # Üst grup (None = kök grup)
    kod: str  # Benzersiz kısa kod
    ad: str  # Ad/başlık
    aciklama: Optional[str] = None  # Ek açıklama
    aktif: bool = True  # False = pasif/silindi

class HesapGrubuRead(HesapGrubuCreate):
    id: int
    class Config:
        from_attributes = True


# ── Rapor ────────────────────────────────────────────────────
class RaporCreate(BaseModel):
    ad: str  # Ad/başlık
    aciklama: Optional[str] = None  # Ek açıklama
    sql_sorgu: str  # SELECT sorgusu (API güvenlik kontrolü uygular)
    kategori: Optional[str] = None  # Gruplama etiketi: Cari, Stok, Finans...
    aktif: bool = True  # False = pasif/silindi

class RaporRead(RaporCreate):
    id: int
    olusturma_tarihi: Optional[datetime] = None  # Kayıt oluşturma zamanı
    class Config:
        from_attributes = True


# ── Adres Referansları ──────────────────────────────────────
class UlkeRead(BaseModel):
    id: int; kod: str; ad: str; aktif: bool
    class Config:
        from_attributes = True

class IlRead(BaseModel):
    id: int; ulke_id: int; plaka: Optional[str]; ad: str; aktif: bool
    class Config:
        from_attributes = True

class IlceRead(BaseModel):
    id: int; il_id: int; ad: str; aktif: bool
    class Config:
        from_attributes = True

class MahalleRead(BaseModel):
    id: int; ilce_id: int; ad: str; posta_kodu: Optional[str]; aktif: bool
    class Config:
        from_attributes = True


# ── CariAdres ───────────────────────────────────────────────
class CariAdresCreate(BaseModel):
    cari_id: int  # Hangi cariye ait
    adres_tipi: str = 'MERKEZ'
    ulke_id: Optional[int] = None  # Ülke seçimi (cascade dropdown adım 1)
    il_id: Optional[int] = None  # İl seçimi (cascade dropdown adım 2)
    ilce_id: Optional[int] = None  # İlçe seçimi (cascade dropdown adım 3)
    mahalle_id: Optional[int] = None  # Mahalle seçimi (cascade dropdown adım 4)
    sokak: Optional[str] = None  # Cadde/sokak adı
    bina_no: Optional[str] = None  # Kapı/bina numarası
    daire_no: Optional[str] = None  # Daire/ofis numarası
    posta_kodu: Optional[str] = None  # Posta kodu
    aciklama: Optional[str] = None  # Ek açıklama
    varsayilan: bool = False  # True = birincil kayıt olarak işaretle
    aktif: bool = True  # False = pasif/silindi

class CariAdresRead(CariAdresCreate):
    id: int
    class Config:
        from_attributes = True


# ── v1 şemaları (değişmedi) ──────────────────────────────────
class BirimGrubuCreate(BaseModel):
    ad: str; aciklama: Optional[str] = None; aktif: bool = True

class BirimGrubuRead(BirimGrubuCreate):
    id: int
    class Config:
        from_attributes = True

class BirimCreate(BaseModel):
    grup_id: int; kod: str; ad: str; katsayi: float = 1.0; taban_mi: bool = False; aktif: bool = True

class BirimRead(BirimCreate):
    id: int
    class Config:
        from_attributes = True

class BirimDonusumCreate(BaseModel):
    kaynak_birim_id: int; hedef_birim_id: int; carpan: float
    aciklama: Optional[str] = None; aktif: bool = True

class BirimDonusumRead(BirimDonusumCreate):
    id: int
    class Config:
        from_attributes = True

class CariCreate(BaseModel):
    kod: str; unvan: str; tip: str
    vergi_no: Optional[str] = None; vergi_dairesi: Optional[str] = None
    telefon: Optional[str] = None; email: Optional[str] = None
    adres: Optional[str] = None; sehir: Optional[str] = None
    hesap_grubu_id: Optional[int] = None; aktif: bool = True

class CariRead(CariCreate):
    id: int; olusturma_tarihi: Optional[datetime] = None
    class Config:
        from_attributes = True

class CariHareketCreate(BaseModel):
    cari_id: int; tarih: date; belge_no: Optional[str] = None  # Hangi cariye ait
    aciklama: Optional[str] = None; hareket_tipi: str; tutar: float
    kaynak_tip: Optional[str] = None; kaynak_id: Optional[int] = None

class CariHareketRead(CariHareketCreate):
    id: int
    class Config:
        from_attributes = True

class StokKartiCreate(BaseModel):
    kod: str; ad: str; tip: str; birim_id: int
    kdv_orani: float = 20.0; satis_fiyati: float = 0.0; alis_fiyati: float = 0.0
    aciklama: Optional[str] = None; aktif: bool = True; hesap_grubu_id: Optional[int] = None

class StokKartiRead(StokKartiCreate):
    id: int; olusturma_tarihi: Optional[datetime] = None
    class Config:
        from_attributes = True

class StokHareketCreate(BaseModel):
    stok_id: int; tarih: date; belge_no: Optional[str] = None
    hareket_tipi: str; birim_id: Optional[int] = None; miktar: float
    cevrilen_miktar: Optional[float] = None; birim_fiyat: Optional[float] = None
    aciklama: Optional[str] = None  # Ek açıklama

class StokHareketRead(StokHareketCreate):
    id: int
    class Config:
        from_attributes = True

class BelgeSatirCreate(BaseModel):
    sira_no: int; stok_id: Optional[int] = None; aciklama: Optional[str] = None
    miktar: float = 1.0; birim_id: Optional[int] = None; birim_fiyat: float = 0.0
    iskonto_oran: float = 0.0; kdv_orani: float = 20.0
    kdvsiz_tutar: float = 0.0; kdv_tutar: float = 0.0; kdvli_tutar: float = 0.0

class BelgeSatirRead(BelgeSatirCreate):
    id: int; baslik_id: int
    class Config:
        from_attributes = True

class BelgeBaslikCreate(BaseModel):
    belge_tip: str; belge_no: str; tarih: date; vade_tarihi: Optional[date] = None
    cari_id: Optional[int] = None; cari_tip: str = 'SATIS'
    aciklama: Optional[str] = None; durum: str = 'ACIK'
    kaynak_belge_id: Optional[int] = None
    toplam_kdvsiz: float = 0.0; toplam_kdv: float = 0.0; toplam_kdvli: float = 0.0
    sirket_id: Optional[int] = None; depo_id: Optional[int] = None  # Şirket FK (opsiyonel)
    evrak_no: Optional[str] = None
    satirlar: List[BelgeSatirCreate] = []

class BelgeBaslikRead(BaseModel):
    id: int; belge_tip: str; belge_no: str; tarih: date; vade_tarihi: Optional[date] = None
    cari_id: Optional[int] = None; cari_tip: str; aciklama: Optional[str] = None
    durum: str; kaynak_belge_id: Optional[int] = None
    toplam_kdvsiz: Optional[float] = None; toplam_kdv: Optional[float] = None; toplam_kdvli: Optional[float] = None
    sirket_id: Optional[int] = None; depo_id: Optional[int] = None  # Şirket FK (opsiyonel)
    evrak_no: Optional[str] = None; olusturma_tarihi: Optional[datetime] = None
    satirlar: List[BelgeSatirRead] = []

    @classmethod
    def from_orm_obj(cls, obj: BelgeBaslik) -> "BelgeBaslikRead":
        return cls(
            id=obj.id, belge_tip=obj.belge_tip, belge_no=obj.belge_no,
            tarih=obj.tarih, vade_tarihi=obj.vade_tarihi,
            cari_id=obj.cari_id, cari_tip=obj.cari_tip,
            aciklama=obj.aciklama, durum=obj.durum,
            kaynak_belge_id=obj.kaynak_belge_id,
            toplam_kdvsiz=d(obj.toplam_kdvsiz), toplam_kdv=d(obj.toplam_kdv),
            toplam_kdvli=d(obj.toplam_kdvli),
            sirket_id=obj.sirket_id, depo_id=obj.depo_id,
            evrak_no=obj.evrak_no, olusturma_tarihi=obj.olusturma_tarihi,
            satirlar=[BelgeSatirRead.model_validate(s) for s in obj.satirlar],
        )


# ════════════════════════════════════════════════════════════
#  FASTAPI UYGULAMASI
# ════════════════════════════════════════════════════════════

app = FastAPI(
    title="Muhasebe API v2",
    description="Muhasebe programının tüm tablolarına REST erişimi (v2 - Finans, Şirket, Adres, Kullanıcı modülleri dahil)",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Üretimde kısıtlayın!
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Yardımcı CRUD fabrikası ────────────────────────────────

def get_or_404(db: Session, model, id: int):
    obj = db.get(model, id)
    if not obj:
        raise HTTPException(404, f"{model.__tablename__} bulunamadı (id={id})")
    return obj


# ════════════════════════════════════════════════════════════
#  GENEL
# ════════════════════════════════════════════════════════════

@app.get("/health", tags=["Genel"])
def health(db: Session = Depends(get_db)):
    from sqlalchemy import text  # Ham SQL çalıştırmak için text() sarmalayıcısı
    try:
        db.execute(text("SELECT 1"))  # Ham SQL sorgusunu çalıştır
        return {"status": "ok", "version": "2.0.0", "time": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/api/v2/ozet", tags=["Genel"])
def ozet(sirket_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    q = db.query(BelgeBaslik)  # Sorgu başlat
    if sirket_id:
        q = q.filter(BelgeBaslik.sirket_id == sirket_id)  # Koşullu filtrele

    def banka_toplam(hesap_id, yon):
        return float(db.query(func.sum(BankaHareket.tutar)).filter(
            BankaHareket.banka_hesap_id == hesap_id,
            BankaHareket.yon == yon).scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)

    banka_toplam_giris = float(db.query(func.sum(BankaHareket.tutar)).filter_by(yon='GIRIS').scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    banka_toplam_cikis = float(db.query(func.sum(BankaHareket.tutar)).filter_by(yon='CIKIS').scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    kasa_toplam_giris  = float(db.query(func.sum(KasaHareket.tutar)).filter_by(yon='GIRIS').scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    kasa_toplam_cikis  = float(db.query(func.sum(KasaHareket.tutar)).filter_by(yon='CIKIS').scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)

    return {
        "cari_sayisi":       db.query(func.count(Cari.id)).filter_by(aktif=True).scalar(),  # Tek değer döndür (toplam, sayı vb.)
        "stok_sayisi":       db.query(func.count(StokKarti.id)).filter_by(aktif=True).scalar(),  # Tek değer döndür (toplam, sayı vb.)
        "birim_sayisi":      db.query(func.count(Birim.id)).filter_by(aktif=True).scalar(),  # Tek değer döndür (toplam, sayı vb.)
        "sirket_sayisi":     db.query(func.count(Sirket.id)).filter_by(aktif=True).scalar(),  # Tek değer döndür (toplam, sayı vb.)
        "acik_fatura":       q.filter_by(belge_tip='FATURA', durum='ACIK').count(),
        "acik_siparis":      q.filter_by(belge_tip='SIPARIS', durum='ACIK').count(),
        "banka_net_bakiye":  round(banka_toplam_giris - banka_toplam_cikis, 2),
        "kasa_net_bakiye":   round(kasa_toplam_giris - kasa_toplam_cikis, 2),
        "vadesi_gelen_cek":  db.query(func.count(CekSenet.id)).filter(  # Kayıt sayısı
            CekSenet.durum == 'PORTFOY',
            CekSenet.vade_tarihi <= date.today()).scalar(),  # Tek değer döndür (toplam, sayı vb.)
    }


# ════════════════════════════════════════════════════════════
#  ŞİRKET  /api/v2/sirketler
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/sirketler", response_model=List[SirketRead], tags=["Şirket"])
def sirketler_listele(aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Sirket)  # Sorgu başlat
    if aktif is not None:
        q = q.filter(Sirket.aktif == aktif)  # Koşullu filtrele
    return q.order_by(Sirket.unvan).all()

@app.get("/api/v2/sirketler/{id}", response_model=SirketRead, tags=["Şirket"])
def sirket_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Sirket, id)

@app.post("/api/v2/sirketler", response_model=SirketRead, status_code=201, tags=["Şirket"])
def sirket_olustur(payload: SirketCreate, db: Session = Depends(get_db)):
    obj = Sirket(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v2/sirketler/{id}", response_model=SirketRead, tags=["Şirket"])
def sirket_guncelle(id: int, payload: SirketCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, Sirket, id)
    for k, v in payload.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/sirketler/{id}", tags=["Şirket"])
def sirket_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, Sirket, id); obj.aktif = False; db.commit()  # Soft delete: fiziksel silme yerine pasife al
    return {"ok": True, "mesaj": "Şirket pasife alındı"}


# ════════════════════════════════════════════════════════════
#  DEPO  /api/v2/depolar
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/depolar", response_model=List[DepoRead], tags=["Depo"])
def depolar_listele(sirket_id: Optional[int] = Query(None), aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Depo)  # Sorgu başlat
    if sirket_id: q = q.filter_by(sirket_id=sirket_id)  # Filtrele
    if aktif is not None: q = q.filter(Depo.aktif == aktif)  # Koşullu filtrele
    return q.order_by(Depo.ad).all()

@app.get("/api/v2/depolar/{id}", response_model=DepoRead, tags=["Depo"])
def depo_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Depo, id)

@app.post("/api/v2/depolar", response_model=DepoRead, status_code=201, tags=["Depo"])
def depo_olustur(payload: DepoCreate, db: Session = Depends(get_db)):
    obj = Depo(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v2/depolar/{id}", response_model=DepoRead, tags=["Depo"])
def depo_guncelle(id: int, payload: DepoCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, Depo, id)
    for k, v in payload.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/depolar/{id}", tags=["Depo"])
def depo_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, Depo, id); obj.aktif = False; db.commit()  # Soft delete: fiziksel silme yerine pasife al
    return {"ok": True, "mesaj": "Depo pasife alındı"}


# ════════════════════════════════════════════════════════════
#  NUMARA SIRA  /api/v2/numara-siralar
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/numara-siralar", response_model=List[NumaraSiraRead], tags=["Numara Sıra"])
def numara_siralar_listele(sirket_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    q = db.query(NumaraSira)  # Sorgu başlat
    if sirket_id: q = q.filter_by(sirket_id=sirket_id)  # Filtrele
    return q.all()

@app.post("/api/v2/numara-siralar", response_model=NumaraSiraRead, status_code=201, tags=["Numara Sıra"])
def numara_sira_olustur(payload: NumaraSiraCreate, db: Session = Depends(get_db)):
    obj = NumaraSira(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.get("/api/v2/numara-siralar/sonraki", tags=["Numara Sıra"])
def sonraki_belge_no(sirket_id: int, belge_tip: str, cari_tip: str = 'SATIS', db: Session = Depends(get_db)):
    sira = db.query(NumaraSira).filter_by(
        sirket_id=sirket_id, belge_tip=belge_tip.upper(),  # Büyük harfe çevir (kullanıcı küçük harf gönderebilir)
        cari_tip=cari_tip.upper(), yil=datetime.now().year).first()  # Büyük harfe çevir (kullanıcı küçük harf gönderebilir)
    if not sira:
        raise HTTPException(404, "Bu kriterlere uygun numara serisi bulunamadı")
    sira.son_sayi += 1
    no = f"{sira.prefix}{str(sira.yil)[2:]}{str(sira.son_sayi).zfill(sira.basamak)}"  # Sayıyı sıfır ile doldur (5 basamak → 00001)
    db.commit()
    return {"belge_no": no, "son_sayi": sira.son_sayi}


# ════════════════════════════════════════════════════════════
#  DÖVİZ TÜRÜ  /api/v2/dovizler
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/dovizler", response_model=List[DovizTuruRead], tags=["Döviz"])
def dovizler_listele(aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(DovizTuru)  # Sorgu başlat
    if aktif is not None: q = q.filter(DovizTuru.aktif == aktif)  # Koşullu filtrele
    return q.order_by(DovizTuru.kod).all()

@app.get("/api/v2/dovizler/{id}", response_model=DovizTuruRead, tags=["Döviz"])
def doviz_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, DovizTuru, id)

@app.post("/api/v2/dovizler", response_model=DovizTuruRead, status_code=201, tags=["Döviz"])
def doviz_olustur(payload: DovizTuruCreate, db: Session = Depends(get_db)):
    obj = DovizTuru(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v2/dovizler/{id}", response_model=DovizTuruRead, tags=["Döviz"])
def doviz_guncelle(id: int, payload: DovizTuruCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, DovizTuru, id)
    for k, v in payload.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)


# ════════════════════════════════════════════════════════════
#  BANKA HESAP  /api/v2/banka-hesaplari
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/banka-hesaplari", response_model=List[BankaHesapRead], tags=["Banka"])
def banka_hesaplari_listele(sirket_id: Optional[int] = Query(None), aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(BankaHesap)  # Sorgu başlat
    if sirket_id: q = q.filter_by(sirket_id=sirket_id)  # Filtrele
    if aktif is not None: q = q.filter(BankaHesap.aktif == aktif)  # Koşullu filtrele
    return q.order_by(BankaHesap.kod).all()

@app.get("/api/v2/banka-hesaplari/{id}", response_model=BankaHesapRead, tags=["Banka"])
def banka_hesap_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, BankaHesap, id)

@app.get("/api/v2/banka-hesaplari/{id}/bakiye", tags=["Banka"])
def banka_bakiye(id: int, db: Session = Depends(get_db)):
    get_or_404(db, BankaHesap, id)
    giris = float(db.query(func.sum(BankaHareket.tutar)).filter_by(banka_hesap_id=id, yon='GIRIS').scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    cikis = float(db.query(func.sum(BankaHareket.tutar)).filter_by(banka_hesap_id=id, yon='CIKIS').scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    return {"hesap_id": id, "giris": giris, "cikis": cikis, "bakiye": round(giris - cikis, 2)}

@app.post("/api/v2/banka-hesaplari", response_model=BankaHesapRead, status_code=201, tags=["Banka"])
def banka_hesap_olustur(payload: BankaHesapCreate, db: Session = Depends(get_db)):
    obj = BankaHesap(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v2/banka-hesaplari/{id}", response_model=BankaHesapRead, tags=["Banka"])
def banka_hesap_guncelle(id: int, payload: BankaHesapCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, BankaHesap, id)
    for k, v in payload.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/banka-hesaplari/{id}", tags=["Banka"])
def banka_hesap_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, BankaHesap, id); obj.aktif = False; db.commit()  # Soft delete: fiziksel silme yerine pasife al
    return {"ok": True, "mesaj": "Banka hesabı pasife alındı"}


# ── Banka Hareket ────────────────────────────────────────────

@app.get("/api/v2/banka-hareketler", response_model=List[BankaHareketRead], tags=["Banka"])
def banka_hareketler_listele(
    hesap_id: Optional[int] = Query(None),
    yon: Optional[str] = Query(None),
    tarih_baslangic: Optional[date] = Query(None),
    tarih_bitis: Optional[date] = Query(None),
    db: Session = Depends(get_db)  # DB oturumu dependency injection ile enjekte edilir
):
    q = db.query(BankaHareket)  # Sorgu başlat
    if hesap_id: q = q.filter_by(banka_hesap_id=hesap_id)  # Filtrele
    if yon: q = q.filter_by(yon=yon.upper())  # Filtrele
    if tarih_baslangic: q = q.filter(BankaHareket.tarih >= tarih_baslangic)  # Koşullu filtrele
    if tarih_bitis: q = q.filter(BankaHareket.tarih <= tarih_bitis)  # Koşullu filtrele
    return q.order_by(BankaHareket.tarih.desc()).all()

@app.get("/api/v2/banka-hareketler/{id}", response_model=BankaHareketRead, tags=["Banka"])
def banka_hareket_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, BankaHareket, id)

@app.post("/api/v2/banka-hareketler", response_model=BankaHareketRead, status_code=201, tags=["Banka"])
def banka_hareket_olustur(payload: BankaHareketCreate, db: Session = Depends(get_db)):
    obj = BankaHareket(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/banka-hareketler/{id}", tags=["Banka"])
def banka_hareket_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, BankaHareket, id); db.delete(obj); db.commit()  # Değişiklikleri veritabanına kalıcı olarak yaz
    return {"ok": True, "mesaj": "Hareket silindi"}


# ════════════════════════════════════════════════════════════
#  KASA HESAP  /api/v2/kasa-hesaplari
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/kasa-hesaplari", response_model=List[KasaHesapRead], tags=["Kasa"])
def kasa_hesaplari_listele(sirket_id: Optional[int] = Query(None), aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(KasaHesap)  # Sorgu başlat
    if sirket_id: q = q.filter_by(sirket_id=sirket_id)  # Filtrele
    if aktif is not None: q = q.filter(KasaHesap.aktif == aktif)  # Koşullu filtrele
    return q.order_by(KasaHesap.kod).all()

@app.get("/api/v2/kasa-hesaplari/{id}", response_model=KasaHesapRead, tags=["Kasa"])
def kasa_hesap_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, KasaHesap, id)

@app.get("/api/v2/kasa-hesaplari/{id}/bakiye", tags=["Kasa"])
def kasa_bakiye(id: int, db: Session = Depends(get_db)):
    get_or_404(db, KasaHesap, id)
    giris = float(db.query(func.sum(KasaHareket.tutar)).filter_by(kasa_hesap_id=id, yon='GIRIS').scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    cikis = float(db.query(func.sum(KasaHareket.tutar)).filter_by(kasa_hesap_id=id, yon='CIKIS').scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    return {"hesap_id": id, "giris": giris, "cikis": cikis, "bakiye": round(giris - cikis, 2)}

@app.post("/api/v2/kasa-hesaplari", response_model=KasaHesapRead, status_code=201, tags=["Kasa"])
def kasa_hesap_olustur(payload: KasaHesapCreate, db: Session = Depends(get_db)):
    obj = KasaHesap(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v2/kasa-hesaplari/{id}", response_model=KasaHesapRead, tags=["Kasa"])
def kasa_hesap_guncelle(id: int, payload: KasaHesapCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, KasaHesap, id)
    for k, v in payload.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/kasa-hesaplari/{id}", tags=["Kasa"])
def kasa_hesap_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, KasaHesap, id); obj.aktif = False; db.commit()  # Soft delete: fiziksel silme yerine pasife al
    return {"ok": True, "mesaj": "Kasa pasife alındı"}

@app.get("/api/v2/kasa-hareketler", response_model=List[KasaHareketRead], tags=["Kasa"])
def kasa_hareketler_listele(
    hesap_id: Optional[int] = Query(None), yon: Optional[str] = Query(None),
    tarih_baslangic: Optional[date] = Query(None), tarih_bitis: Optional[date] = Query(None),
    db: Session = Depends(get_db)  # DB oturumu dependency injection ile enjekte edilir
):
    q = db.query(KasaHareket)  # Sorgu başlat
    if hesap_id: q = q.filter_by(kasa_hesap_id=hesap_id)  # Filtrele
    if yon: q = q.filter_by(yon=yon.upper())  # Filtrele
    if tarih_baslangic: q = q.filter(KasaHareket.tarih >= tarih_baslangic)  # Koşullu filtrele
    if tarih_bitis: q = q.filter(KasaHareket.tarih <= tarih_bitis)  # Koşullu filtrele
    return q.order_by(KasaHareket.tarih.desc()).all()

@app.post("/api/v2/kasa-hareketler", response_model=KasaHareketRead, status_code=201, tags=["Kasa"])
def kasa_hareket_olustur(payload: KasaHareketCreate, db: Session = Depends(get_db)):
    obj = KasaHareket(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/kasa-hareketler/{id}", tags=["Kasa"])
def kasa_hareket_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, KasaHareket, id); db.delete(obj); db.commit()  # Değişiklikleri veritabanına kalıcı olarak yaz
    return {"ok": True, "mesaj": "Hareket silindi"}


# ════════════════════════════════════════════════════════════
#  CARİ HESAP FİŞİ  /api/v2/cari-fisler
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/cari-fisler", response_model=List[CariHesapFisRead], tags=["Cari Fiş"])
def cari_fisler_listele(sirket_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    q = db.query(CariHesapFis)  # Sorgu başlat
    if sirket_id: q = q.filter_by(sirket_id=sirket_id)  # Filtrele
    return q.order_by(CariHesapFis.tarih.desc()).all()

@app.get("/api/v2/cari-fisler/{id}", response_model=CariHesapFisRead, tags=["Cari Fiş"])
def cari_fis_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, CariHesapFis, id)

@app.post("/api/v2/cari-fisler", response_model=CariHesapFisRead, status_code=201, tags=["Cari Fiş"])
def cari_fis_olustur(payload: CariHesapFisCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"satirlar"})  # Pydantic → dict dönüşümü
    fis = CariHesapFis(**data); db.add(fis); db.flush()  # Commit olmadan oturumu senkronize et (ID almak için)
    for s in payload.satirlar:
        satir = CariHesapFisSatir(fis_id=fis.id, **s.model_dump())
        db.add(satir)  # Oturuma ekle
    db.commit(); db.refresh(fis); return fis  # Değişiklikleri veritabanına kalıcı olarak yaz

@app.delete("/api/v2/cari-fisler/{id}", tags=["Cari Fiş"])
def cari_fis_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, CariHesapFis, id); db.delete(obj); db.commit()  # Değişiklikleri veritabanına kalıcı olarak yaz
    return {"ok": True, "mesaj": "Fiş silindi"}


# ════════════════════════════════════════════════════════════
#  ÇEK / SENET  /api/v2/cek-senetler
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/cek-senetler", response_model=List[CekSenetRead], tags=["Çek/Senet"])
def cek_senetler_listele(
    sirket_id: Optional[int] = Query(None),
    tip: Optional[str] = Query(None, description="CEK | SENET"),
    yon: Optional[str] = Query(None, description="ALACAK | BORC"),
    durum: Optional[str] = Query(None),
    db: Session = Depends(get_db)  # DB oturumu dependency injection ile enjekte edilir
):
    q = db.query(CekSenet)  # Sorgu başlat
    if sirket_id: q = q.filter_by(sirket_id=sirket_id)  # Filtrele
    if tip: q = q.filter_by(tip=tip.upper())  # Filtrele
    if yon: q = q.filter_by(yon=yon.upper())  # Filtrele
    if durum: q = q.filter_by(durum=durum.upper())  # Filtrele
    return q.order_by(CekSenet.vade_tarihi).all()

@app.get("/api/v2/cek-senetler/{id}", response_model=CekSenetRead, tags=["Çek/Senet"])
def cek_senet_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, CekSenet, id)

@app.post("/api/v2/cek-senetler", response_model=CekSenetRead, status_code=201, tags=["Çek/Senet"])
def cek_senet_olustur(payload: CekSenetCreate, db: Session = Depends(get_db)):
    obj = CekSenet(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v2/cek-senetler/{id}", response_model=CekSenetRead, tags=["Çek/Senet"])
def cek_senet_guncelle(id: int, payload: CekSenetCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, CekSenet, id)
    for k, v in payload.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/cek-senetler/{id}", tags=["Çek/Senet"])
def cek_senet_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, CekSenet, id); db.delete(obj); db.commit()  # Değişiklikleri veritabanına kalıcı olarak yaz
    return {"ok": True, "mesaj": "Çek/Senet silindi"}


# ════════════════════════════════════════════════════════════
#  TAKSİT PLANI  /api/v2/taksitler
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/taksitler", response_model=List[TaksitPlanRead], tags=["Taksit"])
def taksitler_listele(belge_id: Optional[int] = Query(None), odendi: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(TaksitPlan)  # Sorgu başlat
    if belge_id: q = q.filter_by(belge_id=belge_id)  # Filtrele
    if odendi is not None: q = q.filter(TaksitPlan.odendi == odendi)  # Koşullu filtrele
    return q.order_by(TaksitPlan.vade_tarihi).all()

@app.post("/api/v2/taksitler", response_model=TaksitPlanRead, status_code=201, tags=["Taksit"])
def taksit_olustur(payload: TaksitPlanCreate, db: Session = Depends(get_db)):
    obj = TaksitPlan(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v2/taksitler/{id}/odendi", tags=["Taksit"])
def taksit_odendi_isaretle(id: int, odeme_tarihi: Optional[date] = Query(None), db: Session = Depends(get_db)):
    obj = get_or_404(db, TaksitPlan, id)
    obj.odendi = True; obj.odeme_tarihi = odeme_tarihi or date.today()  # Bugünün tarihi
    db.commit(); return {"ok": True, "taksit_id": id, "odeme_tarihi": str(obj.odeme_tarihi)}  # Değişiklikleri veritabanına kalıcı olarak yaz

@app.delete("/api/v2/taksitler/{id}", tags=["Taksit"])
def taksit_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, TaksitPlan, id); db.delete(obj); db.commit()  # Değişiklikleri veritabanına kalıcı olarak yaz
    return {"ok": True, "mesaj": "Taksit silindi"}


# ════════════════════════════════════════════════════════════
#  HESAP GRUBU  /api/v2/hesap-gruplari
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/hesap-gruplari", response_model=List[HesapGrubuRead], tags=["Hesap Grubu"])
def hesap_gruplari_listele(
    tip: Optional[str] = Query(None, description="CARI | STOK"),
    seviye: Optional[int] = Query(None),
    parent_id: Optional[int] = Query(None),
    aktif: Optional[bool] = Query(None),
    db: Session = Depends(get_db)  # DB oturumu dependency injection ile enjekte edilir
):
    q = db.query(HesapGrubu)  # Sorgu başlat
    if tip: q = q.filter_by(tip=tip.upper())  # Filtrele
    if seviye is not None: q = q.filter_by(seviye=seviye)  # Filtrele
    if parent_id is not None: q = q.filter_by(parent_id=parent_id)  # Filtrele
    if aktif is not None: q = q.filter(HesapGrubu.aktif == aktif)  # Koşullu filtrele
    return q.order_by(HesapGrubu.seviye, HesapGrubu.kod).all()

@app.get("/api/v2/hesap-gruplari/{id}", response_model=HesapGrubuRead, tags=["Hesap Grubu"])
def hesap_grubu_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, HesapGrubu, id)

@app.post("/api/v2/hesap-gruplari", response_model=HesapGrubuRead, status_code=201, tags=["Hesap Grubu"])
def hesap_grubu_olustur(payload: HesapGrubuCreate, db: Session = Depends(get_db)):
    obj = HesapGrubu(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v2/hesap-gruplari/{id}", response_model=HesapGrubuRead, tags=["Hesap Grubu"])
def hesap_grubu_guncelle(id: int, payload: HesapGrubuCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, HesapGrubu, id)
    for k, v in payload.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/hesap-gruplari/{id}", tags=["Hesap Grubu"])
def hesap_grubu_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, HesapGrubu, id); obj.aktif = False; db.commit()  # Soft delete: fiziksel silme yerine pasife al
    return {"ok": True, "mesaj": "Hesap grubu pasife alındı"}


# ════════════════════════════════════════════════════════════
#  RAPOR  /api/v2/raporlar
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/raporlar", response_model=List[RaporRead], tags=["Rapor"])
def raporlar_listele(kategori: Optional[str] = Query(None), aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Rapor)  # Sorgu başlat
    if kategori: q = q.filter_by(kategori=kategori)  # Filtrele
    if aktif is not None: q = q.filter(Rapor.aktif == aktif)  # Koşullu filtrele
    return q.order_by(Rapor.kategori, Rapor.ad).all()

@app.get("/api/v2/raporlar/{id}", response_model=RaporRead, tags=["Rapor"])
def rapor_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Rapor, id)

@app.post("/api/v2/raporlar", response_model=RaporRead, status_code=201, tags=["Rapor"])
def rapor_olustur(payload: RaporCreate, db: Session = Depends(get_db)):
    obj = Rapor(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/raporlar/{id}", tags=["Rapor"])
def rapor_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, Rapor, id); obj.aktif = False; db.commit()  # Soft delete: fiziksel silme yerine pasife al
    return {"ok": True, "mesaj": "Rapor pasife alındı"}

@app.get("/api/v2/raporlar/{id}/calistir", tags=["Rapor"])
def rapor_calistir(id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text  # Ham SQL çalıştırmak için text() sarmalayıcısı
    rapor = get_or_404(db, Rapor, id)
    sql = rapor.sql_sorgu.strip()
    if not sql.upper().startswith("SELECT"):
        raise HTTPException(422, "Sadece SELECT sorguları çalıştırılabilir")
    for yasak in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]:
        if yasak in sql.upper():
            raise HTTPException(422, f"'{yasak}' komutu izin verilmiyor")
    try:
        sonuc = db.execute(text(sql))  # Ham SQL sorgusunu çalıştır
        kolonlar = list(sonuc.keys())  # Sonuç kolon adlarını al
        satirlar = [dict(zip(kolonlar, row)) for row in sonuc.fetchall()]  # Tüm satırları belleğe al
        return {"kolonlar": kolonlar, "satirlar": satirlar, "satir_sayisi": len(satirlar)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ════════════════════════════════════════════════════════════
#  ADRES REFERANSLARI  /api/v2/adres
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/adres/ulkeler", response_model=List[UlkeRead], tags=["Adres"])
def ulkeler_listele(db: Session = Depends(get_db)):
    return db.query(Ulke).filter_by(aktif=True).order_by(Ulke.ad).all()

@app.get("/api/v2/adres/iller", response_model=List[IlRead], tags=["Adres"])
def iller_listele(ulke_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Il).filter_by(aktif=True)  # Filtrele
    if ulke_id: q = q.filter_by(ulke_id=ulke_id)  # Filtrele
    return q.order_by(Il.ad).all()

@app.get("/api/v2/adres/ilceler", response_model=List[IlceRead], tags=["Adres"])
def ilceler_listele(il_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Ilce).filter_by(aktif=True)  # Filtrele
    if il_id: q = q.filter_by(il_id=il_id)  # Filtrele
    return q.order_by(Ilce.ad).all()

@app.get("/api/v2/adres/mahalleler", response_model=List[MahalleRead], tags=["Adres"])
def mahalleler_listele(ilce_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Mahalle).filter_by(aktif=True)  # Filtrele
    if ilce_id: q = q.filter_by(ilce_id=ilce_id)  # Filtrele
    return q.order_by(Mahalle.ad).all()


# ════════════════════════════════════════════════════════════
#  CARİ ADRES  /api/v2/cari-adresler
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/cari-adresler", response_model=List[CariAdresRead], tags=["Cari Adres"])
def cari_adresler_listele(cari_id: Optional[int] = Query(None), aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(CariAdres)  # Sorgu başlat
    if cari_id: q = q.filter_by(cari_id=cari_id)  # Filtrele
    if aktif is not None: q = q.filter(CariAdres.aktif == aktif)  # Koşullu filtrele
    return q.all()

@app.post("/api/v2/cari-adresler", response_model=CariAdresRead, status_code=201, tags=["Cari Adres"])
def cari_adres_olustur(payload: CariAdresCreate, db: Session = Depends(get_db)):
    obj = CariAdres(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v2/cari-adresler/{id}", response_model=CariAdresRead, tags=["Cari Adres"])
def cari_adres_guncelle(id: int, payload: CariAdresCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, CariAdres, id)
    for k, v in payload.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/cari-adresler/{id}", tags=["Cari Adres"])
def cari_adres_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, CariAdres, id); obj.aktif = False; db.commit()  # Soft delete: fiziksel silme yerine pasife al
    return {"ok": True, "mesaj": "Adres pasife alındı"}


# ════════════════════════════════════════════════════════════
#  CARİ İLETİŞİM  /api/v2/cari-iletisimler
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/cari-iletisimler", response_model=List[CariIletisimRead], tags=["Cari İletişim"])
def cari_iletisimler_listele(cari_id: Optional[int] = Query(None), aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(CariIletisim)  # Sorgu başlat
    if cari_id: q = q.filter_by(cari_id=cari_id)  # Filtrele
    if aktif is not None: q = q.filter(CariIletisim.aktif == aktif)  # Koşullu filtrele
    return q.all()

@app.post("/api/v2/cari-iletisimler", response_model=CariIletisimRead, status_code=201, tags=["Cari İletişim"])
def cari_iletisim_olustur(payload: CariIletisimCreate, db: Session = Depends(get_db)):
    obj = CariIletisim(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/cari-iletisimler/{id}", tags=["Cari İletişim"])
def cari_iletisim_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, CariIletisim, id); obj.aktif = False; db.commit()  # Soft delete: fiziksel silme yerine pasife al
    return {"ok": True, "mesaj": "İletişim bilgisi pasife alındı"}


# ════════════════════════════════════════════════════════════
#  CARİ BANKA HESABI  /api/v2/cari-banka-hesaplari
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/cari-banka-hesaplari", response_model=List[CariBankaHesapRead], tags=["Cari Banka"])
def cari_banka_hesaplari_listele(cari_id: Optional[int] = Query(None), aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(CariBankaHesap)  # Sorgu başlat
    if cari_id: q = q.filter_by(cari_id=cari_id)  # Filtrele
    if aktif is not None: q = q.filter(CariBankaHesap.aktif == aktif)  # Koşullu filtrele
    return q.all()

@app.post("/api/v2/cari-banka-hesaplari", response_model=CariBankaHesapRead, status_code=201, tags=["Cari Banka"])
def cari_banka_hesap_olustur(payload: CariBankaHesapCreate, db: Session = Depends(get_db)):
    obj = CariBankaHesap(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v2/cari-banka-hesaplari/{id}", tags=["Cari Banka"])
def cari_banka_hesap_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, CariBankaHesap, id); obj.aktif = False; db.commit()  # Soft delete: fiziksel silme yerine pasife al
    return {"ok": True, "mesaj": "Banka hesabı pasife alındı"}


# ════════════════════════════════════════════════════════════
#  KULLANICI  /api/v2/kullanicilar
# ════════════════════════════════════════════════════════════

@app.get("/api/v2/kullanicilar", response_model=List[KullaniciRead], tags=["Kullanıcı"])
def kullanicilar_listele(aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Kullanici)  # Sorgu başlat
    if aktif is not None: q = q.filter(Kullanici.aktif == aktif)  # Koşullu filtrele
    return q.order_by(Kullanici.ad_soyad).all()

@app.get("/api/v2/kullanicilar/{id}", response_model=KullaniciRead, tags=["Kullanıcı"])
def kullanici_getir(id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Kullanici, id)

@app.delete("/api/v2/kullanicilar/{id}", tags=["Kullanıcı"])
def kullanici_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, Kullanici, id); obj.aktif = False; db.commit()  # Soft delete: fiziksel silme yerine pasife al
    return {"ok": True, "mesaj": "Kullanıcı devre dışı bırakıldı"}

@app.get("/api/v2/kullanicilar/{id}/yetkiler", tags=["Kullanıcı"])
def kullanici_yetkiler(id: int, db: Session = Depends(get_db)):
    get_or_404(db, Kullanici, id)
    sirket = [y.sirket_id for y in db.query(KullaniciSirketYetki).filter_by(kullanici_id=id).all()]
    depo   = [y.depo_id   for y in db.query(KullaniciDepoYetki).filter_by(kullanici_id=id).all()]
    belge  = [{"belge_tip": y.belge_tip, "cari_tip": y.cari_tip, "yazma": y.yazma}
              for y in db.query(KullaniciBelgeYetki).filter_by(kullanici_id=id).all()]
    return {"kullanici_id": id, "sirket_yetkileri": sirket, "depo_yetkileri": depo, "belge_yetkileri": belge}


# ════════════════════════════════════════════════════════════
#  v1 ENDPOINT'LERİ (geriye dönük uyum)
# ════════════════════════════════════════════════════════════

@app.get("/api/v1/birim-gruplari", response_model=List[BirimGrubuRead], tags=["v1 - Birim"])
def bg_listele(aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(BirimGrubu)  # Sorgu başlat
    if aktif is not None: q = q.filter(BirimGrubu.aktif == aktif)  # Koşullu filtrele
    return q.order_by(BirimGrubu.ad).all()

@app.get("/api/v1/birim-gruplari/{id}", response_model=BirimGrubuRead, tags=["v1 - Birim"])
def bg_getir(id: int, db: Session = Depends(get_db)): return get_or_404(db, BirimGrubu, id)

@app.post("/api/v1/birim-gruplari", response_model=BirimGrubuRead, status_code=201, tags=["v1 - Birim"])
def bg_olustur(p: BirimGrubuCreate, db: Session = Depends(get_db)):
    obj = BirimGrubu(**p.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v1/birim-gruplari/{id}", response_model=BirimGrubuRead, tags=["v1 - Birim"])
def bg_guncelle(id: int, p: BirimGrubuCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, BirimGrubu, id)
    for k, v in p.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v1/birim-gruplari/{id}", tags=["v1 - Birim"])
def bg_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, BirimGrubu, id); obj.aktif = False; db.commit(); return {"ok": True}  # Soft delete: fiziksel silme yerine pasife al

@app.get("/api/v1/birimler", response_model=List[BirimRead], tags=["v1 - Birim"])
def b_listele(grup_id: Optional[int] = Query(None), aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Birim)  # Sorgu başlat
    if grup_id: q = q.filter_by(grup_id=grup_id)  # Filtrele
    if aktif is not None: q = q.filter(Birim.aktif == aktif)  # Koşullu filtrele
    return q.order_by(Birim.kod).all()

@app.get("/api/v1/birimler/{id}", response_model=BirimRead, tags=["v1 - Birim"])
def b_getir(id: int, db: Session = Depends(get_db)): return get_or_404(db, Birim, id)

@app.post("/api/v1/birimler", response_model=BirimRead, status_code=201, tags=["v1 - Birim"])
def b_olustur(p: BirimCreate, db: Session = Depends(get_db)):
    obj = Birim(**p.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v1/birimler/{id}", response_model=BirimRead, tags=["v1 - Birim"])
def b_guncelle(id: int, p: BirimCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, Birim, id)
    for k, v in p.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v1/birimler/{id}", tags=["v1 - Birim"])
def b_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, Birim, id); obj.aktif = False; db.commit(); return {"ok": True}  # Soft delete: fiziksel silme yerine pasife al

@app.get("/api/v1/birim-donusumleri", response_model=List[BirimDonusumRead], tags=["v1 - Birim"])
def bd_listele(aktif: Optional[bool] = Query(None), db: Session = Depends(get_db)):
    q = db.query(BirimDonusum)  # Sorgu başlat
    if aktif is not None: q = q.filter(BirimDonusum.aktif == aktif)  # Koşullu filtrele
    return q.all()

@app.post("/api/v1/birim-donusumleri", response_model=BirimDonusumRead, status_code=201, tags=["v1 - Birim"])
def bd_olustur(p: BirimDonusumCreate, db: Session = Depends(get_db)):
    obj = BirimDonusum(**p.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.get("/api/v1/birim-cevirme", tags=["v1 - Birim"])
def birim_cevirme(kaynak_id: int, hedef_id: int, miktar: float = 1.0, db: Session = Depends(get_db)):
    if kaynak_id == hedef_id:
        return {"ok": True, "katsayi": 1.0, "sonuc": round(miktar, 6)}
    kaynak = db.get(Birim, kaynak_id); hedef = db.get(Birim, hedef_id)
    if not kaynak or not hedef:
        raise HTTPException(404, "Birim bulunamadı")
    ozel = db.query(BirimDonusum).filter_by(kaynak_birim_id=kaynak_id, hedef_birim_id=hedef_id, aktif=True).first()
    if ozel:
        k = float(ozel.carpan); return {"ok": True, "katsayi": k, "sonuc": round(miktar * k, 6)}  # Ondalık hassasiyeti 2 basamakla sınırla
    ters = db.query(BirimDonusum).filter_by(kaynak_birim_id=hedef_id, hedef_birim_id=kaynak_id, aktif=True).first()
    if ters:
        k = 1.0 / float(ters.carpan); return {"ok": True, "katsayi": k, "sonuc": round(miktar * k, 6)}  # Ondalık hassasiyeti 2 basamakla sınırla
    if kaynak.grup_id == hedef.grup_id:
        k = float(kaynak.katsayi) / float(hedef.katsayi)
        return {"ok": True, "katsayi": k, "sonuc": round(miktar * k, 6)}
    raise HTTPException(422, "Bu birimler arasında çevrim tanımlı değil")

@app.get("/api/v1/cariler", response_model=List[CariRead], tags=["v1 - Cari"])
def c_listele(tip: Optional[str] = Query(None), aktif: Optional[bool] = Query(None), sehir: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Cari)  # Sorgu başlat
    if aktif is not None: q = q.filter(Cari.aktif == aktif)  # Koşullu filtrele
    if tip: q = q.filter(Cari.tip.in_([tip, "HER_IKISI"]))  # Koşullu filtrele
    if sehir: q = q.filter(Cari.sehir.ilike(f"%{sehir}%"))  # Koşullu filtrele
    return q.order_by(Cari.unvan).all()

@app.get("/api/v1/cariler/{id}", response_model=CariRead, tags=["v1 - Cari"])
def c_getir(id: int, db: Session = Depends(get_db)): return get_or_404(db, Cari, id)

@app.get("/api/v1/cariler/{id}/bakiye", tags=["v1 - Cari"])
def c_bakiye(id: int, db: Session = Depends(get_db)):
    if not db.get(Cari, id): raise HTTPException(404, "Cari bulunamadı")  # Kayıt bulunamadı → 404 Not Found
    borc   = float(db.query(func.sum(CariHareket.tutar)).filter_by(cari_id=id, hareket_tipi="BORC").scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    alacak = float(db.query(func.sum(CariHareket.tutar)).filter_by(cari_id=id, hareket_tipi="ALACAK").scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    return {"cari_id": id, "borc": borc, "alacak": alacak, "bakiye": borc - alacak}

@app.post("/api/v1/cariler", response_model=CariRead, status_code=201, tags=["v1 - Cari"])
def c_olustur(p: CariCreate, db: Session = Depends(get_db)):
    obj = Cari(**p.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v1/cariler/{id}", response_model=CariRead, tags=["v1 - Cari"])
def c_guncelle(id: int, p: CariCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, Cari, id)
    for k, v in p.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v1/cariler/{id}", tags=["v1 - Cari"])
def c_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, Cari, id); obj.aktif = False; db.commit(); return {"ok": True}  # Soft delete: fiziksel silme yerine pasife al

@app.get("/api/v1/cari-hareketler", response_model=List[CariHareketRead], tags=["v1 - Cari"])
def ch_listele(cari_id: Optional[int]=Query(None), hareket_tipi: Optional[str]=Query(None), tarih_baslangic: Optional[date]=Query(None), tarih_bitis: Optional[date]=Query(None), db: Session=Depends(get_db)):
    q = db.query(CariHareket)  # Sorgu başlat
    if cari_id: q = q.filter_by(cari_id=cari_id)  # Filtrele
    if hareket_tipi: q = q.filter_by(hareket_tipi=hareket_tipi)  # Filtrele
    if tarih_baslangic: q = q.filter(CariHareket.tarih >= tarih_baslangic)  # Koşullu filtrele
    if tarih_bitis: q = q.filter(CariHareket.tarih <= tarih_bitis)  # Koşullu filtrele
    return q.order_by(CariHareket.tarih.desc()).all()

@app.post("/api/v1/cari-hareketler", response_model=CariHareketRead, status_code=201, tags=["v1 - Cari"])
def ch_olustur(p: CariHareketCreate, db: Session = Depends(get_db)):
    obj = CariHareket(**p.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v1/cari-hareketler/{id}", tags=["v1 - Cari"])
def ch_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, CariHareket, id); db.delete(obj); db.commit(); return {"ok": True}  # Değişiklikleri veritabanına kalıcı olarak yaz

@app.get("/api/v1/stoklar", response_model=List[StokKartiRead], tags=["v1 - Stok"])
def s_listele(tip: Optional[str]=Query(None), aktif: Optional[bool]=Query(None), db: Session=Depends(get_db)):
    q = db.query(StokKarti)  # Sorgu başlat
    if tip: q = q.filter_by(tip=tip)  # Filtrele
    if aktif is not None: q = q.filter(StokKarti.aktif == aktif)  # Koşullu filtrele
    return q.order_by(StokKarti.ad).all()

@app.get("/api/v1/stoklar/{id}", response_model=StokKartiRead, tags=["v1 - Stok"])
def s_getir(id: int, db: Session = Depends(get_db)): return get_or_404(db, StokKarti, id)

@app.get("/api/v1/stoklar/{id}/miktar", tags=["v1 - Stok"])
def s_miktar(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, StokKarti, id)
    if obj.tip == "HIZMET": return {"stok_id": id, "tip": "HIZMET", "miktar": None}
    giris = float(db.query(func.sum(StokHareket.miktar)).filter_by(stok_id=id, hareket_tipi="GIRIS").scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    cikis = float(db.query(func.sum(StokHareket.miktar)).filter_by(stok_id=id, hareket_tipi="CIKIS").scalar() or 0)  # Tek değer döndür (toplam, sayı vb.)
    return {"stok_id": id, "tip": "MALZEME", "miktar": giris - cikis}

@app.post("/api/v1/stoklar", response_model=StokKartiRead, status_code=201, tags=["v1 - Stok"])
def s_olustur(p: StokKartiCreate, db: Session = Depends(get_db)):
    obj = StokKarti(**p.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.put("/api/v1/stoklar/{id}", response_model=StokKartiRead, tags=["v1 - Stok"])
def s_guncelle(id: int, p: StokKartiCreate, db: Session = Depends(get_db)):
    obj = get_or_404(db, StokKarti, id)
    for k, v in p.model_dump().items(): setattr(obj, k, v)  # Alan değerini güncelle
    db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v1/stoklar/{id}", tags=["v1 - Stok"])
def s_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, StokKarti, id); obj.aktif = False; db.commit(); return {"ok": True}  # Soft delete: fiziksel silme yerine pasife al

@app.get("/api/v1/stok-hareketler", response_model=List[StokHareketRead], tags=["v1 - Stok"])
def sh_listele(stok_id: Optional[int]=Query(None), hareket_tipi: Optional[str]=Query(None), tarih_baslangic: Optional[date]=Query(None), tarih_bitis: Optional[date]=Query(None), db: Session=Depends(get_db)):
    q = db.query(StokHareket)  # Sorgu başlat
    if stok_id: q = q.filter_by(stok_id=stok_id)  # Filtrele
    if hareket_tipi: q = q.filter_by(hareket_tipi=hareket_tipi)  # Filtrele
    if tarih_baslangic: q = q.filter(StokHareket.tarih >= tarih_baslangic)  # Koşullu filtrele
    if tarih_bitis: q = q.filter(StokHareket.tarih <= tarih_bitis)  # Koşullu filtrele
    return q.order_by(StokHareket.tarih.desc()).all()

@app.post("/api/v1/stok-hareketler", response_model=StokHareketRead, status_code=201, tags=["v1 - Stok"])
def sh_olustur(p: StokHareketCreate, db: Session = Depends(get_db)):
    obj = StokHareket(**p.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj  # Veritabanından güncel veriyi yükle (id, tarih vb.)

@app.delete("/api/v1/stok-hareketler/{id}", tags=["v1 - Stok"])
def sh_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, StokHareket, id); db.delete(obj); db.commit(); return {"ok": True}  # Değişiklikleri veritabanına kalıcı olarak yaz

@app.get("/api/v1/belgeler", tags=["v1 - Belge"])
def bel_listele(belge_tip: Optional[str]=Query(None), cari_tip: Optional[str]=Query(None), durum: Optional[str]=Query(None), cari_id: Optional[int]=Query(None), sirket_id: Optional[int]=Query(None), tarih_baslangic: Optional[date]=Query(None), tarih_bitis: Optional[date]=Query(None), limit: int=Query(100, le=500), db: Session=Depends(get_db)):
    q = db.query(BelgeBaslik)  # Sorgu başlat
    if belge_tip: q = q.filter_by(belge_tip=belge_tip.upper())  # Filtrele
    if cari_tip: q = q.filter_by(cari_tip=cari_tip.upper())  # Filtrele
    if durum: q = q.filter_by(durum=durum.upper())  # Filtrele
    if cari_id: q = q.filter_by(cari_id=cari_id)  # Filtrele
    if sirket_id: q = q.filter_by(sirket_id=sirket_id)  # Filtrele
    if tarih_baslangic: q = q.filter(BelgeBaslik.tarih >= tarih_baslangic)  # Koşullu filtrele
    if tarih_bitis: q = q.filter(BelgeBaslik.tarih <= tarih_bitis)  # Koşullu filtrele
    return [BelgeBaslikRead.from_orm_obj(b) for b in q.order_by(BelgeBaslik.tarih.desc()).limit(limit).all()]

@app.get("/api/v1/belgeler/{id}", tags=["v1 - Belge"])
def bel_getir(id: int, db: Session = Depends(get_db)):
    return BelgeBaslikRead.from_orm_obj(get_or_404(db, BelgeBaslik, id))

@app.post("/api/v1/belgeler", status_code=201, tags=["v1 - Belge"])
def bel_olustur(p: BelgeBaslikCreate, db: Session = Depends(get_db)):
    data = p.model_dump(exclude={"satirlar"})  # Pydantic → dict dönüşümü
    baslik = BelgeBaslik(**data); db.add(baslik); db.flush()  # Commit olmadan oturumu senkronize et (ID almak için)
    for s in p.satirlar:
        db.add(BelgeSatir(baslik_id=baslik.id, **s.model_dump()))  # Oturuma ekle
    db.commit(); db.refresh(baslik); return BelgeBaslikRead.from_orm_obj(baslik)  # Değişiklikleri veritabanına kalıcı olarak yaz

@app.put("/api/v1/belgeler/{id}", tags=["v1 - Belge"])
def bel_guncelle(id: int, p: BelgeBaslikCreate, db: Session = Depends(get_db)):
    baslik = get_or_404(db, BelgeBaslik, id)
    for k, v in p.model_dump(exclude={"satirlar"}).items(): setattr(baslik, k, v)  # Pydantic → dict dönüşümü
    db.query(BelgeSatir).filter_by(baslik_id=id).delete(); db.flush()  # Commit olmadan oturumu senkronize et (ID almak için)
    for s in p.satirlar:
        db.add(BelgeSatir(baslik_id=id, **s.model_dump()))  # Oturuma ekle
    db.commit(); db.refresh(baslik); return BelgeBaslikRead.from_orm_obj(baslik)  # Değişiklikleri veritabanına kalıcı olarak yaz

@app.delete("/api/v1/belgeler/{id}", tags=["v1 - Belge"])
def bel_sil(id: int, db: Session = Depends(get_db)):
    obj = get_or_404(db, BelgeBaslik, id)
    db.query(CariHareket).filter_by(kaynak_tip="FATURA", kaynak_id=id).delete()
    db.query(StokHareket).filter(StokHareket.belge_no == obj.belge_no).delete()
    db.delete(obj); db.commit(); return {"ok": True}  # Değişiklikleri veritabanına kalıcı olarak yaz

@app.get("/api/v1/belge-satirlari", response_model=List[BelgeSatirRead], tags=["v1 - Belge"])
def bsat_listele(baslik_id: Optional[int]=Query(None), stok_id: Optional[int]=Query(None), db: Session=Depends(get_db)):
    q = db.query(BelgeSatir)  # Sorgu başlat
    if baslik_id: q = q.filter_by(baslik_id=baslik_id)  # Filtrele
    if stok_id: q = q.filter_by(stok_id=stok_id)  # Filtrele
    return q.order_by(BelgeSatir.baslik_id, BelgeSatir.sira_no).all()

@app.get("/api/v1/ozet", tags=["v1 - Genel"])
def ozet_v1(db: Session = Depends(get_db)):
    """[v1] Temel dashboard istatistikleri (şirket filtresi yok, v2/ozet kullanın)."""
    return {
        "cari_sayisi":  db.query(func.count(Cari.id)).filter_by(aktif=True).scalar(),  # Tek değer döndür (toplam, sayı vb.)
        "stok_sayisi":  db.query(func.count(StokKarti.id)).filter_by(aktif=True).scalar(),  # Tek değer döndür (toplam, sayı vb.)
        "birim_sayisi": db.query(func.count(Birim.id)).filter_by(aktif=True).scalar(),  # Tek değer döndür (toplam, sayı vb.)
        "acik_fatura":  db.query(func.count(BelgeBaslik.id)).filter_by(belge_tip="FATURA", durum="ACIK").scalar(),  # Tek değer döndür (toplam, sayı vb.)
        "acik_siparis": db.query(func.count(BelgeBaslik.id)).filter_by(belge_tip="SIPARIS", durum="ACIK").scalar(),  # Tek değer döndür (toplam, sayı vb.)
    }


# ════════════════════════════════════════════════════════════
#  API YETKİ TABLOSU
#  Her API kaynağının (web arayüzü, mobil, entegrasyon)
#  bağımsız kimlik ve konfigürasyon bilgisi.
#  SECRET_KEY kod içinde sabit olmaz — DB'den yönetilir.
# ════════════════════════════════════════════════════════════

class ApiYetki(Base):
    """
    API erişim kaynakları tablosu.

    Her kaynak (web arayüzü, mobil uygulama, 3. parti entegrasyon)
    kendi api_key ve secret_key'ine sahiptir:
      - api_key   → istemcinin login isteğinde gönderdiği tanımlayıcı
      - secret_key→ JWT'lerin imzalandığı gizli anahtar (DB dışına çıkmaz)

    Bu tasarımın avantajları:
      ✓ Bir kaynak sızdırılsa diğerleri güvende kalır
      ✓ Anlık iptal: aktif=False → tüm mevcut token'lar geçersiz
      ✓ Kaynak bazlı token süresi (web=8h, mobil=24h)
      ✓ Rol kısıtı: mobil kaynak ADMIN token veremez
      ✓ IP kısıtı: sadece belirli sunuculardan erişim
      ✓ son_kullanim takibi: hangi kaynak ne zaman kullandı
    """
    __tablename__ = 'api_yetki'  # MySQL'deki tablo adı
    id                  = Column(Integer, primary_key=True, autoincrement=True)  # DB sütunu
    ad                  = Column(String(100), unique=True, nullable=False)  # DB sütunu
    # Kaynak tanımlayıcı adı (Web Arayüzü, Mobil Uygulama, Muhasebe Entegrasyonu...)

    api_key             = Column(String(64), unique=True, nullable=False)  # DB sütunu
    # İstemcinin X-API-Key header'ında göndereceği anahtar.
    # secrets.token_urlsafe(32) ile üretilir → 43 karakter URL-güvenli rastgele dize.

    secret_key          = Column(String(256), nullable=False)  # DB sütunu
    # JWT imzalamak için kullanılan gizli anahtar.
    # secrets.token_hex(32) ile üretilir → 64 karakter hex dize.
    # API yanıtında HİÇBİR ZAMAN döndürülmez.

    token_sure          = Column(Integer, default=8, nullable=False)  # DB sütunu
    # Bu kaynaktan login olan kullanıcının token geçerlilik süresi (saat).
    # Web: 8, Mobil: 24, Entegrasyon: 1

    izin_verilen_roller = Column(String(200), default='STANDART,SADECE_OKUMA')  # DB sütunu
    # Virgülle ayrılmış izinli rol listesi.
    # Örnek: 'ADMIN,STANDART,SADECE_OKUMA' veya yalnızca 'SADECE_OKUMA'
    # Kullanıcının rolü bu listede yoksa login reddedilir.

    ip_listesi          = Column(Text)  # DB sütunu
    # Virgülle ayrılmış izinli IP adresleri. Boş = kısıtlama yok.
    # Örnek: '192.168.1.10,10.0.0.5'
    # Sunucu entegrasyonları için mutlaka doldurun.

    aktif               = Column(Boolean, default=True, nullable=False)  # DB sütunu
    # False → bu kaynaktan hiçbir login kabul edilmez.
    # Mevcut token'lar bir sonraki istekte geçersiz sayılır.

    olusturma_tarihi    = Column(DateTime, default=datetime.now)  # DB sütunu
    son_kullanim        = Column(DateTime)  # DB sütunu
    # Son başarılı login zamanı. Kullanılmayan kaynakları tespit etmek için.

    aciklama            = Column(Text)  # DB sütunu
    # Kaynağın amacı, bağlanan uygulama, sorumlu ekip vb.


# ── ApiYetki Pydantic Şemaları ───────────────────────────────

class ApiYetkiCreate(BaseModel):
    """
    Yeni API kaynağı oluşturma şeması.
    api_key ve secret_key otomatik üretilir — bu şemada gönderilmez.
    POST yanıtında api_key bir kez görünür; sonraki GET'lerde gizlenir.
    """
    ad: str                         # Benzersiz kaynak adı
    token_sure: int = 8             # Token geçerlilik süresi (saat)
    izin_verilen_roller: str = 'STANDART,SADECE_OKUMA'  # Virgülle ayrılmış roller
    ip_listesi: Optional[str] = None    # Boş = IP kısıtı yok
    aciklama: Optional[str] = None  # Ek açıklama
    aktif: bool = True  # False = pasif/silindi


class ApiYetkiRead(BaseModel):
    """
    GET yanıtı. secret_key bu şemada YOK — veritabanından okunsa bile döndürülmez.
    api_key yalnızca oluşturma anında (POST yanıtında) görünür.
    """
    id: int
    ad: str  # Ad/başlık
    api_key: str                    # İstemciye verilecek anahtar
    token_sure: int
    izin_verilen_roller: str
    ip_listesi: Optional[str] = None  # Boş=kısıt yok | '192.168.1.1,10.0.0.5'
    aktif: bool  # Aktif mi?
    olusturma_tarihi: Optional[datetime] = None  # Kayıt oluşturma zamanı
    son_kullanim: Optional[datetime] = None  # Son başarılı login zamanı
    aciklama: Optional[str] = None  # Ek açıklama
    class Config:
        from_attributes = True      # ORM nesnesinden otomatik doldurma


class ApiYetkiGuncelle(BaseModel):
    """
    Kısmi güncelleme şeması. Yalnızca gönderilen alanlar güncellenir.
    api_key ve secret_key bu yolla değiştirilemez → /rotate endpoint'ini kullanın.
    """
    ad: Optional[str] = None
    token_sure: Optional[int] = None
    izin_verilen_roller: Optional[str] = None
    ip_listesi: Optional[str] = None  # Boş=kısıt yok | '192.168.1.1,10.0.0.5'
    aciklama: Optional[str] = None  # Ek açıklama
    aktif: Optional[bool] = None


# ── ApiYetki Endpoint'leri ───────────────────────────────────

@app.get("/api/v2/api-yetkiler", response_model=List[ApiYetkiRead], tags=["API Yetki"])
def api_yetkiler_listele(
    aktif: Optional[bool] = Query(None),
    db: Session = Depends(get_db),  # DB oturumu dependency injection ile enjekte edilir
    # k = Depends(admin_gerekli)  ← auth.py entegre edilince aktif edin
):
    """
    Tüm API kaynaklarını listeler.
    secret_key yanıtta yer almaz — yalnızca ad, api_key ve yapılandırma döner.
    Sadece ADMIN erişebilmeli (auth.py hazır olunca admin_gerekli ekleyin).
    """
    q = db.query(ApiYetki)  # Sorgu başlat
    if aktif is not None:
        q = q.filter(ApiYetki.aktif == aktif)  # Koşullu filtrele
    return q.order_by(ApiYetki.ad).all()


@app.get("/api/v2/api-yetkiler/{id}", response_model=ApiYetkiRead, tags=["API Yetki"])
def api_yetki_getir(id: int, db: Session = Depends(get_db)):
    """Tek API kaynağını getirir. secret_key döndürülmez."""
    return get_or_404(db, ApiYetki, id)


@app.post("/api/v2/api-yetkiler", response_model=ApiYetkiRead, status_code=201, tags=["API Yetki"])
def api_yetki_olustur(
    payload: ApiYetkiCreate,
    db: Session = Depends(get_db),  # DB oturumu dependency injection ile enjekte edilir
    # k = Depends(admin_gerekli)
):
    """
    Yeni API kaynağı oluşturur.

    api_key ve secret_key bu endpoint tarafından otomatik üretilir:
      api_key   → secrets.token_urlsafe(32)  — 43 karakter, URL güvenli
      secret_key→ secrets.token_hex(32)      — 64 karakter hex

    UYARI: api_key bu yanıtta bir kez görünür.
    Sonraki GET isteklerinde api_key hâlâ görünür ama secret_key asla dönmez.
    api_key'i güvenli bir yerde saklayın.
    """
    obj = ApiYetki(
        ad=payload.ad,
        api_key=secrets.token_urlsafe(32),   # URL-güvenli rastgele anahtar
        secret_key=secrets.token_hex(32),    # JWT imzalama gizli anahtarı
        token_sure=payload.token_sure,
        izin_verilen_roller=payload.izin_verilen_roller,
        ip_listesi=payload.ip_listesi,
        aciklama=payload.aciklama,
        aktif=payload.aktif,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)  # Veritabanından güncel veriyi yükle (id, tarih vb.)
    return obj


@app.put("/api/v2/api-yetkiler/{id}", response_model=ApiYetkiRead, tags=["API Yetki"])
def api_yetki_guncelle(
    id: int,
    payload: ApiYetkiGuncelle,
    db: Session = Depends(get_db),  # DB oturumu dependency injection ile enjekte edilir
):
    """
    API kaynağını günceller. Yalnızca gönderilen alanlar değişir (PATCH mantığı).
    api_key ve secret_key bu endpoint'ten değiştirilemez.
    Anahtar yenilemek için /rotate endpoint'ini kullanın.
    """
    obj = get_or_404(db, ApiYetki, id)
    for k, v in payload.model_dump(exclude_none=True).items():  # Pydantic → dict dönüşümü
        setattr(obj, k, v)   # Sadece None olmayan alanları güncelle
    db.commit()
    db.refresh(obj)  # Veritabanından güncel veriyi yükle (id, tarih vb.)
    return obj


@app.post("/api/v2/api-yetkiler/{id}/rotate", response_model=ApiYetkiRead, tags=["API Yetki"])
def api_key_rotate(id: int, db: Session = Depends(get_db)):
    """
    api_key ve secret_key'i döndürür (rotate eder).

    Ne zaman kullanılır:
      - Güvenlik ihlali şüphesi (api_key sızdı, yetkisiz erişim tespit edildi)
      - Periyodik rotasyon politikası (ayda bir, çeyrekte bir)
      - Geliştirici ayrılışı (erişim kaldırma)

    UYARI: Rotate sonrası eski key ile imzalanmış TÜM token'lar geçersiz olur.
    Bağlı istemciler yeni api_key ile yeniden login olmalıdır.
    Yeni api_key bu yanıtta döner — güvenli şekilde saklayın.
    """
    obj = get_or_404(db, ApiYetki, id)
    obj.api_key    = secrets.token_urlsafe(32)  # Yeni URL-güvenli anahtar
    obj.secret_key = secrets.token_hex(32)      # Yeni JWT imzalama anahtarı
    db.commit()
    db.refresh(obj)  # Veritabanından güncel veriyi yükle (id, tarih vb.)
    return obj


@app.delete("/api/v2/api-yetkiler/{id}", tags=["API Yetki"])
def api_yetki_sil(id: int, db: Session = Depends(get_db)):
    """
    API kaynağını pasife alır (aktif=False).
    Fiziksel silme yapmaz — log ve denetim için kayıt korunur.
    Bu kaynaktan alınan mevcut token'lar bir sonraki istekte reddedilir.
    """
    obj = get_or_404(db, ApiYetki, id)
    obj.aktif = False  # Soft delete: fiziksel silme yerine pasife al
    db.commit()
    return {"ok": True, "mesaj": "API kaynağı devre dışı bırakıldı"}


# ── Login Endpoint (auth.py entegrasyonu ile) ─────────────────

class TokenYanit(BaseModel):
    """Login başarılı olduğunda dönen JWT token bilgisi."""
    access_token: str       # JWT token — Authorization: Bearer <token> header'ında kullanılır
    token_type: str         # Her zaman "bearer"
    kullanici_id: int  # Giriş yapan kullanıcının ID'si
    ad_soyad: str  # Ad ve soyadı
    rol: str                # ADMIN | STANDART | SADECE_OKUMA
    kaynak: str             # Hangi API kaynağından login olundu
    gecerlilik_saati: int   # Token kaç saat geçerli


# ════════════════════════════════════════════════════════════
#  ÇALIŞTIRMA
#  Doğrudan: python api.py
#  Geliştirme: uvicorn api:app --reload --port 8000
#  Üretim   : uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
#  ⚠️ --reload SADECE geliştirme ortamında kullanın!
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
