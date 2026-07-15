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

| Sensor | Descripción | Unidad |
| --- | --- | --- |
| `sensor.hidraqua_consumo_diario` | Consumo del último día con lectura disponible. Compatible con el dashboard de Energía → Agua. Incluye el histórico en el atributo `historyConsumption`. | m³ |
| `sensor.hidraqua_ultima_lectura` | Lectura acumulada del contador. | m³ |

> **Nota:** al igual que en el portal francés, Hidraqua publica los datos con
> un retraso de al menos 24h (a veces más), según la frecuencia de telelectura
> de tu zona. La integración solo puede devolver lo que el portal ya ha
> publicado.

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
