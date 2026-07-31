import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from modules.catalogo_imagenes import buscar_imagen_local, _extraer_tokens_clave

print("Tokens 1:", _extraer_tokens_clave("10.00 R20 16PR LL-D09"))
print("Tokens 2:", _extraer_tokens_clave("10.00 R20 16PR CR-926"))
print("Tokens 3:", _extraer_tokens_clave("10.00"))
print("Tokens 4:", _extraer_tokens_clave("CR-926"))
