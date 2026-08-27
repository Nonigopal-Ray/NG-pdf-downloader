import os
import re
import sys
import requests
import img2pdf

def extract_file_id(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match_id:
        return match_id.group(1)
    return None

def download_pdf(drive_url):
    file_id = extract_file_id(drive_url)
    if not file_id:
        print("Error: Invalid Google Drive URL.")
        sys.exit(1)

    print(f"File ID Extracted: {file_id}")
    image_files = []
    page = 1
    failed_attempts = 0

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    print("Starting fast page download...")
    
    while True:
        thumb_url = f"https://drive.google.com/thumbnail?id={file_id}&v=w2500-h3200&page={page}"
        
        try:
            response = session.get(thumb_url, timeout=15)
            
            # Check if response is valid image data
            if response.status_code == 200 and len(response.content) > 3000:
                img_name = f"page_{page}.jpg"
                with open(img_name, 'wb') as f:
                    f.write(response.content)
                
                image_files.append(img_name)
                if page % 10 == 0 or page == 1:
                    print(f"Downloaded up to Page {page}...")
                page += 1
                failed_attempts = 0  # Reset failed count on success
            else:
                failed_attempts += 1
                if failed_attempts >= 3:  # Stop immediately if 3 consecutive pages fail/end
                    print(f"\nDocument end reached. Total valid pages: {len(image_files)}")
                    break
                page += 1

        except Exception as e:
            failed_attempts += 1
            if failed_attempts >= 3:
                print(f"\nStopped fetching pages. Total pages captured: {len(image_files)}")
                break

    if not image_files:
        print("Error: No pages found. Ensure link permissions are open.")
        sys.exit(1)

    output_pdf = "output.pdf"
    print("\nMerging all images into a single PDF document...")
    
    with open(output_pdf, "wb") as f:
        f.write(img2pdf.convert(image_files))

    print(f"SUCCESS! Created PDF with {len(image_files)} pages.")

    # Clean up temporary images
    for img in image_files:
        try:
            os.remove(img)
        except:
            pass

if __name__ == "__main__":
    if len(sys.argv) > 1:
        download_pdf(sys.argv[1])
    else:
        print("Error: No Drive Link provided.")
        sys.exit(1)
