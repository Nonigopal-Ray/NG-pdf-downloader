import sys
import re
import requests

def download_drive_pdf(url, output_path="downloaded_doc.pdf"):
    # File ID খুঁজে বের করা
    file_id_match = re.search(r'(?:id=|\/d\/|\/file\/d\/)([a-zA-Z0-9_-]+)', url)
    
    if not file_id_match:
        print("[-] ভুল URL! সঠিক Google Drive লিংক দিন।")
        sys.exit(1)
        
    file_id = file_id_match.group(1)
    
    # View-Only ফাইলের সরাসরি PDF এক্সপোর্ট URL
    export_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    print(f"[+] File ID: {file_id}")
    print("[+] গুগল ড্রাইভ থেকে সরাসরি PDF ফাইল ডাউনলোড করা হচ্ছে...")
    
    session = requests.Session()
    response = session.get(export_url, stream=True)
    
    # যদি গুগল ড্রাইভ বড় ফাইলের জন্য 'Large file warning' দেখায়
    token = None
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            token = value
            break
            
    if token:
        export_url = f"https://drive.google.com/uc?export=download&confirm={token}&id={file_id}"
        response = session.get(export_url, stream=True)
        
    if response.status_code == 200 and 'text/html' not in response.headers.get('Content-Type', ''):
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
        print(f"[✔] সফলভাবে ডাউনলোড সম্পন্ন হয়েছে: {output_path}")
    else:
        print("[-] সরাসরি ডাউনলোড ব্যর্থ হয়েছে। বিকল্প 'PDF Viewer Print Method' চেষ্টা করা হচ্ছে...")
        # বিকল্প প্রিন্ট মেথড URL (View-only পারমিশন বাইপাস করার জন্য)
        pdf_view_url = f"https://drive.google.com/viewerng/viewer?id={file_id}&pdf=true"
        res = session.get(pdf_view_url)
        if res.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(res.content)
            print(f"[✔] বিকল্প পদ্ধতিতে PDF ডাউনলোড সফল হয়েছে: {output_path}")
        else:
            print("[-] ডাউনলোড করা সম্ভব হয়নি! ফাইলটির Share settings-এ 'Anyone with the link' আছে কি না চেক করুন।")
            sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ব্যবহার: python download_pdf.py <GOOGLE_DRIVE_URL>")
        sys.exit(1)
    
    download_drive_pdf(sys.argv[1])
