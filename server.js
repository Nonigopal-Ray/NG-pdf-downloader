const express = require('express');
const puppeteer = require('puppeteer');
const { PDFDocument } = require('pdf-lib');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

app.post('/api/download', async (req, res) => {
    const { url } = req.body;
    if (!url || !url.includes('drive.google.com')) {
        return res.status(400).json({ error: 'সঠিক গুগল ড্রাইভ লিংক প্রদান করুন।' });
    }

    let browser;
    try {
        browser = await puppeteer.launch({
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || null,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ],
            headless: 'new'
        });

        const page = await browser.newPage();
        await page.setViewport({ width: 1200, height: 1600 });
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });

        // সব পেজ লোড করার জন্য অটো-স্ক্রলিং
        await page.evaluate(async () => {
            await new Promise((resolve) => {
                let totalHeight = 0;
                const distance = 300;
                const timer = setInterval(() => {
                    const scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if (totalHeight >= scrollHeight) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 150);
            });
        });

        // DOM থেকে ক্যানভাস/ইমেজ ডেটা এক্সট্রাক্ট করা
        const imgDataUrls = await page.evaluate(() => {
            const elements = Array.from(document.querySelectorAll('img, canvas'));
            const urls = [];
            elements.forEach(el => {
                if (el.tagName === 'CANVAS') {
                    try {
                        urls.push(el.toDataURL('image/png'));
                    } catch (e) {}
                } else if (el.tagName === 'IMG' && el.src) {
                    urls.push(el.src);
                }
            });
            return urls;
        });

        await browser.close();

        if (imgDataUrls.length === 0) {
            return res.status(404).json({ error: 'ডকুমেন্ট থেকে কোনো পেজ এক্সট্রাক্ট করা সম্ভব হয়নি।' });
        }

        // PDF তৈরির লজিক
        const pdfDoc = await PDFDocument.create();
        for (const dataUrl of imgDataUrls) {
            try {
                let image;
                if (dataUrl.startsWith('data:image/png')) {
                    const base64Data = dataUrl.replace(/^data:image\/png;base64,/, "");
                    const imgBuffer = Buffer.from(base64Data, 'base64');
                    image = await pdfDoc.embedPng(imgBuffer);
                } else if (dataUrl.startsWith('data:image/jpeg')) {
                    const base64Data = dataUrl.replace(/^data:image\/jpeg;base64,/, "");
                    const imgBuffer = Buffer.from(base64Data, 'base64');
                    image = await pdfDoc.embedJpg(imgBuffer);
                }

                if (image) {
                    const pdfPage = pdfDoc.addPage([image.width, image.height]);
                    pdfPage.drawImage(image, {
                        x: 0,
                        y: 0,
                        width: image.width,
                        height: image.height,
                    });
                }
            } catch (err) {
                console.error('Page embed error:', err);
            }
        }

        const pdfBytes = await pdfDoc.save();
        res.setHeader('Content-Type', 'application/pdf');
        res.setHeader('Content-Disposition', 'attachment; filename="downloaded_document.pdf"');
        return res.send(Buffer.from(pdfBytes));

    } catch (error) {
        if (browser) await browser.close();
        console.error('Processing error:', error);
        return res.status(500).json({ error: 'প্রসেস করার সময় ত্রুটি ঘটেছে: ' + error.message });
    }
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
