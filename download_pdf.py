import os
import sys
import time
import re
from playwright.sync_api import sync_playwright
import pymupdf  # Deprecation warning এড়াতে pymupdf ব্যবহার করা হয়েছে

def fix_drive_url(url):
    # open?id=LINK কে ডাইরেক্ট preview URL-এ পরিবর্তন
    match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/file/d/{file_id}/preview"
    return url

def download_drive_view_only_pdf(drive_url, output_pdf_name="downloaded_doc.pdf"):
    target_url = fix_drive_url(drive_url)
    print(f"[+] প্রসেস করা URL: {target_url}")
    
    print("[+] Browser শুরু হচ্ছে...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1400, "height": 2000},
            device_scale_factor=2
        )
        page = context.new_page()

        print(f"[+] পেজ লোড করা হচ্ছে...")
        page.goto(target_url, wait_until="domcontentloaded")
        time.sleep(7) # প্রাথমিক লোডিং সম্পন্ন হওয়ার জন্য অপেক্ষা

        print("[+] পেজগুলো লোড করার জন্য স্ক্রোলিং হচ্ছে...")
        # একাধিক উপায়ে স্ক্রোল ট্রিগার করা
        for _ in range(35):
            page.mouse.wheel(0, 1000)
            page.keyboard.press("PageDown")
            time.sleep(0.4)

        time.sleep(2)

        # একাধিক সিলেক্টর দিয়ে পেজ বা ক্যানভাস খোঁজা
        elements = page.query_selector_all('canvas')
        if not elements:
            elements = page.query_selector_all('img.drive-viewer-paginated-page-image')
        if not elements:
            elements = page.query_selector_all('.drive-viewer-page')

        print(f"[+] মোট পেজ/ইমেজ পাওয়া গেছে: {len(elements)}")

        if len(elements) == 0:
            print("[-] কোনো পেজ পাওয়া যায়নি! ফাইলটির Access 'Anyone with the link' আছে কি না চেক করুন।")
            browser.close()
            sys.exit(1)

        image_files = []
        for index, element in enumerate(elements):
            element.scroll_into_view_if_needed()
            time.sleep(0.8)  # রেন্ডারিং নিশ্চিত করার জন্য
            
            img_path = f"page_{index + 1}.png"
            element.screenshot(path=img_path)
            image_files.append(img_path)
            print(f"  └─ পেজ {index + 1} ক্যাপচার সম্পন্ন।")

        browser.close()

    # ইমেজ থেকে PDF তৈরি
    print("[+] PDF একত্রিত করা হচ্ছে...")
    doc = pymupdf.open()
    for img in image_files:
        imgdoc = pymupdf.open(img)
        pdfbytes = imgdoc.convert_to_pdf()
        imgpdf = pymupdf.open("pdf", pdfbytes)
        doc.insert_pdf(imgpdf)
        imgdoc.close()
        imgpdf.close()
        os.remove(img)

    doc.save(output_pdf_name)
    doc.close()
    print(f"[✔] সফলভাবে PDF ডাউনলোড হয়েছে: {output_pdf_name}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ব্যবহার: python download_pdf.py <GOOGLE_DRIVE_URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    download_drive_view_only_pdf(url)
