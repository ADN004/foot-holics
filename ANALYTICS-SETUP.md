# Analytics Setup Guide for FootHolics Player

## Overview

Your player now has Google Analytics 4 (GA4) integrated for tracking views and plays. This data is private and only visible to you.

## Setup Steps

### 1. Create Google Analytics Account

1. Go to [Google Analytics](https://analytics.google.com/)
2. Sign in with your Google account
3. Click "Start measuring"
4. Enter account details:
   - Account name: "FootHolics"
   - Check all data sharing settings (optional)

### 2. Create a Property

1. Property name: "FootHolics Player"
2. Time zone: Select your timezone
3. Currency: Select your currency
4. Click "Next"

### 3. Set Up Data Stream

1. Choose platform: **Web**
2. Website URL: `https://footholics.in`
3. Stream name: "FootHolics Web Player"
4. Click "Create stream"

### 4. Get Your Measurement ID

1. After creating the stream, you'll see your **Measurement ID**
2. It looks like: `G-XXXXXXXXXX` (e.g., `G-1A2B3C4D5E`)
3. **Copy this ID** - you'll need it next

### 5. Update Player Files

Replace `G-XXXXXXXXXX` with your actual Measurement ID in these files:

#### File 1: [player.html](player.html)
Find lines 11 and 16:
```html
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
```
and
```javascript
gtag('config', 'G-XXXXXXXXXX', {
```

Replace both instances of `G-XXXXXXXXXX` with your Measurement ID.

#### File 2: [p/footholics-player.html](p/footholics-player.html)
Same as above - replace `G-XXXXXXXXXX` with your Measurement ID.

### 6. Example

If your Measurement ID is `G-ABC123XYZ`, the code should look like:

```html
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-ABC123XYZ"></script>
<script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-ABC123XYZ', {
        'page_title': 'FootHolics Player',
        'page_path': '/player.html'
    });
</script>
```

## What Gets Tracked?

### Automatic Tracking
- **Page Views**: Every time someone opens the player
- **User Location**: Country, city (approximate)
- **Device Info**: Desktop/Mobile, browser, OS
- **Traffic Source**: Where visitors came from
- **Session Duration**: How long they stay

### Custom Events (Already Configured)
- **Video Play**: Tracks when someone plays a stream
  - Event name: `video_play`
  - Includes the stream URL
  - Value: 1 per play

## Viewing Your Analytics

### Access Dashboard
1. Go to [Google Analytics](https://analytics.google.com/)
2. Select "FootHolics Player" property
3. View reports in the left sidebar

### Key Reports to Check

#### 1. Real-Time Report
- See current active users
- Live stream plays happening now
- Current locations

#### 2. Acquisition Report
- Where your traffic comes from
- Direct, referral, social media

#### 3. Engagement Report
- Most viewed streams
- User engagement metrics
- Popular times

#### 4. Custom Events
- Go to: Reports → Engagement → Events
- Look for `video_play` event
- See which streams are most popular

## Privacy Considerations

### Your Data
- Only YOU can see this data
- Data is private to your Google Analytics account
- Not visible to website visitors

### GDPR/Privacy Compliance
- GA4 is privacy-friendly
- No personal data is collected
- Users are not identified individually

### Optional: Add Cookie Consent
If you want to be extra compliant, you can add a cookie banner:
```html
<div id="cookie-banner">
    This site uses analytics cookies to improve user experience.
    <button onclick="acceptCookies()">Accept</button>
</div>
```

## Advanced: Custom Tracking

### Track Stream URLs
The player already tracks which stream URLs are played:

```javascript
gtag('event', 'video_play', {
    'event_category': 'Player',
    'event_label': streamUrl,  // The actual stream URL
    'value': 1
});
```

You can see this in: Reports → Engagement → Events → video_play

### Add More Custom Events

You can add more tracking events. For example, track errors:

```javascript
// Add this to the player error handler
gtag('event', 'player_error', {
    'event_category': 'Error',
    'event_label': errorMessage,
    'value': 1
});
```

## Troubleshooting

### Analytics Not Working?

1. **Check Measurement ID**: Make sure you replaced `G-XXXXXXXXXX`
2. **Wait 24-48 hours**: Data may take time to appear
3. **Use Real-Time Report**: Should show data immediately
4. **Check Browser Console**: Look for errors
5. **Test in Incognito**: Some extensions block analytics

### Verify Installation

1. Open your player: `https://footholics.in/player.html?get=TEST`
2. Open browser Developer Tools (F12)
3. Go to "Network" tab
4. Filter for "google-analytics" or "gtag"
5. You should see requests being sent

### Still Not Working?

- Make sure your website is live (not localhost)
- Check if ad blockers are interfering
- Verify the Measurement ID is correct
- Wait 24 hours for data to process

## Useful Links

- [Google Analytics Dashboard](https://analytics.google.com/)
- [GA4 Documentation](https://support.google.com/analytics/answer/10089681)
- [Event Tracking Guide](https://developers.google.com/analytics/devguides/collection/ga4/events)

## Summary

Once set up, you'll be able to see:
- ✅ How many people use your player
- ✅ Which streams are most popular
- ✅ Where your traffic comes from
- ✅ Peak usage times
- ✅ Device/browser statistics
- ✅ Geographic distribution

All of this data is **private** and only visible in your Google Analytics account!

---

**Last Updated**: December 2025
**Version**: 1.0
