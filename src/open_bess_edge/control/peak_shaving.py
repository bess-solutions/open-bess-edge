"""Peak shaving BTM y ventana dinámica de restricciones de instalación.

Todo es función pura de la medición (sin integrador ni estado):

    L        = p_grid + P_bess                      (carga del sitio; P_bess + = descarga)
    P_shave  = max(0, L − max_grid_import)          (descarga necesaria para no superar la importación)
    dis_max  = min(cap_dis, max(0, L + max_grid_export))   (0 si SOC ≤ reserva)
    chg_max  = min(cap_chg, max(0, max_grid_import − L))

Cualquier P dentro de [−chg_max, +dis_max] cumple, respecto de L:
    p_grid_resultante = L − P  ≥  min(L, −max_export)   y   ≤  max(L, max_import)
es decir, la instalación nunca *empeora* su violación y la corrige siempre que la capacidad alcance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import InstallationConstraints


@dataclass(frozen=True, slots=True)
class SiteWindow:
    load_kw: float
    p_shave_kw: float
    dis_max_kw: float
    chg_max_kw: float
    shave_saturated: bool


def site_window(
    c: InstallationConstraints, *, p_grid_kw: Optional[float], p_bess_kw: float, soc_pct: float,
    dis_cap_kw: float, chg_cap_kw: float,
) -> SiteWindow:
    """Con ``p_grid_kw=None`` (sin medidor) sólo se aplica la reserva de SOC."""
    have = p_grid_kw is not None
    load = (p_grid_kw + p_bess_kw) if p_grid_kw is not None else float("nan")
    shave = max(0.0, load - c.max_grid_import_kw) if (have and c.max_grid_import_kw is not None) else 0.0
    dis = dis_cap_kw
    if have and c.max_grid_export_kw is not None:
        dis = min(dis, max(0.0, load + c.max_grid_export_kw))
    if c.soc_reserve_pct is not None and soc_pct <= c.soc_reserve_pct:
        dis = 0.0
    chg = chg_cap_kw
    if have and c.max_grid_import_kw is not None:
        chg = min(chg, max(0.0, c.max_grid_import_kw - load))
    return SiteWindow(load, shave, dis, chg, shave_saturated=shave > dis + 1e-9)
