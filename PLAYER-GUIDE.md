# FootHolics Custom Branded Player Guide

## Overview

This custom branded video player displays your **FOOTHOLICS.IN** branding on all streams, even when embedded by others. It works similarly to the HelloSports.live player prototype.

## Features

✅ **Persistent Branding**: Blinking "LIVE • FOOTHOLICS.IN" watermark
✅ **Custom Thumbnail**: Branded overlay before stream starts
✅ **Base64 Stream URLs**: Secure URL encoding
✅ **Anti-Hotlinking**: Displays your branding even when embedded elsewhere
✅ **HLS Support**: Plays .m3u8 streams via JW Player
✅ **Mobile Responsive**: Works on all devices
✅ **Right-Click Protection**: Prevents easy copying of source code

## Usage

### Basic Usage

```
https://footholics.in/player.html?get=BASE64_ENCODED_URL
```

### How to Create Stream Links

1. **Get your stream URL** (e.g., `https://example.com/stream.m3u8`)

2. **Encode it to Base64**:
   - Online tool: https://www.base64encode.org/
   - JavaScript: `btoa('https://example.com/stream.m3u8')`
   - Command line: `echo -n 'https://example.com/stream.m3u8' | base64`

3. **Create your player URL**:
   ```
   https://footholics.in/player.html?get=aHR0cHM6Ly9leGFtcGxlLmNvbS9zdHJlYW0ubTN1OA==
   ```

### Advanced Usage with Authentication

If your stream requires authentication keys:

```
https://footholics.in/player.html?get=BASE64_URL&key=AUTH_KEY&key2=AUTH_KEY2
```

**Example:**
```
https://footholics.in/player.html?get=aHR0cHM6Ly9leGFtcGxlLmNvbS9zdHJlYW0ubTN1OA==&key=12345&key2=abcde
```

## Examples

### Example 1: Simple Stream

**Original Stream URL:**
```
https://live.example.com/football/match1.m3u8
```

**Base64 Encoded:**
```
aHR0cHM6Ly9saXZlLmV4YW1wbGUuY29tL2Zvb3RiYWxsL21hdGNoMS5tM3U4
```

**Final Player URL:**
```
https://footholics.in/player.html?get=aHR0cHM6Ly9saXZlLmV4YW1wbGUuY29tL2Zvb3RiYWxsL21hdGNoMS5tM3U4
```

### Example 2: Stream with Authentication

**Original Stream URL:**
```
https://secure.example.com/stream.m3u8
```

**Base64 Encoded:**
```
aHR0cHM6Ly9zZWN1cmUuZXhhbXBsZS5jb20vc3RyZWFtLm0zdTg=
```

**Final Player URL with Keys:**
```
https://footholics.in/player.html?get=aHR0cHM6Ly9zZWN1cmUuZXhhbXBsZS5jb20vc3RyZWFtLm0zdTg=&key=mykey123&key2=secret456
```

## Embedding on Your Site

You can embed the player in an iframe:

```html
<iframe
    src="https://footholics.in/player.html?get=BASE64_URL"
    width="100%"
    height="500"
    frameborder="0"
    allowfullscreen
    allow="autoplay; fullscreen; picture-in-picture">
</iframe>
```

## Benefits of This Setup

### 1. **Brand Visibility**
- Your branding shows on every stream
- Even if others steal your player link, your brand is displayed
- Blinking watermark ensures high visibility

### 2. **SEO & Marketing**
- Anyone using your player promotes your brand
- Drives traffic back to FOOTHOLICS.IN
- Increases brand recognition

### 3. **Anti-Piracy**
- Base64 encoding makes URLs less obvious
- Right-click protection prevents easy source viewing
- Watermark can't be removed without editing code

### 4. **Professional Look**
- Custom thumbnail with your branding
- Smooth loading animations
- Error handling

## Integration with Your Site

### Update Your Match Pages

Replace your current iframe embeds with the new player:

**Old:**
```html
<iframe src="p/1-live.html?match=real-madrid"></iframe>
```

**New:**
```html
<iframe src="player.html?get=ENCODED_STREAM_URL"></iframe>
```

### Updating Your Event Pages

In your match HTML files (e.g., `2025-12-07-real-madrid-vs-celta-vigo.html`), update the stream links:

```html
<a href="player.html?get=ENCODED_STREAM_URL" class="stream-link-card">
    <span class="live-badge">LIVE</span>
    <span class="stream-link-label">LINK 1</span>
</a>
```

## Creating Stream URLs Programmatically

### JavaScript Example

```javascript
function createPlayerUrl(streamUrl, keys = {}) {
    const encodedUrl = btoa(streamUrl);
    let playerUrl = `https://footholics.in/player.html?get=${encodedUrl}`;

    if (keys.key) playerUrl += `&key=${keys.key}`;
    if (keys.key2) playerUrl += `&key2=${keys.key2}`;

    return playerUrl;
}

// Usage
const playerUrl = createPlayerUrl(
    'https://example.com/stream.m3u8',
    { key: '12345', key2: 'abcde' }
);

console.log(playerUrl);
```

### Python Example

```python
import base64

def create_player_url(stream_url, key=None, key2=None):
    encoded_url = base64.b64encode(stream_url.encode()).decode()
    player_url = f"https://footholics.in/player.html?get={encoded_url}"

    if key:
        player_url += f"&key={key}"
    if key2:
        player_url += f"&key2={key2}"

    return player_url

# Usage
player_url = create_player_url(
    'https://example.com/stream.m3u8',
    key='12345',
    key2='abcde'
)

print(player_url)
```

## Sharing Your Player

### Share Link Format

Give this template to others who want to use your player:

```
https://footholics.in/player.html?get=YOUR_BASE64_ENCODED_STREAM_URL
```

### What Happens When Others Use It

1. They embed your player link on their site
2. Your **FOOTHOLICS.IN** branding shows prominently
3. Users see your watermark and brand
4. You gain free marketing and exposure
5. Potential users visit your site

## Customization Options

### Change Branding Colors

Edit [player.html](player.html) line 35-50:

```css
.branded-watermark {
    background: #D50000;  /* Change to your color */
    color: #fff;
}
```

### Change Watermark Text

Edit [player.html](player.html) line 245:

```html
<div class="branded-watermark">
    🔴 LIVE • YOUR-BRAND.COM
</div>
```

### Add Custom Logo

Replace the logo link in [player.html](player.html) around line 380:

```javascript
logo: {
    file: 'assets/img/logos/site/logo.png',
    link: 'https://footholics.in',
    position: 'top-right'
}
```

## Troubleshooting

### Stream Not Loading

1. **Check URL encoding**: Make sure the stream URL is properly base64 encoded
2. **Verify stream URL**: Test the original URL in a regular player
3. **Check CORS**: Some streams may have CORS restrictions
4. **Try different browser**: Some browsers handle HLS differently

### Watermark Not Showing

1. Check browser console for JavaScript errors
2. Ensure CSS is loading properly
3. Clear browser cache

### Player Shows Error Message

1. Verify the base64 encoding is correct
2. Check that the stream URL is accessible
3. Try the stream URL without encoding first

## Support

For issues or questions:
- **Email**: footholicsin@gmail.com
- **Telegram**: https://t.me/+XyKdBR9chQpjM2I9
- **WhatsApp**: https://chat.whatsapp.com/KG7DBpC0BKv6bFtlzfOr2T

## License

This player is proprietary to FOOTHOLICS.IN. Unauthorized modification or removal of branding is prohibited.

---

**Last Updated**: December 2025
**Version**: 1.0
**Author**: Foot Holics Team
