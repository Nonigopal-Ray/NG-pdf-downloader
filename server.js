const express = require('express');
const puppeteer = require('puppeteer');
const { PDFDocument } = require('pdf-lib');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/download-progress', async (req, res) => {
    const driveUrl = req.query.url;

    // SSE Setup
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    const sendProgress = (percent, message) => {
        res.write(`data: ${JSON.stringify({ status: 'progress', percent, message })}\n\n`);
    };

    if (!driveUrl || !driveUrl.includes('drive.google.com')) {
        res.write(`data: ${JSON.stringify({ status: 'error', message: 'সঠিক গুগল ড্রাইভ লিঙ্ক দিন।' })}\n\n`);
        return res.end();
    }

    let browser;
    try {
        sendProgress(10, 'ব্রাউজার লঞ্চ করা হচ্ছে...');
        browser = await puppeteer.launch({
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || null,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
            headless: 'new'
        });

        const page = await browser.newPage();
        await page.setViewport({ width: 1400, height: 1800, deviceScaleFactor: 2 });

        sendProgress(25, 'গুগল ড্রাইভ পেজ লোড করা হচ্ছে...');
        await page.goto(driveUrl, { waitUntil: 'networkidle2', timeout: 90000 });

        sendProgress(40, 'পেজ স্ক্রলিং ও ইমেজ রেন্ডার করা হচ্ছে...');
        
        // অটো-স্ক্রলিং ফিক্স: ড্রাইভের আসল স্ক্রলেবল ডিভ স্ক্রল করা
        await page.evaluate(async () => {
            const scrollableDiv = document.querySelector('.ndfHFb-c4CoJf-a91vB-wzpB63') || document.body;
            await new Promise((resolve) => {
                let totalHeight = 0;
                const distance = 400;
                const timer = setInterval(() => {
                    const scrollHeight = scrollableDiv.scrollHeight;
                    scrollableDiv.scrollBy(0, distance);
                    totalHeight += distance;
                    if (totalHeight >= scrollHeight) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 200);
            });
        });

        sendProgress(60, 'পেজগুলোর ছবি প্রসেস করা হচ্ছে...');

        // পেজ সানিটি চেক ও স্ক্রিনশট নেওয়া (খালি পেজ ফিক্স করার সেরা উপায়)
        const pageElements = await page.$$('.ndfHFb-c4CoJf-g3VI9-wzpB63');
        const pdfDoc = await PDFDocument.create();

        if (pageElements.length === 0) {
            // বিকল্প সিলেক্টর দিয়ে ফুল পেজ স্ক্রিনশট মোড
            const screenshotBuffer = await page.screenshot({ fullPage: true, type: 'jpeg', quality: 80 });
            const image = await pdfDoc.embedJpg(screenshotBuffer);
            const pdfPage = pdfDoc.addPage([image.width, image.height]);
            pdfPage.drawImage(image, { x: 0, y: 0, width: image.width, height: image.height });
        } else {
            let processed = 0;
            for (let i = 0; i < pageElements.length; i++) {
                const element = pageElements[i];
                const imgBuffer = await element.screenshot({ type: 'jpeg', quality: 85 });
                const image = await pdfDoc.embedJpg(imgBuffer);
                const pdfPage = pdfDoc.addPage([image.width, image.height]);
                pdfPage.drawImage(image, { x: 0, y: 0, width: image.width, height: image.height });
                
                processed++;
                const currentPercent = 60 + Math.round((processed / pageElements.length) * 30);
                sendProgress(currentPercent, `পেজ ${processed}/${pageElements.length} রূপান্তর করা হচ্ছে...`);
            }
        }

        await browser.close();

        sendProgress(95, 'PDF সংকলন করা হচ্ছে...');
        const pdfBytes = await pdfDoc.save();
        const base64Pdf = Buffer.from(pdfBytes).toString('base64');

        res.write(`data: ${JSON.stringify({ status: 'completed', pdfBase64: base64Pdf })}\n\n`);
        res.end();

    } catch (error) {
        if (browser) await browser.close();
        console.error('Error:', error);
        res.write(`data: ${JSON.stringify({ status: 'error', message: error.message })}\n\n`);
        res.end();
    }
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
