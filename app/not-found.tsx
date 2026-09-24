import Link from "next/link";

export default function NoEncontrada() {
  return (
    <div className="aviso">
      <h1>Página no encontrada</h1>
      <p>
        La dirección no existe. Vuelve al <Link href="/">inicio</Link>.
      </p>
    </div>
  );
}
