import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from mcp_server import solicitar_ficha_neumatico

print("Result no args:")
print(solicitar_ficha_neumatico())
print("\nResult with arg '10.00 R20 16PR LL-D09':")
print(solicitar_ficha_neumatico(nombre_producto='10.00 R20 16PR LL-D09'))
print("\nResult with arg 'LL-D09':")
print(solicitar_ficha_neumatico(nombre_producto='LL-D09'))
