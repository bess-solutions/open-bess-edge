# Especificación de control (v3)

Fórmulas:
- **Respuesta en frecuencia (FFR / Droop + RoCoF)**:
  - $\Delta f = f - f_0$; $\Delta f_{activo} = \Delta f \mp \text{banda\_muerta}$ (si $|\Delta f| > \text{banda\_muerta}$).
  - $\Delta P_{droop} = -\left(\frac{P_{nom}}{R \cdot f_0}\right) \cdot \Delta f_{activo}$.
  - Inercia sintética (RoCoF filtrado de 1er orden): $\Delta P_{inercia} = -k_{inercia} \cdot P_{nom} \cdot \left(\frac{df}{dt}\right)_{filt}$.
  - $P = \text{base\_rampeada} + \Delta P_{droop} + \Delta P_{inercia}$ (acotada a $\pm P_{nom}$).
- **Control Volt/VAR $Q(V)$ y Prioridad Dinámica**:
  - $Q = -K \cdot Q_{max} \cdot dv_{activo}$, limitado a $\pm Q_{max}$.
  - **Prioridad P normal** ($0.90 \le V \le 1.10\text{ pu}$): $Q$ limitado por $\sqrt{S_{max}^2 - P^2}$.
  - **Prioridad Q en soporte dinámico de red / LVRT** ($V < 0.90\text{ pu}$ o $V > 1.10\text{ pu}$): Conforme a NTSyCS Capítulo 3-4 e IEEE 2800-2022, se prioriza $Q$ para soporte de tensión de la red; $P$ se recorta dinámicamente a $\sqrt{S_{max}^2 - Q^2}$.

Decisiones de diseño y requerimientos normativos:
1. La base del droop es el despacho (programa/AGC), nunca la potencia medida (la v2 generaba un integrador).
2. La rampa (%Pn/min) limita el cambio de la base; la componente droop no se rampea.
3. Alivio instantáneo simétrico de la base (subfrecuencia anula carga; sobrefrecuencia anula descarga).
4. En contingencia ($|\Delta f| \ge \text{umbral}$) la respuesta es droop sin rampa.
5. **Parámetros de red alineados con los requerimientos técnicos de la NTSyCS (Res. Exenta CNE N° 343) y NT SSCC 2026 del CEN**:
   - Frecuencia nominal: $f_0 = 50.0\text{ Hz}$.
   - Estatismo ($R$): $3\%$ ($0.03$), configurable en el rango $2\% - 5\%$ (NTSyCS Art. 3-17).
   - Banda muerta de frecuencia: $\pm 30\text{ mHz}$ ($\pm 0.03\text{ Hz}$).
   - Umbral de contingencia de frecuencia: $\pm 300\text{ mHz}$ ($\pm 0.30\text{ Hz}$).
   - Tiempo de respuesta en frecuencia: activación $\le 200\text{ ms}$, respuesta completa $\le 2.0\text{ s}$.
   - Banda muerta de tensión: $0.98 - 1.02\text{ pu}$ ($\pm 2\%$).
   - Conmutación dinámica a Q-Priority en depresión de tensión ($V < 0.90\text{ pu}$).
   - Retención por pérdida de enlace: 2 s, recorte térmico escalonado desde 45 °C y ventana operativa de SOC 5–95 %.
6. Latencia: se mide de la muestra de frecuencia a la escritura de la consigna; no incluye la respuesta interna del PCS.

