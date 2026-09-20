"""Módulos EXPERIMENTALES (no forman parte de la ruta de control certificable).

* ``can_bms``  : decodificador DBC de tramas CAN de BMS. Validado contra ``cantools``
                 (ver tests/test_experimental_can.py). Sin transporte SocketCAN.
* ``iec104``   : códec y servidor/cliente IEC 60870-5-104 (APCI/ASDU). Sin temporizadores
                 t1/t2/t3 ni ventanas k/w completas: NO apto para un SITR real sin más trabajo.
* ``goose``    : códec ASN.1 BER de un mensaje tipo GOOSE sobre UDP de loopback.
                 NO es GOOSE de IEC 61850-8-1 en la red (que es Ethernet capa 2, EtherType 0x88B8).
                 No se afirma latencia alguna.

Ninguno está conectado al ``EdgeNode``. El servicio ``sitr_gateway`` de la v2 fue ELIMINADO:
implementaba una segunda lógica de FFR (potencia fija a 49,45 Hz) que eludía la envolvente de
seguridad y los controladores; toda respuesta en frecuencia debe pasar por ``EdgeNode``.
"""
