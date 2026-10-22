/**
 * Tests de la lógica que no es React. Lo que se verifica acá es lo que puede
 * estar mal en silencio: un formato de cifra equivocado, una escala de eje que
 * recorta el pico, un tramo de quiebre que desaparece del gráfico.
 */

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { textoUmbral, textosMotivo } from "./alertas";
import { areaHoras, escalaX, escalaY, maximoEje, rangosRecuperados, tramosDibujables } from "./chart";
import {
  RATIOS,
  SENAL,
  aCsv,
  clasificarSenal,
  cuantilCritico,
  deltaPct,
  esperanzaFaltante,
  esperanzaSobrante,
  etiquetaFeature,
  lecturaRatio,
  valorFeature,
} from "./domain";
import {
  conteoDeTotal,
  descripcionCatalogo,
  estadoIngesta,
  etiquetaFecha,
  magnitud,
  porcentaje,
  porcentajeSimple,
  serieCorta,
} from "./format";
import { IDIOMA_POR_DEFECTO, fijarIdioma, idiomaActual } from "./i18n";
import { agruparModelos, conclusionBanda, grupoServido, nombreModelo, textoMejora } from "./modelos";
import type { HistoryPoint, StockoutRun } from "./api/client";

// Los tests de abajo fijan los textos en español, que es como se escribieron. El
// inglés, que es el idioma por defecto, tiene su propio bloque al final.
beforeAll(() => fijarIdioma("es"));
afterAll(() => fijarIdioma(IDIOMA_POR_DEFECTO));

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

