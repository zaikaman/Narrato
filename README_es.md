# Narrato: El Narrador Multimedial Potenciado por IA

<p align=\"center\"> 
  <img src=\"./narrato/static/images/logo-text.png\" alt=\"Narrato Logo\" width=\"400\"/>
</p>

<p align=\"center\"> 
  <a href=\"https://narrato-9ab718a4ca8c.herokuapp.com/\" target=\"_blank\"> 
    <img src=\"https://img.shields.io/badge/Live-Demo-brightgreen?style=for-the-badge&logo=heroku\" alt=\"Demostración en Vivo\"/> 
  </a> 
  <img src=\"https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python\" alt=\"Versión de Python\"/> 
  <img src=\"https://img.shields.io/badge/Framework-Flask-orange?style=for-the-badge&logo=flask\" alt=\"Framework Flask\"/> 
  <img src=\"https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge\" alt=\"Licencia\"/> 
</p>

**Narrato** es una aplicación web mágica que trae tus ideas a la vida generando, ilustrando y narrando automáticamente historias completas a partir de un único prompt. Utilizando una potente cadena de modelos de IA generativa, crea una experiencia de narración rica y multisentido.

> **Nota:** La demostración en vivo está alojada en una instancia gratuita de Heroku y puede ser lenta o no estar disponible en algunos momentos debido al intensivo proceso de generación de IA.

## ✨ Características

-   **✍️ Generación de historias con IA:** Aprovecha Gemini de Google para escribir historias envolventes y creativas.
-   **🎨 Ilustraciones impulsadas por IA:** Genera imágenes hermosas y consistentes para cada párrafo usando un Hugging Face Space y una canalización de análisis de personajes inteligente.
-   **🎤 Narración con IA:** Convierte el texto de la historia en una narración de audio de alta calidad usando la API de Speechify.
-   **🤖 Canal de consistencia inteligente:** Un proceso de IA único y de múltiples pasos que analiza la historia para crear una \"Base de Datos de Personajes\" y una \"Guía de Estilo\", asegurando la consistencia visual a través de todas las ilustraciones.
-   **🔐 Autenticación de usuarios:** Inicio de sesión seguro sin contraseña mediante OTP enviados por correo, impulsado por Shov.com.
-   **📚 Biblioteca de historias:** Los usuarios pueden ver su historial de historias y explorar historias públicas creadas por otros.
-   **📤 Exportación a PDF:** Exporta tus historias favoritas a un libro PDF bellamente formateado, con ilustraciones incluidas.
-   **⚙️ Progreso de transmisión en vivo:** La generación de historias ocurre en una única solicitud HTTP de larga duración, transmitiendo el progreso en tiempo real a tu navegador mediante Eventos Enviados por el Servidor (SSE).

## 🛠️ Tecnologías

-   **Backend:** Python, Flask, Gunicorn
-   **Frontend:** HTML5, CSS3, JavaScript
-   **Servicios de IA:** Gemini de Google, Hugging Face, Speechify
-   **Base de datos y Almacenamiento:** Shov.com (BD clave-valor), Cloudinary (Almacenamiento de medios)
-   **Despliegue:** Heroku

## 🚀 Cómo Funciona: La Pipelines de IA

La magia de Narrato reside en su pipeline de IA de vanguardia que garantiza una salida de alta calidad y coherencia.

1.  **Prompt -> Historia:** Proporcionas un prompt. **Google Gemini** escribe una historia completa con título, párrafos y moraleja.
2.  **Historia -> Análisis:** La aplicación utiliza **Gemini** de nuevo para leer la historia generada y crear dos documentos cruciales:
    *   **Base de Datos de Personajes:** Descripciones detalladas de la apariencia, vestimenta y expresiones de cada personaje.
    *   **Guía de Estilo Artístico:** Una guía coherente para paleta de colores, iluminación y estilo artístico general.
