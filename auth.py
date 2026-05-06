"""
auth.py — JWT Kimlik Doğrulama Katmanı
=======================================
Bu modül api.py ile birlikte çalışır.
SECRET_KEY kodda sabit değildir; her API kaynağı (web, mobil, entegrasyon)
kendi secret_key'ini api_yetki tablosundan alır.

Kurulum:
    pip install python-jose[cryptography] passlib[bcrypt]

Login akışı:
    1. İstemci → POST /login  (X-API-Key header + email + şifre)
    2. api_yetki tablosundan kaynak bulunur ve doğrulanır
    3. IP kısıtı kontrol edilir
    4. Kullanıcı + bcrypt şifre doğrulanır
    5. Kullanıcı rolü kaynağın izin listesinde mi kontrol edilir
    6. JWT token üretilir (kaynağa özel secret_key ile imzalanır)
    7. Sonraki isteklerde: Authorization: Bearer <token>
"""

# Standart kütüphane — tarih/saat ve tip ipuçları
from datetime import datetime, timedelta  # datetime: zaman damgası | timedelta: token süre hesabı
from typing import Optional  # Opsiyonel tip ipuçları

# JWT encode/decode kütüphanesi
# JWTError → geçersiz imza, süresi dolmuş veya bozuk token hatası
from jose import JWTError, jwt  # JWT encode/decode | JWTError: geçersiz/süresi dolmuş token

# Şifre hashleme — bcrypt tek yönlü hash algoritması
# Düz şifre asla veritabanına yazılmaz
from passlib.context import CryptContext  # Şifre hashleme motoru — bcrypt desteği

# FastAPI güvenlik araçları
from fastapi import Depends, HTTPException, Request, status  # DI, HTTP hata, istek nesnesi, durum kodları
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm  # Bearer token okuyucu ve login form şeması
# OAuth2PasswordBearer → Authorization: Bearer <token> header'ını otomatik okur
# OAuth2PasswordRequestForm → /login'de gelen form verisi (username + password)

# Yanıt şeması için Pydantic
from pydantic import BaseModel  # Yanıt şeması tanımı

# Veritabanı bağlantısı ve modeller
from sqlalchemy.orm import Session  # Veritabanı oturumu tipi
from api import get_db, Kullanici, ApiYetki  # api.py'den DB bağımlılığı ve modeller
# get_db    → DB oturumu dependency injection fonksiyonu
# Kullanici → kullanici tablosu SQLAlchemy modeli
# ApiYetki  → api_yetki tablosu SQLAlchemy modeli

# ─────────────────────────────────────────────────────────────
# GENEL AYARLAR
# ─────────────────────────────────────────────────────────────

# JWT imzalama algoritması
# HS256 (HMAC-SHA256): simetrik algoritma, aynı secret ile imzalar ve doğrular
# Alternatif RS256 (asimetrik) daha karmaşık; bu kullanım için HS256 yeterlidir
ALGORITHM = "HS256"  # JWT imzalama algoritması (HMAC-SHA256)

# Şifre hashleme motoru
# schemes=["bcrypt"] → bcrypt algoritması kullanılır
# deprecated="auto"  → eski algoritmalar tespit edilince otomatik geçersiz sayılır
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # bcrypt hashleme motoru; eski algoritmalar otomatik geçersiz

# Bearer token okuyucu
# tokenUrl → Swagger UI'da "Authorize" düğmesinin yönleneceği endpoint adresi
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")  # Authorization: Bearer <token> header'ını okur


# ─────────────────────────────────────────────────────────────
# ŞİFRE İŞLEMLERİ
# ─────────────────────────────────────────────────────────────

def sifreyi_dogrula(duz: str, hashli: str) -> bool:
    """
    Kullanıcının girdiği düz şifreyi veritabanındaki bcrypt hash ile karşılaştırır.
    Doğrudan string karşılaştırması yapılmaz; bcrypt'in güvenli verify() metodu kullanılır.

    Args:
        duz    : Kullanıcının login formuna girdiği şifre (düz metin)
        hashli : Veritabanındaki bcrypt hash (kullanici.sifre_hash alanı)

    Returns:
        True → şifre doğru | False → şifre yanlış
    """
    return pwd_context.verify(duz, hashli)  # bcrypt güvenli karşılaştırma


