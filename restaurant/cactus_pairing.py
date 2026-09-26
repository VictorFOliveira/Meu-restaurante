import hashlib
import hmac
import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from .db import connect, rows

router=APIRouter(prefix='/api/platform')
PRODUCT_CODE='MEU_RESTAURANTE'
PRODUCT_NAME='Meu Restaurante'

class PairRequest(BaseModel):
    controlPlane:str
    expectedProductCode:str
    expectedEnvironment:str
    platformKey:str
    rotate:bool=False

def env_name():
    return os.getenv('CACTUS_SAAS_ENV','local').strip().lower()

@router.get('/discovery')
def discovery():
    paired=rows("SELECT active FROM platform_control_plane_credentials WHERE id=1 LIMIT 1")
    return {
        'ok':True,'service':'cactus-saas','productCode':PRODUCT_CODE,
        'productName':PRODUCT_NAME,'environment':env_name(),
        'adminApiPath':'/api/platform','apiVersion':1,
        'paired':bool(paired and paired[0].get('active'))
    }

@router.post('/pair')
def pair(body:PairRequest,x_cactus_pairing_key:str|None=Header(default=None,alias='x-cactus-pairing-key')):
    expected=os.getenv('CACTUS_PAIRING_KEY','')
    if len(expected)<32 or not x_cactus_pairing_key or not hmac.compare_digest(x_cactus_pairing_key,expected):
        raise HTTPException(404)
    if body.controlPlane!='cactus-superadmin' or body.expectedProductCode.upper()!=PRODUCT_CODE:
        raise HTTPException(400,'pairing_identity_invalid')
    if body.expectedEnvironment.lower()!=env_name():
        raise HTTPException(409,'environment_mismatch')
    if len(body.platformKey)<32:
        raise HTTPException(400,'platform_key_invalid')
    current=rows("SELECT active FROM platform_control_plane_credentials WHERE id=1 LIMIT 1")
    if current and current[0].get('active') and not body.rotate:
        raise HTTPException(409,'already_paired')
    digest=hashlib.sha256(body.platformKey.encode()).hexdigest()
    with connect() as con:
        con.execute(text("""INSERT INTO platform_control_plane_credentials(id,key_hash,active,paired_at,rotated_at)
          VALUES(1,:h,TRUE,NOW(),CASE WHEN :r THEN NOW() ELSE NULL END)
          ON CONFLICT(id) DO UPDATE SET key_hash=excluded.key_hash,active=TRUE,
          paired_at=CASE WHEN platform_control_plane_credentials.active THEN platform_control_plane_credentials.paired_at ELSE NOW() END,
          rotated_at=CASE WHEN :r THEN NOW() ELSE platform_control_plane_credentials.rotated_at END"""),
          {'h':digest,'r':body.rotate})
    return {'ok':True,'service':'cactus-saas','productCode':PRODUCT_CODE,'productName':PRODUCT_NAME,'environment':env_name(),'apiVersion':1}

@router.get('/info')
def info(x_platform_key:str|None=Header(default=None,alias='x-platform-key')):
    if not x_platform_key:
        raise HTTPException(401,'platform_unauthorized')
    current=rows("SELECT key_hash FROM platform_control_plane_credentials WHERE id=1 AND active=TRUE LIMIT 1")
    digest=hashlib.sha256(x_platform_key.encode()).hexdigest()
    if not current or not hmac.compare_digest(digest,current[0]['key_hash']):
        raise HTTPException(401,'platform_unauthorized')
    return {'ok':True,'service':'cactus-saas','productCode':PRODUCT_CODE,'productName':PRODUCT_NAME,'environment':env_name(),'apiVersion':1}
