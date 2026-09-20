import os,base64,hashlib,hmac,secrets,time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ALPHABET='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'

def _key():
    raw=os.getenv('MFA_ENCRYPTION_KEY','')
    if os.getenv('ENVIRONMENT','development').lower()=='production' and len(raw)<32:
        raise RuntimeError('MFA_ENCRYPTION_KEY must have at least 32 characters in production')
    return hashlib.sha256((raw or 'cactus-food-dev-mfa-key').encode()).digest()

def generate_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')

def _decode(secret):
    padded=secret+'='*((8-len(secret)%8)%8)
    return base64.b32decode(padded,casefold=True)

def totp_code(secret,at=None,step=30,digits=6):
    at=time.time() if at is None else at
    counter=int(at//step).to_bytes(8,'big')
    digest=hmac.new(_decode(secret),counter,hashlib.sha1).digest()
    offset=digest[-1]&0x0f
    value=((digest[offset]&0x7f)<<24)|(digest[offset+1]<<16)|(digest[offset+2]<<8)|digest[offset+3]
    return str(value%(10**digits)).zfill(digits)

def verify_totp(secret,code,window=1):
    code=str(code or '').strip()
    if len(code)!=6 or not code.isdigit():return False
    now=time.time()
    return any(hmac.compare_digest(totp_code(secret,now+i*30),code) for i in range(-window,window+1))

def encrypt_secret(value):
    nonce=secrets.token_bytes(12)
    aes=AESGCM(_key())
    encrypted=aes.encrypt(nonce,str(value).encode(),None)
    return base64.urlsafe_b64encode(nonce+encrypted).decode()

def decrypt_secret(value):
    raw=base64.urlsafe_b64decode(value.encode())
    nonce,cipher=raw[:12],raw[12:]
    return AESGCM(_key()).decrypt(nonce,cipher,None).decode()

def opaque_hash(value):
    return hashlib.sha256(str(value).encode()).hexdigest()

def recovery_codes(count=8):
    return ['-'.join([secrets.token_hex(3)[:5],secrets.token_hex(3)[:5]]).upper() for _ in range(count)]
