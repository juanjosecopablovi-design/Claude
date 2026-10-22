# Puente Gemini

Conecta tu cuenta de Gemini (API de Google) con Claude Desktop y Cowork. Tiene dos piezas:

| Pieza | Qué hace | Dónde está |
|---|---|---|
| Extensión `gemini.mcpb` | Servidor MCP local que guarda tu clave y llama a la API de Gemini. Añade las herramientas `ask_gemini` y `list_gemini_models`. | `dist/gemini.mcpb` (código en `extension/`) |
| Artefacto «Puente Gemini» | Chat con Gemini: fuentes de la búsqueda, aviso de sentencias y normas por verificar, y revisión cruzada con Claude. | https://claude.ai/artifact/V2M8xqTa2CBgXCKr1G8GZk (código en `artefacto/`) |

Un artefacto no puede llamar a servidores externos por sí solo, así que la conexión con Google pasa por la extensión local.

## Antes de empezar: suscripción y API son cosas distintas

La suscripción Google AI Pro (la app de Gemini) **no incluye** el uso de la API. Según la página oficial de planes de Google, los beneficios del plan aplican solo dentro de la interfaz web de Google AI Studio, y el uso directo de la API (con claves o aplicaciones externas) se factura y gestiona por separado:
https://ai.google.dev/gemini-api/docs/google-ai-plans

Por eso necesitas una **clave de API** propia. Sus cuotas y precios son los de la API de Gemini, no los de tu suscripción.

## Instalación (una sola vez)

1. **Crea la clave** en Google AI Studio: https://aistudio.google.com/apikey
2. **Instala la extensión** en la app de escritorio de Claude: Configuración → Extensiones → Instalar extensión, y elige `dist/gemini.mcpb`. Pega la clave cuando te la pida. Claude Desktop trae su propio Node.js, así que no tienes que instalar nada más.
3. **Abre el artefacto** desde la app de escritorio de Claude y pulsa **Conectar con Gemini**. La app te pedirá permiso la primera vez.
4. Fija el artefacto en tu barra lateral para tenerlo a mano desde cualquier conversación.

## Uso

- **Desde el artefacto:** escribe la consulta, elige el modelo y, si quieres fuentes, marca «Buscar en Google y citar fuentes». Cada respuesta muestra cuántas referencias normativas o jurisprudenciales detectó para que las verifiques, y el botón «Contrastar con Claude» le pide a Claude una revisión crítica.
- **Desde un chat:** con la extensión activa, en los chats de la app de escritorio puedes escribir, por ejemplo, «Pregúntale a Gemini qué opina de esta cláusula» o «Envíale a Gemini el archivo ~/Documentos/contrato.pdf y pídele un resumen». Claude usará la herramienta `ask_gemini`. Que Cowork vea las extensiones depende de la versión de la app y de la configuración de tu organización.

## Límites

- Adjuntos desde el artefacto: unos 500 KB por consulta (PDF, imágenes o texto). Para archivos más grandes, pide la consulta en un chat indicando la ruta del archivo: la extensión lo lee de tu equipo (hasta 18 MB).
- Cada consulta tiene un tiempo máximo de 2 minutos.
- El artefacto solo llega a Gemini cuando lo abres dentro de la app de escritorio de Claude. En el navegador muestra la guía de conexión.
- Las consultas del artefacto se guardan solo en tu navegador. Los adjuntos no se guardan.

## Privacidad

- La clave se guarda en el almacén seguro de Claude Desktop y solo se envía a `generativelanguage.googleapis.com`.
- El texto de tus consultas y los adjuntos van a Google según los términos de la API de Gemini que aceptaste al crear la clave.

## Configuración manual (alternativa sin el paquete)

Si prefieres no usar el `.mcpb`, necesitas Node.js 18 o superior y añadir esto a `claude_desktop_config.json`. El nombre del servidor debe ser `gemini` para que el artefacto lo encuentre:

```json
{
  "mcpServers": {
    "gemini": {
      "command": "node",
      "args": ["/ruta/a/puente-gemini/extension/server/index.js"],
      "env": {
        "GEMINI_API_KEY": "tu-clave",
        "GEMINI_MODEL": "gemini-3.1-pro-preview"
      }
    }
  }
}
```

## Volver a empaquetar la extensión

```bash
npx @anthropic-ai/mcpb validate extension/manifest.json
npx @anthropic-ai/mcpb pack extension dist/gemini.mcpb
```