def sifreyi_hashle(duz: str) -> str:
    """
    Düz şifreyi bcrypt ile hashler. Kullanıcı oluşturma veya şifre değişikliğinde kullanılır.
    Üretilen hash her seferinde farklıdır (salt eklenir) — bu normaldir ve güvenlidir.

    Örnek kullanım:
        from auth import sifreyi_hashle
        hash_deger = sifreyi_hashle("guclu_sifre_123!")
        # Bu değeri kullanici.sifre_hash alanına kaydedin

    Args:
        duz : Kullanıcının belirlediği düz şifre

    Returns:
        '$2b$12$...' formatında bcrypt hash dizesi
    """
    return pwd_context.hash(duz)  # bcrypt ile güvenli hashleme


# ─────────────────────────────────────────────────────────────
# API KAYNAK DOĞRULAMA
# ─────────────────────────────────────────────────────────────

def api_yetki_getir(api_key: str, db: Session) -> ApiYetki:
    """
    İstemcinin X-API-Key header'ında gönderdiği anahtara göre api_yetki kaydını bulur.
    Her kaynak (web arayüzü, mobil uygulama, entegrasyon) farklı api_key taşır.
    Bu sayede hangi kaynaktan bağlanıldığı ve hangi secret_key kullanılacağı belirlenir.

    Args:
        api_key : X-API-Key header değeri
        db      : Veritabanı oturumu

    Returns:
        ApiYetki ORM nesnesi (secret_key dahil)

    Raises:
        HTTPException(401) : api_key bulunamazsa veya kaynak aktif=False ise
    """
    # api_key + aktif=True ile kayıt ara; pasif kaynaklar kabul edilmez
    kaynak = db.query(ApiYetki).filter_by(api_key=api_key, aktif=True).first()  # api_key + aktif=True ile kaynak ara

    if not kaynak:  # Bulunamadı ya da pasife alınmış
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,  # 401: kimlik doğrulama başarısız
            detail="Geçersiz veya devre dışı API anahtarı. "  # Hata mesajı
                   "Lütfen api_yetki tablosundan geçerli bir api_key alın.",  # Yönlendirici açıklama
        )
    return kaynak  # Doğrulanmış kaynak nesnesi


# ─────────────────────────────────────────────────────────────
# IP KISITI KONTROLÜ
# ─────────────────────────────────────────────────────────────

def ip_kontrol(kaynak: ApiYetki, request: Request) -> None:
    """
    Kaynağın ip_listesi doluysa istemci IP'sinin listede olup olmadığını kontrol eder.
    ip_listesi boş veya None ise hiçbir kısıt uygulanmaz — herkese açık.

    ip_listesi formatı: virgülle ayrılmış IP adresleri
    Örnek: "192.168.1.10,10.0.0.5,172.16.0.1"

    NOT — Nginx/proxy arkasında çalışıyorsanız:
        Gerçek istemci IP'si için X-Forwarded-For header'ını kullanın:
        istemci_ip = request.headers.get(
            "X-Forwarded-For", request.client.host
        ).split(",")[0].strip()

    Args:
        kaynak  : ApiYetki ORM nesnesi (ip_listesi alanı okunur)
        request : FastAPI Request nesnesi (istemci IP'si için)

    Raises:
        HTTPException(403) : İstemci IP'si izin listesinde değilse
    """
    if not kaynak.ip_listesi:  # ip_listesi boş → kısıtlama yok, devam et
        return  # ip_listesi boş → kısıtlama yok, geç

    # Virgülle ayrılmış listeyi ayrıştır, başındaki/sonundaki boşlukları temizle
    izinli_ipler = [ip.strip() for ip in kaynak.ip_listesi.split(",") if ip.strip()]  # IP listesini parse et, boşlukları temizle

    # İstemci IP adresini al
    istemci_ip = request.client.host  # İstemci IP adresi
    # Nginx arkasında: istemci_ip = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()

    if istemci_ip not in izinli_ipler:  # İzin listesinde yok
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,  # 403: erişim yasak
            detail=f"Bu IP adresinden erişim izni yok: {istemci_ip}. "  # IP kısıtı hata mesajı
                   f"İzinli IP'ler api_yetki tablosunda yönetilir.",
        )


# ─────────────────────────────────────────────────────────────
# JWT TOKEN ÜRETİMİ
# ─────────────────────────────────────────────────────────────

