import re
import sys
import requests
import img2pdf
import os
import concurrent.futures

def extract_file_id(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match: return match.group(1)
    match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match_id: return match_id.group(1)
    return None

def download_page(file_id, page, headers):
    thumb_url = f"https://drive.google.com/thumbnail?id={file_id}&v=w2500-h3200&page={page}"
    response = requests.get(thumb_url, headers=headers)
    
    # ২০০০ বাইটের ভুল শর্তটি বাদ দিয়ে ৫০০ বাইট করা হয়েছে যাতে ফাঁকা পেজগুলোও বাদ না যায়
    if response.status_code == 200 and len(response.content) > 500:
        img_name = f"page_{page}.jpg"
        with open(img_name, 'wb') as f:
            f.write(response.content)
        return img_name
    return None

def download_pdf(drive_url):
    file_id = extract_file_id(drive_url)
    if not file_id:
        print("Error: Invalid Google Drive URL.")
        sys.exit(1)

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # পর্যায় ১: Direct Export Trick (দ্রুততম উপায়)
    print("সরাসরি ব্যাকএন্ড থেকে PDF Export করার চেষ্টা চলছে...")
    export_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    export_res = requests.get(export_url, headers=headers, stream=True)
    
    # যদি ফাইলটি রেস্ট্রিক্টেড না হয়, তবে সরাসরি PDF ডাউনলোড হবে
    if export_res.status_code == 200 and 'text/html' not in export_res.headers.get('Content-Type', ''):
        with open("output.pdf", "wb") as f:
            for chunk in export_res.iter_content(chunk_size=8192):
                f.write(chunk)
        print("সফল! Direct Export এর মাধ্যমে মাত্র কয়েক সেকেন্ডে মূল PDF ডাউনলোড হয়েছে।")
        return

    # পর্যায় ২: Multithreaded Fallback (View-Only ফাইলের জন্য)
    print("ফাইলটি রেস্ট্রিক্টেড। Multithreading-এর মাধ্যমে দ্রুত পেজ সংগ্রহ করা হচ্ছে...")
    image_files = []
    page = 1
    max_workers = 5 # একসাথে ৫টি পেজ লোড হবে, ফলে সময় ৫ গুণ কমে যাবে
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        while True:
            futures = [executor.submit(download_page, file_id, p, headers) for p in range(page, page + max_workers)]
            batch_results = [f.result() for f in futures]
            
            valid_pages = [res for res in batch_results if res is not None]
            image_files.extend(valid_pages)
            print(f"পেজ {page} থেকে {page + len(valid_pages) - 1} সফলভাবে প্রসেস হয়েছে।")
            
            if len(valid_pages) < max_workers:
                break # ব্যাচের কোনো পেজ না পাওয়া গেলে ডকুমেন্ট শেষ
            
            page += max_workers

    if image_files:
        print("সকল পেজ একত্রিত করে PDF তৈরি করা হচ্ছে...")
        with open("output.pdf", "wb") as f:
            f.write(img2pdf.convert(image_files))
        print("PDF successfully created!")

        # টেম্পোরারি ফাইল রিমুভ করা
        for img in image_files:
            try: os.remove(img)
            except: pass
    else:
        print("Error: কোনো পেজ ডাউনলোড করা সম্ভব হয়নি। পারমিশন চেক করুন।")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        download_pdf(sys.argv[1])
    else:
        print("Error: No Drive Link provided.")
        sys.exit(1)
