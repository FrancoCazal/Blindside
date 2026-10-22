/**
 * Sello de motivo de alerta. Los urgentes llevan borde y fondo ocre además del
 * color: la urgencia nunca se marca solo con color.
 */

import { URGENTES, rotuloMotivo } from "../alertas";

export function SelloMotivo({ clave }: { clave: string }) {
  return (
    <span className="sello-motivo" data-urgente={URGENTES.has(clave) ? "true" : undefined}>
      {rotuloMotivo(clave)}
    </span>
  );
}