def token_olustur(kullanici: Kullanici, kaynak: ApiYetki) -> str:
    """
    Kullanıcı ve kaynak bilgisini içeren, kaynağa özel secret_key ile imzalı JWT üretir.

    Token payload alanları (claims):
        sub    → kullanıcı ID'si (standart JWT "subject" alanı)
        email  → kullanıcı e-postası (bilgi amaçlı)
        rol    → ADMIN | STANDART | SADECE_OKUMA
        kaynak → api_yetki.ad — decode aşamasında doğru secret'ı bulmak için
        exp    → token son kullanma zamanı (Unix timestamp — jose otomatik kontrol eder)

    Her kaynak kendi secret_key'i ile imzaladığından, farklı kaynakların
    token'ları birbirinin secret'ı ile doğrulanamaz — güvenlik katmanı sağlanır.

    Args:
        kullanici : Kimliği doğrulanmış Kullanici ORM nesnesi
        kaynak    : Login yapılan ApiYetki ORM nesnesi

    Returns:
        İmzalı JWT token dizesi ("eyJ..." formatında)
    """
    payload = {  # JWT payload: token içindeki veriler
        "sub":    kullanici.id,      # Kullanıcı kimliği — token sahibi
        "email":  kullanici.email,   # Bilgi amaçlı — doğrulama gerektirmez
        "rol":    kullanici.rol,     # Rol bazlı erişim kontrolü için
        "kaynak": kaynak.ad,         # Decode'da doğru secret'ı bulmak için kritik
        "exp":    datetime.utcnow() + timedelta(hours=kaynak.token_sure),  # Token son kullanma zamanı
        # exp: bu zamandan sonra token geçersiz; jose kütüphanesi otomatik kontrol eder
    }

    # Kaynağa özel secret_key ile imzala
    return jwt.encode(payload, kaynak.secret_key, algorithm=ALGORITHM)


# ─────────────────────────────────────────────────────────────
# JWT TOKEN ÇÖZÜMLEME (İKİ AŞAMALI)
# ─────────────────────────────────────────────────────────────

def token_coz(token: str, db: Session) -> dict:
    """
    JWT token'ı iki aşamada çözer ve doğrulanmış payload'ı döner.

    Neden iki aşama gerekli?
        Her API kaynağının farklı bir secret_key'i vardır.
        Doğrulamadan önce hangi kaynağın secret'ını kullanacağımızı bilmemiz gerekir.
        Bu bilgi token'ın 'kaynak' alanındadır — önce onu okumamız gerekir.

    Aşama 1 — İmzasız okuma:
        verify_signature=False ile token payload'ı okunur.
        Sadece 'kaynak' alanı alınır. Bu aşama GÜVENLİ DEĞİLDİR;
        token henüz doğrulanmamıştır — yalnızca kaynak adı okunur.

    Aşama 2 — İmzalı doğrulama:
        'kaynak' alanından api_yetki tablosunda o kaynağın secret_key'i bulunur.
        Token bu secret ile yeniden decode edilir.
        jose kütüphanesi hem imzayı hem exp (süre) alanını bu aşamada doğrular.

    Args:
        token : Authorization: Bearer <token> header'ından okunan JWT dizesi
        db    : Veritabanı oturumu (secret_key sorgusu için)

    Returns:
        Doğrulanmış payload sözlüğü {'sub': ..., 'email': ..., 'rol': ..., ...}

    Raises:
        HTTPException(401) : Token geçersiz, süresi dolmuş veya kaynak pasifse
    """
    # Standart 401 hata yanıtı — tüm token hataları aynı mesajla döner
    # (farklı mesajlar saldırgana bilgi verebilir)
    hata = HTTPException(  # Tüm token hataları için standart 401 yanıtı
        status_code=status.HTTP_401_UNAUTHORIZED,  # 401: kimlik doğrulama başarısız
        detail="Token geçersiz veya süresi dolmuş. Lütfen yeniden giriş yapın.",  # Genel hata mesajı (detay vermez)
        headers={"WWW-Authenticate": "Bearer"},  # Standart OAuth2 header'ı
    )

    try:
        # ── Aşama 1: İmzasız okuma — sadece 'kaynak' alanını almak için ──────
        govde = jwt.decode(  # Aşama 1: imzasız okuma — sadece kaynak alanı için
            token,
            options={"verify_signature": False},  # İmzayı atla, sadece payload'ı oku
        )
        kaynak_adi = govde.get("kaynak")  # 'kaynak' alanını al

        if not kaynak_adi:  # Token'da kaynak yoksa → geçersiz format
            raise hata  # Token'da kaynak bilgisi yoksa → geçersiz format

        # DB'den o kaynağın kaydını ve secret_key'ini al
        kaynak = db.query(ApiYetki).filter_by(ad=kaynak_adi, aktif=True).first()

        if not kaynak:
            raise hata  # Kaynak pasife alınmış veya silinmiş → token geçersiz

        # ── Aşama 2: Gerçek imza + süre doğrulaması ─────────────────────────
        payload = jwt.decode(
            token,
            kaynak.secret_key,       # Kaynağa özel secret ile doğrula
            algorithms=[ALGORITHM],  # Yalnızca HS256 kabul et
        )
        # jose burada hem imzayı hem exp (süre) alanını kontrol eder
        # Süresi dolmuşsa veya imza yanlışsa → JWTError fırlatır

        return payload  # Doğrulanmış payload

    except JWTError:
        # JWTError: imza yanlış, token süresi dolmuş veya token bozuk
        raise hata


