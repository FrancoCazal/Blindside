/**
 * Tests de la lógica que no es React. Lo que se verifica acá es lo que puede
 * estar mal en silencio: un formato de cifra equivocado, una escala de eje que
 * recorta el pico, un tramo de quiebre que desaparece del gráfico.
 */

import { describe, expect, it } from "vitest";

import { areaHoras, escalaX, escalaY, maximoEje, rangosRecuperados, tramosDibujables } from "./chart";
import {
  RATIOS,
  cuantilCritico,
  deltaPct,
  esperanzaFaltante,
  esperanzaSobrante,
  impactoDeLinea,
} from "./domain";
import { conteoDeTotal, magnitud, porcentaje, serieCorta } from "./format";
import type { HistoryPoint, StockoutRun } from "./api/client";

const punto = (dt: string, observed: number, recovered = observed, horas = 0): HistoryPoint => ({
  dt,
  observed,
  recovered,
  is_censored: horas > 0,
  oos_hours_open: horas,
  available_weight: null,
  inflation_factor: null,
});

describe("formato de cifras", () => {
  it("usa coma decimal y punto de miles, sin unidad", () => {
    expect(magnitud(1.35)).toBe("1,35");
    expect(conteoDeTotal(60, 3066)).toBe("60 de 3.066");
  });

  it("usa el menos tipográfico y no un guion", () => {
    // U+2212. Un guion en una cifra negativa se lee como resta o como viñeta.
    expect(porcentaje(-24.5)).toBe("\u221224,5 %");
    expect(porcentaje(21.13)).toBe("+21,1 %");
  });

  it("arma el código corto de serie con ceros a la izquierda", () => {
    expect(serieCorta(4, 871)).toBe("T04 · P0871");
  });
});

describe("cuantil crítico", () => {
  it("es Cu / (Cu + Co)", () => {
    expect(cuantilCritico(1, 0.6)).toBeCloseTo(0.625, 10);
  });

  it("da la mediana cuando los dos errores cuestan igual", () => {
    expect(cuantilCritico(1, 1)).toBe(0.5);
  });

  it("los presets del control coinciden con los cuantiles que muestran", () => {
    const esperados = [0.769, 0.625, 0.5, 0.4];
    RATIOS.forEach((r, i) => {
      expect(cuantilCritico(1, r.co)).toBeCloseTo(esperados[i], 3);
    });
  });
});

describe("ahorro esperado de una línea de reorder", () => {
  const linea = (faltante: number, sobrante: number, deltaPct: number) => ({
    expected_shortfall: faltante,
    expected_overage: sobrante,
    cost_delta_pct: deltaPct,
  });

  it("reconstruye el ahorro absoluto desde el delta porcentual", () => {
    // costo de la orden = 0,2 + 0,6 * 0,5 = 0,5. Si eso es 8 % menos que la
    // política, la política cuesta 0,5 / 0,92 y el ahorro es la diferencia.
    const costoOrden = 0.2 + 0.6 * 0.5;
    const esperado = costoOrden / 0.92 - costoOrden;
    expect(impactoDeLinea(linea(0.2, 0.5, -8), 0.6)).toBeCloseTo(esperado, 10);
  });

  it("da ahorro negativo cuando la orden cuesta más que la política", () => {
    expect(impactoDeLinea(linea(0.2, 0.5, +10), 0.6)).toBeLessThan(0);
  });

  it("es cero sin línea, que es el caso de la API caída", () => {
    expect(impactoDeLinea(undefined, 0.6)).toBe(0);
  });

  it("ordena por magnitud y no por porcentaje", () => {
    // Dos series con el mismo ahorro relativo y bases muy distintas: la que
    // mueve más plata tiene que quedar primera. Es el motivo de reconstruir el
    // absoluto en vez de ordenar por cost_delta_pct.
    const grande = impactoDeLinea(linea(2.0, 5.0, -10), 0.6);
    const chica = impactoDeLinea(linea(0.02, 0.05, -10), 0.6);
    expect(grande).toBeGreaterThan(chica);
  });
});

