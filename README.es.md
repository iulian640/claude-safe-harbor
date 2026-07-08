# Claude safe-harbor

Una skill de [Claude Code](https://claude.com/claude-code) que lleva tu trabajo a puerto seguro antes de que un límite de uso, tokens o presupuesto lo corte a media tarea, para que un corte en seco nunca te cueste más que el último paso pequeño.

[English](README.md)

## El problema

Estás metido en una sesión larga, quizá con varios agentes en segundo plano, y topas con un límite duro: la cuota semanal, un presupuesto de tokens, un límite de ritmo. Todo lo que no está guardado se pierde. Los agentes que ya habían hecho commit y push sobreviven. Los que estaban a media faena desaparecen con su contexto, y después ni siquiera puedes saber hasta dónde llegó cada uno.

## La idea

Dos mitades, las dos necesarias:

- **Prevención.** El trabajo hace commit y push en cuanto cada pieza está lista, así un corte en cualquier instante pierde como mucho el trocito en curso.
- **Reacción.** Cuando el límite está cerca, parar a propósito: guardar todo, dejar un traspaso listo para retomar, y no dejar nada a medio guardar.

`safe-harbor` es la segunda mitad, y te empuja hacia la primera.

## Qué hace

Cuando la ejecutas:

1. Deja de lanzar trabajo nuevo.
2. Hace inventario de lo hecho, lo que está en marcha y lo que está en cola.
3. Guarda todo: commit, push y PR de lo terminado; estado parcial de lo que estaba a medias.
4. Escribe un documento `HANDOFF` en un sitio durable, con el estado actual, las PRs abiertas, dónde se paró cada tarea en marcha, y el comando exacto para retomar.
5. Actualiza la memoria a largo plazo si la sesión tiene.
6. Limpia el estado temporal y las tareas en segundo plano, pero solo después de haber guardado el trabajo.
7. Reporta qué entró, qué queda y cómo seguir.

## Instalar

Copia la skill a tu carpeta de skills de Claude Code:

```bash
git clone https://github.com/iulian640/claude-safe-harbor
mkdir -p ~/.claude/skills/safe-harbor
cp claude-safe-harbor/SKILL.md ~/.claude/skills/safe-harbor/
cp -r claude-safe-harbor/references ~/.claude/skills/safe-harbor/
```

O ejecuta `./install.sh` desde el repo clonado.

## Uso

Actívala pidiéndolo, con las palabras que te salgan:

- "cierra con cuidado, estamos cerca del límite"
- "guarda el progreso antes de que se acabe"
- `/safe-harbor`

También puedes darle un tope por adelantado ("quédate por debajo del 90% esta semana", "gástate como mucho 500k tokens en esto") y dimensionará el trabajo para caber y llegar a puerto sola antes del tope.

## Cómo hacer que se dispare de verdad

Instalar la skill le da a Claude el procedimiento. No hace que lo ejecute solo. Dos pasos cierran ese hueco:

1. **Conviértela en instrucción permanente.** Añade una línea a tu `CLAUDE.md` (global o por proyecto):

   > Ejecuta siempre la skill safe-harbor al cerrar una sesión o al acercarte a un límite de uso, tokens o presupuesto.

   Eso la pasa de "disponible si la pides" a "se ejecuta por defecto".

2. **Dale un disparador con el que pueda actuar.** La skill no puede leer tu consumo en vivo, así que dale un tope al empezar el trabajo caro: "quédate por debajo del 90% esta semana" o "gástate como mucho 500k tokens en esto". Claude dimensiona el trabajo para caber y llega a puerto antes del tope.

Como red de seguridad mecánica al terminar la sesión, también puedes montar un hook `Stop` que haga commit y push de lo que quede suelto. Es opcional; la línea en `CLAUDE.md` más un presupuesto cubren el caso común.

3. **Deja que estime su propio consumo (opcional).** `scripts/usage.py` lee tus transcripts locales de Claude Code, pondera los tokens por modelo y los escala contra una calibración que tomas de tu `/usage` real. Ejecuta `python scripts/usage.py calibrate <porcentaje>` una vez, y luego `python scripts/usage.py estimate` cuando quieras para tener un % aproximado y una señal de disparo. Solo ve esta máquina y es un aviso conservador, no un marcador exacto, pero permite que la skill se dispare sola en vez de esperar a que te des cuenta.

## Por qué no es totalmente automática

Una skill no puede vigilar tu consumo y cortar la corriente sola. No es un proceso en segundo plano, y la cuota semanal vive en el servidor sin una lectura fiable en vivo desde dentro de una sesión. Así que `safe-harbor` se dispara con tu señal o con un presupuesto que tú marcas, no con un vigilante de porcentaje. Junto con un trabajo que va guardándose sobre la marcha, donde un corte casi no cuesta nada, llegas al mismo resultado sin depender de un vigilante que no puede existir.

## Licencia

MIT. Ver [LICENSE](LICENSE).