# ─────────────────────────────────────────────────────────────
# DEPENDENCY INJECTION — AKTİF KULLANICI
# ─────────────────────────────────────────────────────────────

def aktif_kullanici(
    token: str = Depends(oauth2_scheme),  # Authorization header'dan otomatik alınır
    db: Session = Depends(get_db),        # DB oturumu enjekte edilir
) -> Kullanici:
    """
    Korumalı endpoint'lere enjekte edilen temel bağımlılık.
    Token'ı çözer, kullanıcıyı DB'den getirir ve döner.

    Kullanım örneği:
        @app.get("/api/v2/cariler")
        def cariler(
            db: Session = Depends(get_db),
            k: Kullanici = Depends(aktif_kullanici),  # ← bu satır yeterli
        ):
            # k → giriş yapmış kullanıcı; k.id, k.rol, k.email erişilebilir

    Args:
        token : oauth2_scheme tarafından Authorization: Bearer <token> header'ından okunur
        db    : DB oturumu

    Returns:
        Aktif ve doğrulanmış Kullanici ORM nesnesi

    Raises:
        HTTPException(401) : Token geçersizse veya kullanıcı bulunamazsa/pasifse
    """
    payload = token_coz(token, db)  # Token'ı doğrula ve payload'ı al

    kullanici_id = payload.get("sub")  # 'sub' → kullanıcı ID'si
    if not kullanici_id:
        raise HTTPException(401, "Token içinde kullanıcı bilgisi eksik.")

    kullanici = db.get(Kullanici, kullanici_id)  # DB'den kullanıcıyı getir

    if not kullanici:  # Kullanıcı silinmiş
        raise HTTPException(401, "Kullanıcı bulunamadı.")

    if not kullanici.aktif:  # Hesap devre dışı
        raise HTTPException(401, "Kullanıcı hesabı devre dışı bırakılmış.")

    return kullanici  # Doğrulanmış kullanıcı nesnesi


# ─────────────────────────────────────────────────────────────
# ROL BAZLI ERİŞİM KONTROL FONKSİYONLARI
# Her biri Depends() ile endpoint parametresine eklenir.
# ─────────────────────────────────────────────────────────────

def admin_gerekli(k: Kullanici = Depends(aktif_kullanici)) -> Kullanici:
    """
    Yalnızca ADMIN rolündeki kullanıcıların erişebildiği endpoint'ler için.
    Kullanıcı yönetimi, API yetki yönetimi, sistem ayarları gibi kritik işlemler.

    Kullanım:
        @app.delete("/api/v2/kullanicilar/{id}")
        def kullanici_sil(id: int, k = Depends(admin_gerekli), db = Depends(get_db)):
            ...  # Yalnızca ADMIN buraya ulaşabilir

    Raises:
        HTTPException(401) : Token geçersizse (aktif_kullanici üzerinden)
        HTTPException(403) : Kullanıcı rolü ADMIN değilse
    """
    if k.rol != "ADMIN":  # ADMIN dışındaki roller reddedilir
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,  # 403: erişim yasak
            detail=f"Bu işlem için ADMIN yetkisi gerekli. Mevcut rol: {k.rol}",
        )
    return k  # ADMIN kullanıcı — işleme devam