describe("esperanzas del newsvendor sobre la banda", () => {
  it("son cero del lado en el que no hay error", () => {
    expect(esperanzaFaltante(10, 0, 10)).toBe(0);
    expect(esperanzaSobrante(0, 0, 10)).toBe(0);
  });

  it("en el centro de la banda reparten el error por igual", () => {
    expect(esperanzaFaltante(5, 0, 10)).toBeCloseTo(esperanzaSobrante(5, 0, 10), 10);
  });

  it("degeneran a la diferencia cuando la banda tiene ancho cero", () => {
    expect(esperanzaFaltante(1, 3, 3)).toBe(2);
    expect(esperanzaSobrante(5, 3, 3)).toBe(2);
  });
});

describe("delta contra la política", () => {
  it("no divide por cero", () => {
    expect(deltaPct(2, 0)).toBe(0);
  });

  it("informa la variación relativa en porcentaje", () => {
    expect(deltaPct(1.35, 0.96)).toBeCloseTo(40.625, 3);
  });
});

describe("escalas del gráfico", () => {
  it("el eje Y se autoescala al máximo con 6 % de aire", () => {
    expect(maximoEje([1, 12, 3])).toBeCloseTo(12.72, 10);
  });

  it("no colapsa cuando la serie es toda cero", () => {
    expect(maximoEje([0, 0])).toBe(1);
  });

  it("respeta los rellenos internos del área de dibujo", () => {
    const x = escalaX(10);
    expect(x(0)).toBe(46);
    expect(x(9)).toBe(1000 - 14);
    const y = escalaY(100);
    expect(y(0)).toBe(300 - 22);
    expect(y(100)).toBe(12);
  });
});

describe("tramos de quiebre", () => {
  const fechas = ["2024-06-01", "2024-06-02", "2024-06-03", "2024-06-04", "2024-06-05"];
  const x = escalaX(fechas.length);

  it("una racha de un solo día conserva ancho mínimo de 3 px", () => {
    const runs: StockoutRun[] = [{ start: "2024-06-03", end: "2024-06-03", n_days: 1 }];
    const [tramo] = tramosDibujables(runs, fechas, x);
    // Sin el mínimo el ancho sería 0 y la mitad del fenómeno desaparecería: la
    // mediana de racha en el panel real es de 2 días.
    expect(tramo.ancho).toBe(3);
  });

  it("la línea recuperada se dibuja con un día de entrada y uno de salida", () => {
    const runs: StockoutRun[] = [{ start: "2024-06-02", end: "2024-06-03", n_days: 2 }];
    const tramos = tramosDibujables(runs, fechas, x);
    expect(rangosRecuperados(tramos, fechas.length)).toEqual([{ desde: 0, hasta: 3 }]);
  });

  it("no se sale de la serie cuando el quiebre toca los bordes", () => {
    const runs: StockoutRun[] = [{ start: "2024-06-01", end: "2024-06-05", n_days: 5 }];
    const tramos = tramosDibujables(runs, fechas, x);
    expect(rangosRecuperados(tramos, fechas.length)).toEqual([{ desde: 0, hasta: 4 }]);
  });

  it("ignora tramos cuyas fechas no están en la ventana pedida", () => {
    const runs: StockoutRun[] = [{ start: "2024-01-01", end: "2024-01-02", n_days: 2 }];
    expect(tramosDibujables(runs, fechas, x)).toEqual([]);
  });
});

describe("franja de horas de quiebre", () => {
  it("escala de 0 a las franjas comerciales, no de 0 a 24", () => {
    const puntos = [punto("2024-06-01", 1, 1, 16), punto("2024-06-02", 1, 1, 0)];
    const trazo = areaHoras(puntos, 16, escalaX(2));
    // Con 16 de 16 horas en quiebre el primer punto toca el techo de la franja.
    expect(trazo.startsWith("M46.00 6.00")).toBe(true);
    // Y el día limpio queda sobre la base.
    expect(trazo).toContain("L986.00 46.00");
  });
});
