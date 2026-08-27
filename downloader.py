import re
import sys
import requests
import img2pdf

def extract_file_id(url):
    # Extract Google Drive File ID from URL
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
    
    # High quality fetch loop until no more pages exist
    while True:
        # Fetching maximum possible resolution per page directly from Google Drive API
        thumb_url = f"https://drive.google.com/thumbnail?id={file_id}&v=w2500-h3200&page={page}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(thumb_url, headers=headers)
        
        # Stop condition when page thumbnail does not exist or fails
        if response.status_code != 200 or len(response.content) < 2000:
            if page == 1:
                print("Error: Could not fetch pages. Ensure the file has 'Anyone with link' permission.")
                sys.exit(1)
            print(f"End of document reached. Total pages captured: {page - 1}")
            break

        img_name = f"page_{page}.jpg"
        with open(img_name, 'wb') as f:
            f.write(response.content)
            
        image_files.append(img_name)
        print(f"Page {page} downloaded successfully.")
        page += 1

    if image_files:
        output_pdf = "output.pdf"
        print("Combining all pages into single PDF...")
        with open(output_pdf, "wb") as f:
            f.write(img2pdf.convert(image_files))
        
        print("PDF successfully created!")

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