def yazma_gerekli(k: Kullanici = Depends(aktif_kullanici)) -> Kullanici:
    """
    SADECE_OKUMA rolündeki kullanıcıları engelleyen endpoint'ler için.
    POST, PUT, DELETE işlemlerinde kullanılır.
    ADMIN ve STANDART rolleri bu kontrolü geçer.

    Kullanım:
        @app.post("/api/v2/belgeler")
        def belge_olustur(payload: BelgeBaslikCreate, k = Depends(yazma_gerekli)):
            ...  # ADMIN ve STANDART buraya ulaşabilir; SADECE_OKUMA reddedilir

    Raises:
        HTTPException(403) : Kullanıcı rolü SADECE_OKUMA ise
    """
    if k.rol == "SADECE_OKUMA":  # Yalnızca SADECE_OKUMA rolü reddedilir
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,  # 403: erişim yasak
            detail="Bu işlem için yazma yetkisi gerekli. "
                   "SADECE_OKUMA rolü yalnızca listeleme ve görüntüleme yapabilir.",
        )
    return k  # ADMIN veya STANDART — işleme devam


def okuma_gerekli(k: Kullanici = Depends(aktif_kullanici)) -> Kullanici:
    """
    Giriş yapmış tüm kullanıcılara açık endpoint'ler için.
    ADMIN, STANDART ve SADECE_OKUMA rolleri bu kontrolü geçer.
    Yalnızca oturum doğrulaması yapılır; ek rol kontrolü yoktur.

    Kullanım:
        @app.get("/api/v2/cariler")
        def cariler(k = Depends(okuma_gerekli), db = Depends(get_db)):
            ...  # Giriş yapmış herkes erişebilir
    """
    return k  # Tüm roller geçer — sadece giriş doğrulaması yapılır


# ─────────────────────────────────────────────────────────────
# LOGIN YANIT ŞEMASI
# ─────────────────────────────────────────────────────────────

class TokenYanit(BaseModel):
    """Login başarılı olduğunda dönen JWT token bilgisi."""
    access_token: str       # JWT — Authorization: Bearer <token> header'ında kullanılır
    token_type: str         # Her zaman "bearer" (OAuth2 standardı)
    kullanici_id: int       # Giriş yapan kullanıcının ID'si
    ad_soyad: str           # Görüntüleme için kullanıcı adı
    rol: str                # ADMIN | STANDART | SADECE_OKUMA
    kaynak: str             # Hangi API kaynağından login olundu (ApiYetki.ad)
    gecerlilik_saati: int   # Token kaç saat geçerli (ApiYetki.token_sure)


# ─────────────────────────────────────────────────────────────
# LOGIN İŞLEMİ — ANA FONKSİYON
# ─────────────────────────────────────────────────────────────

