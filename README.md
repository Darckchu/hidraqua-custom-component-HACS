# Hidraqua (Veolia España)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Integración no oficial de Home Assistant para consultar el consumo de agua desde
el área de cliente de **Hidraqua** (`hidraqua.veolia.es`), marca de Veolia en
España para la Comunidad Valenciana.

> ⚠️ Integración no oficial, creada mediante ingeniería inversa del tráfico web
> del portal. Puede dejar de funcionar sin previo aviso si Veolia/Hidraqua
> cambia su web. Úsala bajo tu responsabilidad.

Inspirada en el proyecto original para el portal francés
[kugan49/veolia-custom-component-HACS](https://github.com/kugan49/veolia-custom-component-HACS)
(archivado) y su sucesor
[Jezza34000/homeassistant_veolia](https://github.com/Jezza34000/homeassistant_veolia).

## Sensores

| Sensor | Descripción | Unidad | ¿Válido para Energía? |
| --- | --- | --- | --- |
| `sensor.hidraqua_ultima_lectura` | Totalizador real del contador. Recibe además el histórico **horario** importado directamente en sus estadísticas. | m³ | ✅ Sí — es la fuente recomendada |
| `sensor.hidraqua_consumo_diario` | Consumo del último día con lectura disponible (valor informativo, se reinicia cada día). | m³ | ❌ No (a propósito) |

## Consumo por horas en el dashboard de Energía

El dashboard de Energía siempre lee de las **estadísticas** de la entidad
seleccionada, no de su estado en vivo. Por eso, aunque `Última lectura` solo
se actualiza cada 12h, su histórico de estadísticas se rellena por detrás con
datos **horarios** reales del portal — así que al seleccionarla como fuente
de agua, el panel pinta barras hora a hora, no solo un valor por ciclo.

- Al añadir la integración por primera vez, se cargan los últimos **30 días**
  de histórico horario.
- En cada ciclo posterior, solo se importan las horas nuevas (incremental).
- El portal permite consultar como máximo **1 año hacia atrás** en modo
  horario. Si quieres forzar una carga inicial más amplia, edita
  `INITIAL_BACKFILL_DAYS` en `statistics.py` antes de instalar.

## Añadir el consumo al dashboard de Energía

Ajustes → Energía → lápiz en "Agua" → Añadir consumo de agua → selecciona
**`sensor.hidraqua_ultima_lectura`** (no el de "Consumo diario").

> Si ya tenías configurado el sensor de "Consumo diario" como fuente de
> Energía en una versión anterior, cámbialo por "Última lectura" — es el
> correcto y además es el único que recibe el detalle horario.

## Instalación

### Vía HACS (recomendado)

1. HACS → menú ⋮ (arriba a la derecha) → **Repositorios personalizados**
2. Repositorio: `https://github.com/TU_USUARIO_GITHUB/hidraqua-custom-component-HACS`
3. Categoría: **Integración**
4. Instala la integración desde la lista de HACS
5. Reinicia Home Assistant

### Manual

1. Copia la carpeta `custom_components/hidraqua` dentro de `custom_components/` en tu configuración de Home Assistant
2. Reinicia Home Assistant

## Configuración

Ajustes → Dispositivos y servicios → Añadir integración → busca **Hidraqua**.

Introduce tu usuario (DNI/NIE) y contraseña del área de cliente.

> Si tu cuenta tiene activada la verificación en dos pasos, la integración no
> podrá completar el login todavía.

## Añadir el consumo al dashboard de Energía

Ajustes → Energía → lápiz en "Agua" → Añadir consumo de agua → selecciona
`sensor.hidraqua_consumo_diario`.

## Aviso legal

Este proyecto no está afiliado, respaldado ni soportado por Veolia ni por
Hidraqua. Utiliza endpoints internos no documentados públicamente, obtenidos
inspeccionando el tráfico del propio navegador del usuario. Puede romperse en
cualquier momento sin aviso.

## Licencia

MIT
