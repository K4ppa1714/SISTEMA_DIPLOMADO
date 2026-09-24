// Pruebas del validador de payload (npm test). Incluyen TODOS los resultados de muestra.json,
// que es copia de lo que el pipeline publica en analitica.resultados.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { formatear, marcas, normalizarCaja, percentil, validarPayload, type Resultado } from "./payload.ts";

const base = { titulo: "T", conclusion: "C", fuente: "F" };

test("todos los resultados de muestra se pueden dibujar", () => {
  const muestra: Resultado[] = JSON.parse(readFileSync(new URL("./muestra.json", import.meta.url), "utf8"));
  assert.ok(muestra.length > 20);
  for (const r of muestra) {
    const v = validarPayload(r.payload);
    assert.ok(v.ok, `${r.modulo}/${r.clave}: ${v.ok ? "" : v.motivo}`);
  }
});

test("rechaza tipo desconocido y campos obligatorios faltantes", () => {
  assert.equal(validarPayload({ ...base, tipo: "pastel" }).ok, false);
  assert.equal(validarPayload({ tipo: "texto", titulo: "T", fuente: "F" }).ok, false);
  assert.equal(validarPayload(null).ok, false);
  assert.equal(validarPayload([]).ok, false);
});

test("línea: longitudes de x y series deben coincidir", () => {
  const malo = validarPayload({ ...base, tipo: "linea", x: { valores: ["a", "b"] }, series: [{ nombre: "s", valores: [1] }] });
  assert.equal(malo.ok, false);
  const bueno = validarPayload({ ...base, tipo: "linea", x: { valores: ["a", "b"] }, series: [{ nombre: "s", valores: [1, null] }] });
  assert.equal(bueno.ok, true);
});

test("línea: valores no numéricos se rechazan", () => {
  const v = validarPayload({ ...base, tipo: "barras", x: { valores: ["a"] }, series: [{ nombre: "s", valores: ["1"] }] });
  assert.equal(v.ok, false);
});

test("métrica con valor único se convierte en filas", () => {
  const v = validarPayload({ ...base, tipo: "metrica", valor: 0.93 });
  assert.ok(v.ok && v.payload.tipo === "metrica" && v.payload.filas[0].valor === 0.93);
});

test("caja: respaldo desde valores crudos coincide con numpy.percentile lineal", () => {
  const c = normalizarCaja({ nombre: "x", valores: [1, 2, 3, 4, 5, 6, 7, 8, 100] });
  assert.ok(c);
  assert.equal(c.q1, 3);
  assert.equal(c.mediana, 5);
  assert.equal(c.q3, 7);
  assert.deepEqual(c.atipicos, [100]);
  assert.equal(c.max, 8);
  assert.equal(percentil([1, 2, 3, 4], 25), 1.75); // numpy.percentile([1,2,3,4], 25) = 1.75
});

test("caja: cuartiles precalculados se respetan", () => {
  const c = normalizarCaja({ nombre: "d", n: 10, min: 0, q1: 1, mediana: 2, q3: 3, max: 5, atipicos: [9, "x"] });
  assert.deepEqual(c, { nombre: "d", n: 10, min: 0, q1: 1, mediana: 2, q3: 3, max: 5, atipicos: [9] });
});

test("marcas de eje cubren el rango con pasos redondos", () => {
  const m = marcas(0, 87);
  assert.ok(m[0] <= 0 && m[m.length - 1] >= 87);
  assert.deepEqual(marcas(0, 1, 5), [0, 0.2, 0.4, 0.6, 0.8, 1]);
  assert.ok(marcas(5, 5).length >= 2);
});

test("formato numérico en español de México", () => {
  assert.equal(formatear(1234.5), "1,234.5");
  assert.equal(formatear(null), "—");
  assert.equal(formatear(true), "sí");
  assert.equal(formatear(0.004123), "0.00412");
});

test("dispersión con x propio por serie (clustering/pca_segmentos)", () => {
  const v = validarPayload({ ...base, tipo: "dispersion", x: { etiqueta: "PC1" }, y: { etiqueta: "PC2" },
    series: [{ nombre: "a", x: [0.1, 0.2], valores: [1, 2] }, { nombre: "b", x: [3], valores: [4] }] });
  assert.ok(v.ok && v.payload.tipo === "dispersion" && v.payload.series[1].x[0] === 3);
  assert.equal(validarPayload({ ...base, tipo: "dispersion", series: [{ nombre: "a", x: [1], valores: [1, 2] }] }).ok, false);
});
