"""Open BESS Edge — gateway industrial de borde para BESS.

Convenciones físicas (únicas en todo el código; ver docs/spec/CONVENTIONS.md):

* P [kW]    : ``+`` = descarga / inyección a la red, ``-`` = carga / absorción.
* Q [kvar]  : ``+`` = capacitivo (inyecta reactivos, eleva tensión),
              ``-`` = inductivo (absorbe reactivos, reduce tensión).
* f [Hz], V [V], SOC/SOH [%], T [°C], V_celda [V], R_aislamiento [kΩ].

Toda conversión desde/hacia la convención de un dispositivo se hace en el
borde del driver (perfil), nunca dentro de controladores ni de la envolvente.
"""

__version__ = "3.1.0"

__all__ = ["__version__"]