def login_isle(
    api_key: str,      # X-API-Key header'ından gelen kaynak anahtarı
    email: str,        # Kullanıcı e-postası (OAuth2 form'da "username" alanı)
    sifre: str,        # Kullanıcının girdiği düz şifre
    request: Request,  # IP kısıt kontrolü için FastAPI request nesnesi
    db: Session,       # Tüm DB sorguları için oturum
) -> TokenYanit:
    """
    Login işleminin tüm adımlarını sırayla yürütür.

    Adım 1 — API Kaynağı Doğrulama:
        X-API-Key → api_yetki tablosunda aranır.
        Bulunamazsa veya aktif=False ise → 401 Unauthorized

    Adım 2 — IP Kısıtı Kontrolü:
        Kaynağın ip_listesi doluysa istemci IP'si kontrol edilir.
        İzin verilmiyorsa → 403 Forbidden

    Adım 3 — Kullanıcı Kimlik Doğrulama:
        E-posta + şifre kullanici tablosunda doğrulanır.
        Bulunamazsa, şifre yanlışsa veya aktif=False ise → 401 Unauthorized
        (Güvenlik: "kullanıcı yok" ile "şifre yanlış" aynı mesajla döner)

    Adım 4 — Rol İzin Kontrolü:
        Kullanıcının rolü kaynağın izin_verilen_roller listesinde mi?
        Değilse → 403 Forbidden
        Örnek: ip_listesi='SADECE_OKUMA' olan kaynak ADMIN'i reddeder.

    Adım 5 — Token Üretimi ve Kayıt:
        Kaynağa özel secret_key ile JWT imzalanır.
        kaynak.son_kullanim güncellenerek denetim kaydı tutulur.

    Args:
        api_key : X-API-Key header değeri
        email   : Kullanıcı e-postası
        sifre   : Kullanıcı şifresi (düz metin)
        request : FastAPI Request nesnesi
        db      : Veritabanı oturumu

    Returns:
        TokenYanit — access_token ve kullanıcı bilgilerini içerir

    Raises:
        HTTPException(401) : Kimlik doğrulama başarısız
        HTTPException(403) : Yetkilendirme başarısız
    """

    # ── Adım 1: API kaynağını doğrula ───────────────────────
    kaynak = api_yetki_getir(api_key, db)  # Bulunamazsa 401 fırlatır

    # ── Adım 2: IP kısıtı ────────────────────────────────────
    ip_kontrol(kaynak, request)  # İzin verilmiyorsa 403 fırlatır

    # ── Adım 3: Kullanıcı kimlik doğrulama ───────────────────
    kullanici = db.query(Kullanici).filter_by(
        email=email,   # E-posta eşleşmeli
        aktif=True,    # Pasif kullanıcılar giriş yapamaz
    ).first()

    # Güvenlik notu: "şifre yanlış" ile "kullanıcı bulunamadı" ayrı mesaj vermez
    # — saldırganın kullanıcı adı tespiti yapmasını önler
    if not kullanici or not sifreyi_dogrula(sifre, kullanici.sifre_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,  # 401: kimlik doğrulama başarısız
            detail="E-posta veya şifre hatalı.",
        )

    # ── Adım 4: Rol izin kontrolü ────────────────────────────
    izinli_roller = [
        r.strip()  # Her roldeki boşlukları temizle
        for r in kaynak.izin_verilen_roller.split(",")  # Virgülle ayır
    ]

    if kullanici.rol not in izinli_roller:  # Kullanıcı rolü listede yok
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,  # 403: erişim yasak
            detail=f"'{kaynak.ad}' kaynağı '{kullanici.rol}' rolüne izin vermiyor. "
                   f"İzin verilen roller: {kaynak.izin_verilen_roller}",
        )

    # ── Adım 5: Token üret ve son kullanımı güncelle ─────────
    token = token_olustur(kullanici, kaynak)  # Kaynağa özel JWT imzala

    kaynak.son_kullanim = datetime.now()  # Denetim için son kullanım zamanı kaydet
    db.commit()  # son_kullanim değişikliğini veritabanına yaz

    return TokenYanit(
        access_token=token,              # İmzalanmış JWT
        token_type="bearer",             # OAuth2 standardı
        kullanici_id=kullanici.id,       # Kullanıcı ID'si
        ad_soyad=kullanici.ad_soyad,     # Görüntüleme adı
        rol=kullanici.rol,               # Kullanıcı rolü
        kaynak=kaynak.ad,               # Hangi kaynaktan login olundu
        gecerlilik_saati=kaynak.token_sure,  # Token süresi (saat)
    )


# ─────────────────────────────────────────────────────────────
# api.py'e ENTEGRASYON
# ─────────────────────────────────────────────────────────────
# Aşağıdaki kodu api.py dosyasına ekleyin:
#
# from auth import (
#     login_isle, TokenYanit,
#     aktif_kullanici, admin_gerekli,
#     yazma_gerekli, okuma_gerekli,
# )
# from fastapi import Header, Request
# from fastapi.security import OAuth2PasswordRequestForm
#
# @app.post("/login", response_model=TokenYanit, tags=["Auth"])
# def login(
#     request: Request,
#     form: OAuth2PasswordRequestForm = Depends(),
#     x_api_key: str = Header(..., alias="X-API-Key",
#                             description="api_yetki tablosundan alınan API anahtarı"),
#     db: Session = Depends(get_db),
# ):
#     """
#     Giriş endpoint'i. İki şey gereklidir:
#       Header → X-API-Key: <api_key>   (hangi kaynaktan bağlanıldığı)
#       Body   → username + password     (kullanıcı e-posta ve şifre)
#     Yanıt   → access_token (JWT Bearer)
#     """
#     return login_isle(x_api_key, form.username, form.password, request, db)
#
#
# ENDPOINT KORUMA ÖRNEKLERİ:
#
# # Herkese açık (giriş yapmış) — GET endpoint'leri için:
# @app.get("/api/v2/cariler")
# def cariler(k = Depends(okuma_gerekli), db = Depends(get_db)):
#     ...
#
# # Yazma işlemleri (SADECE_OKUMA giremez):
# @app.post("/api/v2/belgeler")
# def belge_olustur(payload: BelgeBaslikCreate, k = Depends(yazma_gerekli), db = Depends(get_db)):
#     ...
#
# # Sadece ADMIN:
# @app.delete("/api/v2/kullanicilar/{id}")
# def kullanici_sil(id: int, k = Depends(admin_gerekli), db = Depends(get_db)):
#     ...
