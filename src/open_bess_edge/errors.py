"""Jerarquía de excepciones de Open BESS Edge.

Regla de diseño: los errores de configuración y de perfil fallan **fuerte y
temprano** (al arranque). Los errores de planta en tiempo de ejecución nunca
se silencian: se convierten en estados/faltas explícitas del nodo.
"""

from __future__ import annotations


class OpenBessEdgeError(Exception):
    """Base de todas las excepciones del paquete."""


class ConfigError(OpenBessEdgeError, ValueError):
    """Configuración inválida, incompleta o inconsistente."""


class ProfileError(OpenBessEdgeError, ValueError):
    """Perfil de dispositivo inválido o inconsistente."""


class CodecError(OpenBessEdgeError, ValueError):
    """Error de codificación/decodificación de registros (p. ej. desborde)."""


class PlantCommError(OpenBessEdgeError):
    """Fallo de comunicación con la planta (timeout, desconexión, excepción Modbus)."""


class PlantDataError(OpenBessEdgeError):
    """La planta respondió pero los datos son inutilizables."""
