const http = require('http');
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

// Simple static server for the watson-glaser-trainer directory
function createServer(rootDir, port = 8080) {
  return http.createServer((req, res) => {
    try {
      let reqPath = decodeURI(req.url.split('?')[0]);
      if (reqPath === '/') reqPath = '/advanced.html';
      const filePath = path.join(rootDir, reqPath);
      const safePath = path.normalize(filePath);
      if (!safePath.startsWith(rootDir)) {
        res.statusCode = 403;
        res.end('Forbidden');
        return;
      }

      fs.stat(safePath, (err, stats) => {
        if (err) {
          res.statusCode = 404;
          res.end('Not found');
          return;
        }

        if (stats.isDirectory()) {
          res.statusCode = 403;
          res.end('Forbidden');
          return;
        }

        const rs = fs.createReadStream(safePath);
        const ext = path.extname(safePath).toLowerCase();
        const mime = {
          '.html': 'text/html',
          '.js': 'application/javascript',
          '.css': 'text/css',
          '.json': 'application/json',
          '.png': 'image/png',
          '.jpg': 'image/jpeg',
          '.svg': 'image/svg+xml'
        }[ext] || 'application/octet-stream';
        res.setHeader('Content-Type', mime + '; charset=utf-8');
        rs.pipe(res);
      });
    } catch (e) {
      res.statusCode = 500;
      res.end('Server error');
    }
  }).listen(port);
}

(async () => {
  const root = path.resolve(__dirname, '..'); // watson-glaser-trainer
  const port = 8080;
  console.log('Starting static server for', root, 'on port', port);
  const server = createServer(root, port);

  // Helper to replace deprecated waitForTimeout
  const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  // Ensure screenshots dir exists
  const outDir = path.join(__dirname, 'screenshots');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const baseUrl = `http://localhost:${port}`;
  const advUrl = `${baseUrl}/advanced.html`;
  const wrapperUrl = `${baseUrl}/iframe_wrapper.html`;

  const browser1 = await puppeteer.launch({ 
    headless: 'new', 
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--no-zygote',
      '--single-process',
      '--disable-gpu'
    ],
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined
  });
  const page1 = await browser1.newPage();
  page1.on('pageerror', err => console.error('Browser1 pageerror:', err));
  page1.on('error', err => console.error('Browser1 error:', err));
  page1.on('console', msg => console.log('Browser1 console:', msg.text()));
  try {
    console.log('Browser1: navigating to', advUrl);
    await page1.goto(advUrl, { waitUntil: 'networkidle2', timeout: 20000 });
    await page1.waitForSelector('#agentSelector', { timeout: 10000 });

    // choose an agent and start evolution
    await page1.select('#agentSelector', 'intermediate-researcher'); // Intermediate Researcher
    await delay(1000);
    
    // Click start button to begin evolution
    await page1.click('#startBtn');
    console.log('Browser1: Evolution started');
    
    // wait for cycles to increase
    await page1.waitForFunction(() => parseInt(document.getElementById('cycleCount').textContent, 10) > 0, { timeout: 20000 });
    await delay(2000);
    
    // wait for more cycles
    await page1.waitForFunction(() => parseInt(document.getElementById('cycleCount').textContent, 10) > 1, { timeout: 20000 });
    await delay(2000);

    const shot1 = path.join(outDir, 'browser1.png');
    await page1.screenshot({ path: shot1, fullPage: true });
    console.log('Browser1: Screenshot saved to', shot1);
    
    // stop evolution
    await page1.click('#startBtn'); // Toggle button stops when running
    await delay(500);
  } catch (err) {
    console.error('Browser1 error:', err.message);
  } finally {
    await browser1.close();
  }

  // Browser within a browser: load wrapper page containing an iframe
  const browser2 = await puppeteer.launch({ 
    headless: 'new', 
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--no-zygote',
      '--single-process',
      '--disable-gpu'
    ],
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined
  });
  const page2 = await browser2.newPage();
  page2.on('pageerror', err => console.error('Browser2 pageerror:', err));
  page2.on('error', err => console.error('Browser2 error:', err));
  page2.on('console', msg => console.log('Browser2 console:', msg.text()));
  try {
    console.log('Browser2: navigating to wrapper', wrapperUrl);
    await page2.goto(wrapperUrl, { waitUntil: 'networkidle2', timeout: 20000 });

    // wait for the iframe to load the advanced.html
    await page2.waitForSelector('iframe#tisFrame', { timeout: 10000 });
    await delay(1000); // Give iframe time to fully load
    
    // get the frame
    let frame = page2.frames().find(f => f.url().endsWith('/advanced.html'));
    if (!frame) {
      // sometimes frame.url() is relative; find by name
      const frames = page2.frames();
      for (const f of frames) {
        if (f.url().includes('advanced.html')) {
          frame = f;
          break;
        }
      }
    }

    if (!frame) {
      throw new Error('TIS iframe not found');
    }

    // Interact inside the frame
    await frame.waitForSelector('#agentSelector', { timeout: 10000 });
    await frame.select('#agentSelector', 'emerging-expert'); // Emerging Expert
    await delay(1000);
    
    // Start evolution in iframe
    await frame.click('#startBtn');
    console.log('Browser2: Evolution started in iframe');
    
    // wait for cycles to increase
    await frame.waitForFunction(() => parseInt(document.getElementById('cycleCount').textContent, 10) > 0, { timeout: 20000 });
    await delay(2000);

    // wait for more cycles
    await frame.waitForFunction(() => parseInt(document.getElementById('cycleCount').textContent, 10) > 1, { timeout: 20000 });
    await delay(2000);

    const shot2 = path.join(outDir, 'browser2_iframe.png');
    await page2.screenshot({ path: shot2, fullPage: true });
    console.log('Browser2: Screenshot saved to', shot2);
    
    // stop evolution in iframe
    await frame.click('#startBtn'); // Toggle button
    await delay(500);
  } catch (err) {
    console.error('Browser2 error:', err.message);
  } finally {
    await browser2.close();
  }

  server.close(() => {
    console.log('Static server stopped.');
  });

  console.log('Puppeteer tests finished. Screenshots placed in', outDir);
  process.exit(0);
})();