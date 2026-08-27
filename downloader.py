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
    try:
        response = requests.get(thumb_url, headers=headers, timeout=10)
        # Google Drive অস্তিত্বহীন পেজের ক্ষেত্রে ২০০ বাইটের চেয়ে কম সাইজের ছবি বা ৪-ও-৪ রেসপন্স দেয়
        if response.status_code == 200 and len(response.content) > 1000:
            img_name = f"page_{page:04d}.jpg" # পেজ সাজানোর সুবিধার্থে 0001, 0002 ফরম্যাট
            with open(img_name, 'wb') as f:
                f.write(response.content)
            return page, img_name
    except Exception:
        pass
    return page, None

def download_pdf(drive_url):
    file_id = extract_file_id(drive_url)
    if not file_id:
        print("Error: Invalid Google Drive URL.")
        sys.exit(1)

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # পর্যায় ১: Direct Export Trick (১০০% দ্রুততম)
    print("সরাসরি ব্যাকএন্ড থেকে PDF Export করার চেষ্টা চলছে...")
    export_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    export_res = requests.get(export_url, headers=headers, stream=True)
    
    if export_res.status_code == 200 and 'text/html' not in export_res.headers.get('Content-Type', ''):
        with open("output.pdf", "wb") as f:
            for chunk in export_res.iter_content(chunk_size=8192):
                f.write(chunk)
        print("সফল! Direct Export এর মাধ্যমে মূল PDF ডাউনলোড হয়ে গেছে।")
        return

    # পর্যায় ২: Multithreaded Fallback উইথ সঠিক Stop Condition
    print("ফাইলটি রেস্ট্রিক্টেড। পেজ-বাই-পেজ ক্যাপচার শুরু হচ্ছে...")
    
    downloaded_images = {}
    page = 1
    consecutive_failures = 0
    max_failures_allowed = 3 # টানা ৩টি পেজ না পেলে কোড নিশ্চিত হবে যে ফাইল শেষ
    max_workers = 5

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        while True:
            # ৫টি করে পেজের ব্যাচ রিকোয়েস্ট
            futures = [executor.submit(download_page, file_id, p, headers) for p in range(page, page + max_workers)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
            
            # ফলাফল পেজ নম্বর অনুযায়ী সর্ট করা
            results.sort(key=lambda x: x[0])
            
            stop_loop = False
            for p_num, img_path in results:
                if img_path:
                    downloaded_images[p_num] = img_path
                    consecutive_failures = 0 # সফল হলে ব্যর্থতার কাউন্টার ০ হবে
                    print(f"পেজ {p_num} ডাউনলোড সম্পন্ন।")
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures_allowed:
                        stop_loop = True
                        break
            
            if stop_loop:
                print(f"ডকুমেন্টের শেষ প্রান্তে পৌঁছানো গেছে। মোট পেজ পাওয়া গেছে: {len(downloaded_images)}")
                break
                
            page += max_workers

    if downloaded_images:
        # পেজ নম্বর ক্রমানুসারে সাজিয়ে নেওয়া
        sorted_image_files = [downloaded_images[k] for k in sorted(downloaded_images.keys())]
        
        print("সকল পেজ একত্রিত করে PDF তৈরি করা হচ্ছে...")
        with open("output.pdf", "wb") as f:
            f.write(img2pdf.convert(sorted_image_files))
        print("PDF successfully created!")

        # টেম্পোরারি ছবিগুলো ডিলিট করা
        for img in sorted_image_files:
            try: os.remove(img)
            except: pass
    else:
        print("Error: কোনো পেজ ডাউনলোড করা সম্ভব হয়নি।")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        download_pdf(sys.argv[1])
    else:
        print("Error: No Drive Link provided.")
        sys.exit(1)
