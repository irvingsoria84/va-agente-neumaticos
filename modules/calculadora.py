"""
modules/calculadora.py
Replica las fórmulas del Excel "Calculo de Precios Ventas" adaptado a Neumáticos.
Todos los valores en CLP.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MARGEN_DEFAULT, IVA, ISLR, DESCUENTO_COMPRA


def _fp(valor: float) -> str:
    """Formatea un valor como precio CLP: $1.234.567"""
    return f"${int(valor):,}".replace(",", ".")


def _fpp(valor: float) -> str:
    """Formatea porcentaje con 1 decimal."""
    return f"{valor:.1f}%"


def calcular_cotizacion(
    precio_base: float,
    margen_pct: float = MARGEN_DEFAULT,
    cantidad: int = 1,
    flete: float = 0.0,
    comision_bancaria_pct: float = 0.0,
    comision_vendedor_pct: float = 0.0,
) -> dict:
    """
    Calcula precio de venta, IVA, ganancias y márgenes.
    Aplica el descuento de compra (35%) al precio base para obtener el costo real.
    """
    if margen_pct >= 100:
        raise ValueError("El margen no puede ser 100% o más.")
    if precio_base <= 0:
        raise ValueError("El precio base debe ser mayor a 0.")

    # ── Nuevo paso: Cálculo de Costo Real (Descuento 35%) ──
    costo = precio_base * (1.0 - DESCUENTO_COMPRA)

    # Precio de venta
    precio_sin_iva = costo / (1.0 - margen_pct / 100.0)

    # IVA
    iva_costo = costo * IVA
    iva_venta = precio_sin_iva * IVA
    iva_neto = iva_venta - iva_costo

    total_costo = costo + iva_costo
    total_venta = precio_sin_iva + iva_venta

    # Ganancias
    ganancia_bruta = precio_sin_iva - costo
    comision_bancaria = total_venta * (comision_bancaria_pct / 100.0)
    ganancia_neta = ganancia_bruta - flete - comision_bancaria
    comision_vendedor = ganancia_bruta * (comision_vendedor_pct / 100.0)
    provision_islr = ganancia_neta * ISLR

    ganancia_final = ganancia_neta - provision_islr - comision_vendedor

    pct_ganancia_real = (ganancia_final / total_venta * 100) if total_venta > 0 else 0

    return {
        "cantidad": int(cantidad),
        "margen_pct": float(margen_pct),
        "precio_base": round(precio_base),
        "costo_unitario": round(costo),
        "iva_costo": round(iva_costo),
        "total_costo_iva": round(total_costo),
        "precio_sin_iva": round(precio_sin_iva),
        "iva_venta": round(iva_venta),
        "total_venta_iva": round(total_venta),
        "iva_neto_sii": round(iva_neto),
        "ganancia_bruta": round(ganancia_bruta),
        "flete": round(flete),
        "comision_bancaria": round(comision_bancaria),
        "comision_vendedor": round(comision_vendedor),
        "ganancia_neta": round(ganancia_neta),
        "provision_islr": round(provision_islr),
        "ganancia_final": round(ganancia_final),
        "pct_ganancia_real": round(pct_ganancia_real, 1),
        "total_costo_cantidad": round(total_costo * cantidad),
        "total_venta_cantidad": round(total_venta * cantidad),
        "ganancia_total": round(ganancia_final * cantidad),
    }


def formatear_tabla_cotizacion(
    calc: dict,
    nombre_producto: str = "",
    codigo: str = "",
    stock: str = "",
    marca: str = "",
) -> str:
    """Formatea el resultado del cálculo como tabla de texto lista para presentar."""
    lineas: list[str] = []

    if nombre_producto:
        lineas.append(f"**{nombre_producto}**")
        if marca:
            lineas.append(f"   Marca: {marca}")
        if codigo:
            lineas.append(f"   Código: {codigo}")
        if stock:
            lineas.append(f"   Stock: {stock}")
        lineas.append("")

    sep = "-" * 46

    lineas.append("**COSTO PROVEEDOR (con 35% dcto.)**")
    lineas.append(sep)
    lineas.append(f"  Precio Base Original:      {_fp(calc['precio_base'])}")
    lineas.append(f"  Costo con Descuento:       {_fp(calc['costo_unitario'])}")
    lineas.append(f"  IVA crédito fiscal (19%):  {_fp(calc['iva_costo'])}")
    lineas.append(f"  Total costo c/IVA:         {_fp(calc['total_costo_iva'])}")
    lineas.append("")

    lineas.append(f"**PRECIO DE VENTA SUGERIDO (margen {_fpp(calc['margen_pct'])})**")
    lineas.append(sep)
    lineas.append(f"  Precio s/IVA:              {_fp(calc['precio_sin_iva'])}")
    lineas.append(f"  IVA débito fiscal (19%):   {_fp(calc['iva_venta'])}")
    lineas.append(f"  TOTAL CON IVA:             {_fp(calc['total_venta_iva'])}")
    lineas.append(f"  IVA neto a pagar SII:      {_fp(calc['iva_neto_sii'])}")
    lineas.append("")

    lineas.append("**MÁRGENES Y GANANCIAS**")
    lineas.append(sep)
    lineas.append(f"  Ganancia bruta:            {_fp(calc['ganancia_bruta'])}")
    if calc["flete"] > 0:
        lineas.append(f"  Flete/despacho:           -{_fp(calc['flete'])}")
    if calc["comision_bancaria"] > 0:
        lineas.append(f"  Comisión bancaria:        -{_fp(calc['comision_bancaria'])}")
    if calc["comision_vendedor"] > 0:
        lineas.append(f"  Comisión vendedor:        -{_fp(calc['comision_vendedor'])}")
    lineas.append(f"  Ganancia neta:             {_fp(calc['ganancia_neta'])}")
    lineas.append(f"  Provisión ISLR (12,5%):   -{_fp(calc['provision_islr'])}")
    lineas.append(f"  Ganancia final:            {_fp(calc['ganancia_final'])}")
    lineas.append(f"  % ganancia real s/venta:   {_fpp(calc['pct_ganancia_real'])}")

    if calc["cantidad"] > 1:
        lineas.append("")
        lineas.append(f"**TOTALES × {calc['cantidad']} UNIDADES**")
        lineas.append(sep)
        lineas.append(f"  Total costo c/dcto:        {_fp(calc['total_costo_cantidad'])}")
        lineas.append(f"  Total venta c/IVA:         {_fp(calc['total_venta_cantidad'])}")
        lineas.append(f"  Ganancia total:            {_fp(calc['ganancia_total'])}")

    return "\n".join(lineas)
