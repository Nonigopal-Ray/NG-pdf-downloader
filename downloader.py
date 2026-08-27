import os
import time
import base64
import sys
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from reportlab.pdfgen import canvas

def download_pdf(drive_url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=chrome_options)

    try:
        print(f"Opening link: {drive_url}")
        driver.get(drive_url)
        time.sleep(5)

        # Scrolling down to render pages
        for _ in range(12):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)

        # Extract Canvas Images
        js_extract = """
        var callback = arguments[arguments.length - 1];
        var imgs = Array.from(document.querySelectorAll('img[src^="blob:"]'));
        var imgDataArray = [];

        function processImage(index) {
            if (index >= imgs.length) {
                callback(imgDataArray);
                return;
            }
            var img = imgs[index];
            var canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            imgDataArray.push(canvas.toDataURL('image/jpeg', 1.0));
            processImage(index + 1);
        }
        processImage(0);
        """
        driver.set_script_timeout(45)
        images_base64 = driver.execute_async_script(js_extract)

        if not images_base64:
            print("Error: No images extracted.")
            return

        pdf_path = "output.pdf"
        c = None
        for i, img_str in enumerate(images_base64):
            img_bytes = base64.b64decode(img_str.split(',')[1])
            img = Image.open(BytesIO(img_bytes))
            w, h = img.size

            if i == 0:
                c = canvas.Canvas(pdf_path, pagesize=(w, h))
            else:
                c.setPageSize((w, h))

            temp_name = f"temp_{i}.jpg"
            img.save(temp_name)
            c.drawImage(temp_name, 0, 0, w, h)
            c.showPage()
            os.remove(temp_name)

        if c:
            c.save()
            print("PDF generation complete!")

    finally:
        driver.quit()

if __name__ == "__main__":
    url = sys.argv[1]
    download_pdf(url)