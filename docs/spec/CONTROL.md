# Especificación de control (v3)

Fórmulas: Δf = f − f0; Δf_activo = Δf ∓ banda muerta; ΔP = −(P_nom/(s·f0))·Δf_activo; P = base_rampeada + ΔP (±P_nom).
Q(V): Q = −K·Qmax·dv_activo, limitado a ±Qmax y a √(S²−P²) (prioridad a P).

Decisiones de diseño que **requieren confirmación del titular**:
1. La base del droop es el despacho (programa/AGC), nunca la potencia medida (la v2 generaba un integrador).
2. La rampa (%Pn/min) limita el cambio de la base; la componente droop no se rampea.
3. Alivio instantáneo simétrico de la base (subfrecuencia anula carga; sobrefrecuencia anula descarga).
4. En contingencia (|Δf| ≥ umbral) la respuesta es droop sin rampa, no potencia máxima (coincide con las pruebas CEN de v2).
5. Parámetros de red (±30 mHz, 3 %, 300 mHz, 20 %/min), retención 2 s, recorte 50 % desde 45 °C y SOC 5–95 %
   no están verificados contra la NTSyCS vigente.
6. Latencia: se mide de la muestra de frecuencia a la escritura de la consigna; no incluye la respuesta interna del PCS.
