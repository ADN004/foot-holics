/**
 * Vercel Serverless Function — HLS-aware CORS Proxy
 * Route: /api/proxy?url=ENCODED_TARGET_URL
 *
 * For HLS manifests (.m3u8): rewrites all relative URIs to absolute CDN URIs
 * so HLS.js resolves segments correctly regardless of proxy base URL.
 * For binary segments (.ts etc.): streams through as-is with CORS headers.
 */

/**
 * Rewrite relative URIs inside an HLS playlist to absolute URLs.
 * Handles: segment URI lines, #EXT-X-KEY URI=, #EXT-X-MAP URI=,
 *          #EXT-X-MEDIA URI=, variant stream URI lines.
 */
function rewriteM3U8(text, baseUrl) {
    const base = new URL(baseUrl);

    // Rewrite URI="..." attributes in tag lines
    const rewrittenTags = text.replace(/(URI=")([^"]+)(")/g, (match, pre, uri, post) => {
        if (/^https?:\/\//i.test(uri)) return match;
        try { return pre + new URL(uri, base).href + post; }
        catch { return match; }
    });

    // Rewrite bare URI lines (lines that don't start with # and aren't empty)
    return rewrittenTags.split('\n').map(line => {
        const t = line.trim();
        if (t === '' || t.startsWith('#')) return line;
        if (/^https?:\/\//i.test(t)) return line;  // already absolute
        try { return new URL(t, base).href; }
        catch { return line; }
    }).join('\n');
}

function isM3U8(contentType, url) {
    if (contentType && /mpegurl/i.test(contentType)) return true;
    return /\.m3u8(\?|#|$)/i.test(url);
}

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

    if (!/^https?:\/\//i.test(targetUrl)) {
        return res.status(400).json({ error: 'Only http/https URLs are allowed' });
    }

    // Prevent proxying our own domain (avoids infinite loops / SSRF)
    try {
        const target = new URL(targetUrl);
        if (target.hostname.endsWith('footholics.in')) {
            return res.status(400).json({ error: 'Cannot proxy own domain' });
        }
    } catch {
        return res.status(400).json({ error: 'Invalid URL' });
    }

    try {
        const upstream = await fetch(targetUrl, {
            method: 'GET',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                // No Origin header — server-side requests bypass CDN CORS checks
            },
            redirect: 'follow',
        });

        const ct = upstream.headers.get('content-type') || 'application/octet-stream';

        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
        res.setHeader('Cache-Control', 'no-cache');

        if (isM3U8(ct, targetUrl)) {
            // HLS manifest: rewrite all relative URIs → absolute CDN URIs
            // This prevents HLS.js from resolving segments against our proxy URL
            const text = await upstream.text();
            const rewritten = rewriteM3U8(text, upstream.url || targetUrl);
            res.setHeader('Content-Type', 'application/vnd.apple.mpegurl');
            return res.status(upstream.status).send(rewritten);
        } else {
            // Binary segment / key / other — stream through as-is
            const body = await upstream.arrayBuffer();
            res.setHeader('Content-Type', ct);
            return res.status(upstream.status).send(Buffer.from(body));
        }
    } catch (err) {
        console.error('[proxy] fetch error:', err.message);
        return res.status(502).json({ error: 'Upstream fetch failed', detail: err.message });
    }
}
