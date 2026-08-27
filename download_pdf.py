import os
import sys
import time
from playwright.sync_api import sync_playwright
import fitz  # PyMuPDF

def download_drive_view_only_pdf(drive_url, output_pdf_name="downloaded_doc.pdf"):
    print("[+] Browser শুরু হচ্ছে...")
    with sync_playwright() as p:
        # Fast load options
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 2200},
            device_scale_factor=2 # হাই রেজোলিউশনের জন্য (2x scale)
        )
        page = context.new_page()

        print(f"[+] URL লোড করা হচ্ছে: {drive_url}")
        page.goto(drive_url, wait_until="networkidle")
        
        # পেজ সঠিকভাবে লোড হওয়ার জন্য কিছুটা সময় অপেক্ষা
        time.sleep(5)

        # Scroll container খুঁজে বের করা
        scroll_selector = '.drive-viewer-scroller, div[role="document"], .docos-input-textarea'
        
        print("[+] সব পেজ লোড করার জন্য অটো-স্ক্রোল করা হচ্ছে...")
        # ডাউন-স্ক্রোল করে সব পেজ (Lazy loading) ট্রিগার করা
        for _ in range(30):
            page.keyboard.press("PageDown")
            time.sleep(0.3)

        # স্ক্রোল ব্যাক টু টপ
        page.keyboard.press("Home")
        time.sleep(1)

        # সব ক্যানভাস/পেজ এলিমেন্টগুলো ধরা (Google Drive view only ক্যানভাসে রেন্ডার করে)
        canvas_elements = page.query_selector_all('canvas')
        
        if not canvas_elements:
            # যদি ক্যানভাস সরাসরি না পাওয়া যায়, তবে ইমেজের ডিরেক্ট এলিমেন্ট খোঁজা
            canvas_elements = page.query_selector_all('.drive-viewer-paginated-page-image')

        print(f"[+] মোট পেজ/ইমেজ পাওয়া গেছে: {len(canvas_elements)}")

        if len(canvas_elements) == 0:
            print("[-] কোনো পেজ পাওয়া যায়নি! URL বা অ্যাক্সেস চেক করুন।")
            browser.close()
            sys.exit(1)

        image_files = []
        for index, element in enumerate(canvas_elements):
            element.scroll_into_view_if_needed()
            time.sleep(0.5) # রেন্ডারিং সম্পন্ন হওয়ার জন্য সামান্য পজ
            
            img_path = f"page_{index + 1}.png"
            element.screenshot(path=img_path)
            image_files.append(img_path)
            print(f"  └─ পেজ {index + 1} ক্যাপচার করা হয়েছে।")

        browser.close()

    # ইমেজগুলোকে একটি নিট PDF ফাইলে রূপান্তর
    print("[+] ক্যাপচার করা ইমেজগুলো মিলিয়ে PDF তৈরি করা হচ্ছে...")
    doc = fitz.open()
    for img in image_files:
        imgdoc = fitz.open(img)
        pdfbytes = imgdoc.convert_to_pdf()
        imgpdf = fitz.open("pdf", pdfbytes)
        doc.insert_pdf(imgpdf)
        imgdoc.close()
        imgpdf.close()
        # অস্থায়ী PNG ইমেজটি মুছে ফেলা
        os.remove(img)

    doc.save(output_pdf_name)
    doc.close()
    print(f"[✔] সফলভাবে PDF তৈরি হয়েছে: {output_pdf_name}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ব্যবহার নির্দেশিকা: python download_pdf.py <GOOGLE_DRIVE_URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    download_drive_view_only_pdf(url)