3.  **Análisis -> Prompts de imágenes:** Con la historia, la base de datos de personajes y la guía de estilo, **Gemini** crea prompts detallados y consistentes para la IA de generación de imágenes para *cada párrafo*.
4.  **Prompts -> Imágenes:** Los prompts se envían a un **Hugging Face Space** para generar ilustraciones. Los resultados se almacenan en **Cloudinary**.
5.  **Texto -> Audio:** El título y los párrafos se envían a la **Speechify API** para generar la narración en audio, que también se almacena en **Cloudinary**.
6.  **Ensamblaje:** La historia final, con texto, imágenes y audio, se arma y se guarda en el historial del usuario usando **Shov.com**.

## 📂 Estructura del Proyecto

El proyecto está organizado en los directorios principales siguientes:

```
autoaistory/
├── narrato/
│   ├── core/              # Lógica principal de la aplicación, decoradores
│   ├── routes/            # Blueprints de Flask (auth, story, stream)
│   ├── services/          # Módulos para interactuar con APIs externas
│   ├── static/            # Recursos del frontend (CSS, JS, imágenes, tipografías)
│   └── templates/         # Plantillas HTML para la interfaz web
├── docs/                  # Documentación del proyecto
├── .env.example           # Archivo de variables de entorno de ejemplo
├── config.py              # Configuración de Flask
├── run.py                 # Punto de entrada principal para ejecutar la aplicación
├── requirements.txt       # Dependencias de Python
└── Procfile               # Archivo de procesos de Heroku
```

## 🏁 Cómo Empezar

Sigue estos pasos para ejecutar Narrato en tu máquina local.

### 1. Requisitos previos

-   Python 3.9+ 
-   Git

### 2. Clonar y Configurar

```bash
# Clonar el repositorio
git clone <tu-URL-del-repositorio>
cd autoaistory

# Crear y activar un entorno virtual
python -m venv venv
# En Windows: .\\venv\\Scripts\\activate
# En macOS/Linux: source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crea un archivo `.env` copiando el archivo `.env.example`. Luego, abre el `.env` y añade tus claves de secreto y valores de configuración. Consulta `docs/environment.md` para más detalles.

```ini
# Clave secreta de Flask para la sesión
SECRET_KEY=\"una_clave_secreta_muy_fuerte_y_aleatoria\" 

# Base de datos Shov.com
SHOV_API_KEY=\"tu_shov_api_key\" 
SHOV_PROJECT=\"tu_nombre_de_proyecto_shov\" 

# Claves de API de Google Gemini (agrega tantas como tengas) 
GOOGLE_API_KEY=\"tu_api_key_gemini\" 

# Claves de Speechify 
SPEECHIFY_KEY=\"tu_api_key_speechify\" 

# Token de Hugging Face para generación de imágenes 
HUGGING_FACE_TOKEN=\"tu_token_hugging_face\" 

# Cloudinary para almacenamiento de medios
CLOUDINARY_CLOUD_NAME=\"tu_cloudinary_cloud_name\" 
CLOUDINARY_KEY=\"tu_cloudinary_api_key\" 
CLOUDINARY_SECRET=\"tu_cloudinary_api_secret\" 
```

### 5. Ejecutar la aplicación

```bash
python run.py
```

La aplicación estará disponible en `http://127.0.0.1:8080`.

## ☁️ Despliegue

Esta aplicación está configurada para desplegarse en Heroku. El `Procfile` define el proceso `web` que sirve la aplicación usando Gunicorn.

La aplicación utiliza una arquitectura de streaming y no requiere un worker separado. Sin embargo, es crucial configurar un tiempo de espera largo (por ejemplo, 3600 segundos) para que el servidor web pueda manejar las solicitudes de larga duración para la generación de historias.

Para instrucciones detalladas, consulta la [Guía de Despliegue](./docs/deployment.md).

## 📄 Licencia

Este proyecto está licenciado bajo la MIT License.
