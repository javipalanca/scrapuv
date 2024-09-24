import time
import pandas as pd
import csv
import asyncio  # Importar asyncio
from selenium import webdriver
from bs4 import BeautifulSoup
from telegram import Bot  # Asegúrate de importar Bot desde telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # Cambiamos el scheduler

# Configuración de tu bot de Telegram
TELEGRAM_TOKEN = '7991974992:AAGgG5dsltxIIsGcwgRNJOcub5giRaZhBqc'
TELEGRAM_CHAT_ID = '12011'
bot = Bot(token=TELEGRAM_TOKEN)

# Configuración de Selenium
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Ejecutar en modo headless
options.add_argument('--no-sandbox')  # Necesario para Docker
options.add_argument('--disable-dev-shm-usage')  # Para evitar problemas de memoria compartida
options.add_argument('--disable-gpu')  # Deshabilitar GPU (no es necesario para headless)
options.add_argument('--window-size=1920x1080')  # Define el tamaño de la ventana si es necesario

driver = webdriver.Chrome(options=options)

# URL base para la primera página
base_url = "https://webges.uv.es/uvTaeWeb/VisualizarEdictoPublicoFrontAction.do"
params = {
    'opcionTipoEdicto': '49',
    'descripcion': '',
    'esHistorico': 'false',
    'fechaPublicacionInicio': '',
    'titulo': '',
    'fechaPublicacionFin': '',
    'opcionTipoCentro': 'D',
    'opcionOrganismoExterno': '-1',
    'numeroExpediente': '',
    'opcionCentro': 'D240',
    'd-2486328-p': 1  # Página inicial
}

def build_url(page_number):
    params['d-2486328-p'] = page_number
    return base_url + "?" + "&".join([f"{key}={value}" for key, value in params.items()])

def scrape_page(page_number):
    url = build_url(page_number)
    driver.get(url)
    time.sleep(3)  # Espera para asegurar que la página esté completamente cargada

    # Obtener el contenido de la página
    html = driver.page_source
    soup = BeautifulSoup(html, 'lxml')

    anuncios = []
    table = soup.find('table', id='nuevaListaPublicados')
    if not table:
        return []

    rows = table.find_all('tr', class_=['FilaImpar', 'FilaPar'])

    for row in rows:
        columns = row.find_all('td')
        if len(columns) > 0:
            titulo = columns[0].get_text(strip=True).replace("\n", " ").replace("\r", " ").replace(",", " ")
            enlace = columns[0].find('a')['href'] if columns[0].find('a') else None
            tipo = columns[1].get_text(strip=True).replace("\n", " ").replace("\r", " ").replace(",", " ")
            procedencia = columns[2].get_text(strip=True).replace("\n", " ").replace("\r", " ").replace(",", " ")
            fecha_publicacion = columns[3].get_text(strip=True).replace("\n", " ").replace("\r", " ").replace(",", " ")

            if "informàtica" in procedencia.lower():
                url_detalle = f"https://webges.uv.es{enlace}" if enlace else None

                anuncios.append({
                    'Título': titulo,
                    'Tipo': tipo,
                    'Procedencia': procedencia,
                    'Fecha Publicación': fecha_publicacion,
                    'URL Detalle': url_detalle
                })
    return anuncios

async def send_telegram_message(message):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

async def check_for_new_offers():
    all_anuncios = []
    page = 1

    while True:
        anuncios = scrape_page(page)
        if not anuncios:
            break
        all_anuncios.extend(anuncios)
        print(f"Página {page} procesada.")
        page += 1
        time.sleep(2)  # Evitar hacer demasiadas solicitudes rápidas

    # Cargar datos existentes del CSV
    try:
        df_existing = pd.read_csv('anuncios_pdi_informatica.csv')
    except FileNotFoundError:
        df_existing = pd.DataFrame(columns=['Título', 'Tipo', 'Procedencia', 'Fecha Publicación', 'URL Detalle'])

    # Convertir a DataFrame y encontrar nuevas ofertas
    df_new = pd.DataFrame(all_anuncios)
    df_combined = pd.concat([df_existing, df_new]).drop_duplicates(subset=['Título'], keep=False)

    if not df_combined.empty:
        # Guardar los nuevos anuncios en el CSV
        df_updated = pd.concat([df_existing, df_combined]).drop_duplicates(subset=['Título'])
        df_updated.to_csv('anuncios_pdi_informatica.csv', index=False, encoding='utf-8', quoting=csv.QUOTE_ALL)

        # Enviar notificaciones de Telegram para los nuevos anuncios
        for _, row in df_combined.iterrows():
            mensaje = (f"Nuevo anuncio:\n\n"
                       f"Título: {row['Título']}\n"
                       f"Tipo: {row['Tipo']}\n"
                       f"Procedencia: {row['Procedencia']}\n"
                       f"Fecha Publicación: {row['Fecha Publicación']}\n"
                       f"URL Detalle: {row['URL Detalle']}")
            await send_telegram_message(mensaje)

        print("Se han encontrado nuevas ofertas y se han enviado notificaciones.")
    else:
        print("No hay nuevas ofertas.")

# Configurar APScheduler para ejecutar el trabajo cada hora con AsyncIOScheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(check_for_new_offers, 'interval', hours=1)

# Iniciar el loop de eventos asíncrono
async def main():

    # Ejecutar la verificación al inicio
    await check_for_new_offers()

    print("El bot de ofertas de trabajo está en funcionamiento...")
    scheduler.start()
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        driver.quit()
        print("Bot detenido")

# Ejecutar el script de forma asíncrona
asyncio.run(main())
