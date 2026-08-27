const express = require('express');
const puppeteer = require('puppeteer');
const { PDFDocument } = require('pdf-lib');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/download-progress', async (req, res) => {
    const driveUrl = req.query.url;

    // SSE Setup for Real-time Progress
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
        sendProgress(5, 'ব্রাউজার ইঞ্জিন চালু হচ্ছে...');
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
        // স্ট্যান্ডার্ড A4 সাইজ অনুপাত বজায় রাখার জন্য ভিউপোর্ট
        await page.setViewport({ width: 1200, height: 1600, deviceScaleFactor: 2 });

        sendProgress(15, 'গুগল ড্রাইভ ফাইল লোড করা হচ্ছে...');
        await page.goto(driveUrl, { waitUntil: 'networkidle2', timeout: 90000 });

        sendProgress(30, 'সবগুলো পেজ স্ক্যান ও স্ক্রল করা হচ্ছে...');

        // ১. প্রতিটি পেজ সম্পূর্ণ লোড করার জন্য ডিপ স্ক্রলিং লজিক
        await page.evaluate(async () => {
            const getScrollContainer = () => {
                return document.querySelector('div[role="main"]') || 
                       document.querySelector('.ndfHFb-c4CoJf-a91vB-wzpB63') || 
                       document.documentElement;
            };
            
            const container = getScrollContainer();
            let lastHeight = 0;
            let currentHeight = container.scrollHeight;

            // শেষ পেজ পর্যন্ত স্ক্রল নিশ্চিত করা
            while (lastHeight < currentHeight) {
                lastHeight = currentHeight;
                container.scrollBy(0, 800);
                await new Promise(r => setTimeout(r, 600)); // পেজ লোড হওয়ার জন্য ওয়েট
                currentHeight = container.scrollHeight;
            }
        });

        sendProgress(55, 'পেজের হাই-রেজোলেশন ইমেজ ডাটা বের করা হচ্ছে...');

        // ২. DOM থেকে ড্রাইভের পেজ কন্টেইনার ডিরেক্ট ফিল্টার করা
        const pageBlobs = await page.evaluate(async () => {
            // ড্রাইভের পেজ ইলিমেন্ট সিলেক্টর
            const pageElements = document.querySelectorAll('.ndfHFb-c4CoJf-g3VI9-wzpB63, div[role="option"]');
            const imagesData = [];

            for (let el of pageElements) {
                const img = el.querySelector('img');
                const canvas = el.querySelector('canvas');

                if (canvas) {
                    imagesData.push(canvas.toDataURL('image/jpeg', 0.95));
                } else if (img && img.src) {
                    imagesData.push(img.src);
                }
            }
            return imagesData;
        });

        // যদি বিশেষ কোনো ক্যানভাস বা ইমেজ না পাওয়া যায়, তবে প্রতিটি পেজ কন্টেইনারের নিখুঁত শট নেওয়া
        const pdfDoc = await PDFDocument.create();

        if (pageBlobs.length > 0) {
            sendProgress(70, `${pageBlobs.length} টি পেজ চিহ্নিত করা হয়েছে। রূপান্তর চলছে...`);
            
            for (let i = 0; i < pageBlobs.length; i++) {
                const dataUrl = pageBlobs[i];
                if (dataUrl.startsWith('data:image')) {
                    const base64Data = dataUrl.split(',')[1];
                    const imgBuffer = Buffer.from(base64Data, 'base64');
                    const image = await pdfDoc.embedJpg(imgBuffer);
                    
                    // আসল পেজ সাইজ অনুযায়ী নতুন PDF পেজ তৈরি
                    const pdfPage = pdfDoc.addPage([image.width, image.height]);
                    pdfPage.drawImage(image, { x: 0, y: 0, width: image.width, height: image.height });
                }
                const p = 70 + Math.round(((i + 1) / pageBlobs.length) * 25);
                sendProgress(p, `পেজ ${i + 1}/${pageBlobs.length} যুক্ত করা হয়েছে...`);
            }
        } else {
            // অল্টারনেট পেজ বাই পেজ স্ক্রিনশট লজিক (একটিও পেজ বাদ পড়বে না)
            const pages = await page.$$('.ndfHFb-c4CoJf-g3VI9-wzpB63');
            
            if (pages.length === 0) {
                throw new Error('ড্রাইভের পেজগুলো সনাক্ত করা যায়নি। ফাইলটি পাবলিক ভিউ মোডে আছে কিনা নিশ্চিত করুন।');
            }

            sendProgress(70, `মোট ${pages.length} টি পেজ প্রসেস করা হচ্ছে...`);

            for (let i = 0; i < pages.length; i++) {
                // পেজে ফোকাস ও স্ক্রল
                await pages[i].scrollIntoView();
                await new Promise(r => setTimeout(r, 300));

                const imgBuffer = await pages[i].screenshot({ type: 'jpeg', quality: 90 });
                const image = await pdfDoc.embedJpg(imgBuffer);
                const pdfPage = pdfDoc.addPage([image.width, image.height]);
                pdfPage.drawImage(image, { x: 0, y: 0, width: image.width, height: image.height });

                const p = 70 + Math.round(((i + 1) / pages.length) * 25);
                sendProgress(p, `পেজ ${i + 1}/${pages.length} যুক্ত করা হয়েছে...`);
            }
        }

        await browser.close();

        sendProgress(98, 'PDF ফাইল ফাইনাল ডাউনলোড করার জন্য রেডি হচ্ছে...');
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
