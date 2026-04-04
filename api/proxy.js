/**
 * Vercel Serverless Function — CORS Proxy
 * Route: /api/proxy?url=ENCODED_TARGET_URL
 *
 * Fetches the target URL server-side (no Origin header sent),
 * then adds CORS headers so the browser can read the response.
 * Used by universal-player.html to bypass CDN CORS restrictions.
 */
export default async function handler(req, res) {
    // Handle preflight
    if (req.method === 'OPTIONS') {
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', '*');
        return res.status(200).end();
    }

    const targetUrl = req.query.url;

    if (!targetUrl) {
        return res.status(400).json({ error: 'Missing ?url= parameter' });
    }

    // Only allow http(s) URLs to prevent SSRF against internal network
    if (!/^https?:\/\//i.test(targetUrl)) {
        return res.status(400).json({ error: 'Only http/https URLs are allowed' });
    }

    try {
        const upstream = await fetch(targetUrl, {
            method: req.method,
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                // Do NOT forward Origin — server-side requests have none, which lets CDNs pass them
            },
            redirect: 'follow',
        });

        const body = await upstream.arrayBuffer();

        // Forward content-type so HLS.js knows it's an m3u8 or a TS segment
        const ct = upstream.headers.get('content-type') || 'application/octet-stream';

        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
        res.setHeader('Content-Type', ct);
        res.setHeader('Cache-Control', 'no-cache');

        return res.status(upstream.status).send(Buffer.from(body));
    } catch (err) {
        console.error('[proxy] fetch error:', err.message);
        return res.status(502).json({ error: 'Upstream fetch failed', detail: err.message });
    }
}