describe("etiquetas de explicabilidad", () => {
  it("traduce las variables que dominan la explicación real", () => {
    expect(etiquetaFeature("latent_roll_mean_7")).toBe("Media de demanda · 7 días");
    expect(etiquetaFeature("latent_roll_median_14")).toBe("Mediana de demanda · 14 días");
    expect(etiquetaFeature("holiday_flag")).toBe("Feriado");
    expect(etiquetaFeature("discount")).toBe("Factor de descuento");
  });

  it("traduce rezagos y humaniza una feature nueva sin dejar snake_case", () => {
    expect(etiquetaFeature("latent_lag_28")).toBe("Demanda hace 28 días");
    expect(etiquetaFeature("feature_nueva")).toBe("Feature nueva");
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

describe("modelos: nombres, agrupación y mejora", () => {
  const fila = (model_name: string, metric: string, mean: number) => ({
    model_name,
    metric,
    mean,
    std: 0.04,
    worst_origin: mean + 0.05,
    best_origin: mean - 0.05,
    n_origins: 8,
  });
  const rows = [
    ...["cqr_lgbm_quantile", "conformal_lgbm_quantile_adaptive", "lgbm_global"].flatMap((m) => [
      fila(m, "mase", 0.8217),
      fila(m, "wape", 0.351),
      fila(m, "mae", 0.47),
    ]),
    fila("moving_average", "mase", 0.905),
    fila("moving_average", "wape", 0.396),
    fila("moving_average", "mae", 0.52),
    fila("seasonal_naive", "mase", 1.1),
    fila("seasonal_naive", "wape", 0.471),
    fila("seasonal_naive", "mae", 0.6),
    fila("cqr_lgbm_quantile", "coverage", 0.88),
  ];

  it("agrupa los modelos con el mismo pronóstico puntual en una fila", () => {
    const grupos = agruparModelos(rows);
    expect(grupos).toHaveLength(3);
    const lgbm = grupos[0];
    expect(lgbm.nombre).toBe("LightGBM global · CQR");
    expect(lgbm.miembros).toHaveLength(3);
    // El servido representa al grupo.
    expect(lgbm.clave).toBe("cqr_lgbm_quantile");
    expect(grupoServido(grupos)?.clave).toBe("cqr_lgbm_quantile");
  });

  it("no agrupa modelos que difieren aunque sea en una métrica", () => {
    const distinto = rows.map((r) =>
      r.model_name === "lgbm_global" && r.metric === "mae" ? { ...r, mean: 0.471 } : r,
    );
    expect(agruparModelos(distinto)).toHaveLength(4);
  });

  it("mide la mejora contra el naive estacional con una sola convención de signo", () => {
    const lgbm = agruparModelos(rows)[0];
    expect(lgbm.mejora).toBeCloseTo(25.3, 1);
    expect(lgbm.cumpleObjetivo).toBe(true);
    const fmt = (v: number) => `${magnitud(v, 1)} %`;
    expect(textoMejora(25.3, fmt)).toBe("25,3 % menos error");
    expect(textoMejora(-5.5, fmt)).toBe("5,5 % más error");
    expect(agruparModelos(rows).find((g) => g.esReferencia)?.mejora).toBeNull();
  });

  it("traduce las claves de modelo y conserva las desconocidas", () => {
    expect(nombreModelo("moving_average")).toBe("Media móvil 21 días");
    expect(nombreModelo("seasonal_naive")).toBe("Naive estacional");
    expect(nombreModelo("modelo_nuevo")).toBe("modelo_nuevo");
  });

  it("deriva la conclusión por banda de los números, no de un texto fijo", () => {
    // El texto fijo anterior decía lo contrario de la tabla: 0,822 contra 1,121.
    expect(conclusionBanda(0.822, 1.121, "baja")).toMatch(/le gana al naive/);
    expect(conclusionBanda(1.0, 1.01, "media")).toMatch(/empata/);
    expect(conclusionBanda(1.3, 1.0, "alta")).toMatch(/naive estacional le gana/);
  });
});

describe("valores de feature y estados de ingesta", () => {
  it("muestra ids y banderas sin decimales y magnitudes con dos", () => {
    expect(valorFeature("product_id", 600)).toBe("600");
    expect(valorFeature("holiday_flag", 1)).toBe("1");
    expect(valorFeature("latent_roll_mean_7", 6.04)).toBe("6,04");
    expect(valorFeature("discount", null)).toBe("sin dato");
  });

  it("traduce las features que quedaban en inglés", () => {
    expect(etiquetaFeature("days_since_start")).toBe("Antigüedad de la serie");
    expect(etiquetaFeature("dow")).toBe("Día de la semana");
    expect(etiquetaFeature("latent_lag_0")).toBe("Demanda del día del origen");
    expect(etiquetaFeature("avg_temperature_lag_7")).toBe("Temperatura · hace 7 días");
  });

  it("no muestra claves crudas de estado", () => {
    expect(estadoIngesta("sin_cambios")).toBe("sin cambios");
    expect(estadoIngesta("ok")).toBe("aplicado");
    expect(estadoIngesta("otro_estado")).toBe("otro estado");
  });
});

describe("estado de la señal reciente", () => {
  const resumen = (frac: number, racha = 0, sinVenta: number | null = 0) => ({
    estimated_share_last_28: frac,
    current_run_days: racha,
    days_since_last_sale: sinVenta,
  });

  it("clasifica en los tres estados según los umbrales medidos", () => {
    expect(clasificarSenal(resumen(0.1)).estado).toBe("observada");
    expect(clasificarSenal(resumen(0.29)).estado).toBe("observada");
    expect(clasificarSenal(resumen(SENAL.parcial)).estado).toBe("parcial");
    expect(clasificarSenal(resumen(0.35)).estado).toBe("parcial");
    expect(clasificarSenal(resumen(SENAL.escasa)).estado).toBe("escasa");
  });

  it("no usa el conteo de días censurados, que era el criterio mal calibrado", () => {
    // La mediana del panel es 12 de 28 días censurados, así que un umbral de 14
    // marcaba el 35,6 % del catálogo. Una serie con muchos días censurados pero
    // poca masa estimada tiene señal observada, y esto lo fija.
    const muchosDiasPocaMasa = clasificarSenal(resumen(0.05, 5));
    expect(muchosDiasPocaMasa.estado).toBe("observada");
  });

  it("menciona la racha vigente en el rótulo cuando es larga", () => {
    const enQuiebre = clasificarSenal(resumen(0.1, 4));
    expect(enQuiebre.rotulo).toContain("4");
    // Pero si la racha es corta no ensucia el rótulo.
    expect(clasificarSenal(resumen(0.1, 1)).rotulo).toBe("observada");
  });

  it("el detalle siempre dice la fracción, que es la cifra del criterio", () => {
    expect(clasificarSenal(resumen(0.42, 3, 2)).detalle).toContain("42 %");
    expect(clasificarSenal(resumen(0.42, 3, 2)).detalle).toContain("3 días de quiebre");
    expect(clasificarSenal(resumen(0.42, 3, 2)).detalle).toContain("2 sin venta");
  });
});

describe("armado de CSV", () => {
  it("escribe encabezados y filas separados por CRLF", () => {
    const csv = aCsv(["a", "b"], [[1, 2], [3, 4]]);
    expect(csv).toBe("a,b\r\n1,2\r\n3,4");
  });

  it("entrecomilla lo que lleva coma, comilla o salto de línea", () => {
    expect(aCsv(["x"], [["con,coma"]])).toBe('x\r\n"con,coma"');
    expect(aCsv(["x"], [['con"comilla']])).toBe('x\r\n"con""comilla"');
    expect(aCsv(["x"], [["con\nsalto"]])).toBe('x\r\n"con\nsalto"');
  });

  it("deja vacío lo nulo y lo no finito en vez de escribir NaN", () => {
    // Un "NaN" en una celda de Excel es peor que un vacío: se lee como dato.
    expect(aCsv(["x", "y", "z"], [[null, NaN, Infinity]])).toBe("x,y,z\r\n,,");
  });

  it("no toca los números, que van sin formato local", () => {
    // El CSV lo consume una planilla, no una persona: un separador decimal de
    // coma acá rompería el archivo que la propia coma separa.
    expect(aCsv(["x"], [[1.5]])).toBe("x\r\n1.5");
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

describe("idioma", () => {
  // Cada test fija su idioma y lo devuelve: el resto del archivo corre en español.
  const enIngles = (fn: () => void) => () => {
    fijarIdioma("en");
    try {
      fn();
    } finally {
      fijarIdioma("es");
    }
  };

  it("el idioma por defecto es inglés", () => {
    expect(IDIOMA_POR_DEFECTO).toBe("en");
  });

  it(
    "en inglés usa punto decimal, coma de miles y el % pegado a la cifra",
    enIngles(() => {
      expect(idiomaActual()).toBe("en");
      expect(magnitud(1.35)).toBe("1.35");
      expect(conteoDeTotal(60, 3066)).toBe("60 of 3,066");
      expect(porcentaje(-24.5)).toBe("\u221224.5%");
      expect(porcentajeSimple(42)).toBe("42%");
    }),
  );

  it(
    "en inglés la tienda se abrevia S y la fecha va mes y día",
    enIngles(() => {
      expect(serieCorta(4, 871)).toBe("S04 · P0871");
      expect(etiquetaFecha("2024-07-03")).toBe("Jul 3");
    }),
  );

  it("en español la fecha va día y mes", () => {
    expect(etiquetaFecha("2024-07-03")).toBe("3 jul");
  });

  it(
    "traduce modelos, features, estados y conclusiones",
    enIngles(() => {
      expect(nombreModelo("moving_average")).toBe("21-day moving average");
      expect(etiquetaFeature("latent_roll_mean_7")).toBe("Mean demand · 7 days");
      expect(etiquetaFeature("latent_lag_0")).toBe("Demand on the origin day");
      expect(estadoIngesta("sin_cambios")).toBe("no changes");
      expect(valorFeature("discount", null)).toBe("no data");
      expect(textoMejora(25.3, (v) => porcentajeSimple(v, 1))).toBe("25.3% less error");
      // La banda llega como valor de la API y se nombra en el idioma activo.
      expect(conclusionBanda(0.822, 1.121, "baja")).toBe(
        "In low turnover the model beats the seasonal naive.",
      );
      expect(clasificarSenal({ estimated_share_last_28: 0.1, current_run_days: 4 }).rotulo).toBe(
        "out of stock 4 d",
      );
      expect(lecturaRatio(0.6)).toMatch(/^Perishable/);
      expect(lecturaRatio(0.42)).toBeNull();
    }),
  );

  it(
    "redacta los textos de un motivo por clave y cae en los de la API si no la conoce",
    enIngles(() => {
      const grupo = {
        key: "no_confiable",
        label: "Modelo no confiable",
        meaning: "texto de la API",
        action: "texto de la API",
        threshold: "umbral de la API",
        threshold_value: 1,
      };
      expect(textosMotivo(grupo).rotulo).toBe("Unreliable model");
      expect(textoUmbral(grupo)).toBe("series MASE above 1.0: worse than the seasonal naive");
      expect(textoUmbral({ ...grupo, key: "riesgo_merma", threshold_value: 0.5 })).toMatch(
        /of 50% or more of expected demand over 7 days/,
      );
      const nuevo = { ...grupo, key: "motivo_nuevo" };
      expect(textosMotivo(nuevo).rotulo).toBe("Modelo no confiable");
      expect(textoUmbral(nuevo)).toBe("umbral de la API");
    }),
  );

  it(
    "vuelve a redactar la descripción de catálogo que la API arma en español",
    enIngles(() => {
      expect(descripcionCatalogo("tienda 12 · producto 403 · grupo 1 · cat 2/5/9 · ciudad 0")).toBe(
        "store 12 · product 403 · group 1 · cat 2/5/9 · city 0",
      );
      // Un formato que no se reconoce se muestra tal cual en vez de inventar.
      expect(descripcionCatalogo("otra cosa")).toBe("otra cosa");
    }),
  );
});
