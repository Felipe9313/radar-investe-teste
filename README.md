# Radar Investe São Carlos

## Railway

Variável:
CAMINHO_BANCO=/data/radar.db

Volume:
Mount Path = /data

Start command:
uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
