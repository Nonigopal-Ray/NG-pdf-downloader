const express = require('express');
const puppeteer = require('puppeteer');
const { PDFDocument } = require('pdf-lib');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/download-progress', async (req, res) => {
    const driveUrl = req.query.url;

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
        sendProgress(5, 'সার্ভার ইঞ্জিন চালু করা হচ্ছে...');
        browser = await puppeteer.launch({
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || null,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
            headless: 'new'
        });

        const page = await browser.newPage();
        await page.setViewport({ width: 1200, height: 1600, deviceScaleFactor: 2 });

        sendProgress(15, 'ড্রাইভ ফাইল ওপেন করা হচ্ছে...');
        await page.goto(driveUrl, { waitUntil: 'networkidle2', timeout: 90000 });

        sendProgress(30, 'সবগুলো পেজ স্ক্যান করা হচ্ছে...');

        // ১. অটো-স্ক্রলিং (সব পেজ লোড নিশ্চিত করতে)
        await page.evaluate(async () => {
            const container = document.querySelector('div[role="main"]') || document.body;
            let lastHeight = 0;
            let currentHeight = container.scrollHeight;

            while (lastHeight < currentHeight) {
                lastHeight = currentHeight;
                window.scrollBy(0, 800);
                await new Promise(r => setTimeout(r, 400));
                currentHeight = container.scrollHeight;
            }
        });

        sendProgress(45, 'ডকুমেন্টের পেজ সনাক্ত করা হচ্ছে...');

        // ২. ফ্লেক্সিবল সিলেক্টর লজিক (গুগলের ক্লাস পরিবর্তন হলেও কাজ করবে)
        let pageNodes = await page.$$('div[role="option"]');
        
        if (pageNodes.length === 0) {
            pageNodes = await page.$$('div[class*="g3VI9"]');
        }
        if (pageNodes.length === 0) {
            pageNodes = await page.$$('.drive-viewer-page, .ndfHFb-c4CoJf-g3VI9-wzpB63');
        }

        const pdfDoc = await PDFDocument.create();

        // ৩. পেজ খুঁজে পাওয়া গেলে পেজ বাই পেজ স্ক্রিনশট মোড
        if (pageNodes.length > 0) {
            const totalPages = pageNodes.length;
            sendProgress(50, `মোট ${totalPages} টি পেজ সনাক্ত হয়েছে। প্রসেসিং চলছে...`);

            for (let i = 0; i < totalPages; i++) {
                await pageNodes[i].scrollIntoView();
                await new Promise(r => setTimeout(r, 300));

                const imgBuffer = await pageNodes[i].screenshot({ type: 'jpeg', quality: 90 });
                const image = await pdfDoc.embedJpg(imgBuffer);
                
                const pdfPage = pdfDoc.addPage([image.width, image.height]);
                pdfPage.drawImage(image, { x: 0, y: 0, width: image.width, height: image.height });

                const percent = 50 + Math.round(((i + 1) / totalPages) * 45);
                sendProgress(percent, `পেজ ${i + 1}/${totalPages} প্রসেসড...`);
            }
        } else {
            // ৪. ব্যাকআপ মেকানিজম: পেজ নোড না পেলে ফুল পেজ ক্যাপচার (Fall-back)
            sendProgress(60, 'বিকল্প পদ্ধতিতে সম্পূর্ণ ফাইলটি ক্যাপচার করা হচ্ছে...');
            
            const fullScreenshot = await page.screenshot({ fullPage: true, type: 'jpeg', quality: 90 });
            const image = await pdfDoc.embedJpg(fullScreenshot);
            const pdfPage = pdfDoc.addPage([image.width, image.height]);
            pdfPage.drawImage(image, { x: 0, y: 0, width: image.width, height: image.height });
        }

        await browser.close();

        sendProgress(98, 'PDF ফাইল সংকলন করা হচ্ছে...');
        const pdfBytes = await pdfDoc.save();
        const base64Pdf = Buffer.from(pdfBytes).toString('base64');

        res.write(`data: ${JSON.stringify({ status: 'completed', pdfBase64: base64Pdf })}\n\n`);
        res.end();

    } catch (error) {
        if (browser) await browser.close();
        res.write(`data: ${JSON.stringify({ status: 'error', message: error.message })}\n\n`);
        res.end();
    }
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
