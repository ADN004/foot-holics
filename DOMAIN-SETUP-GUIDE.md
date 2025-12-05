# Domain Setup Guide: GoDaddy to Vercel

## 📋 Overview
This guide will help you connect your **footholics.in** domain from GoDaddy to your Vercel deployment.

---

## 🎯 Step-by-Step Instructions

### **PART 1: Vercel Setup**

#### Step 1: Log in to Vercel
1. Go to [https://vercel.com](https://vercel.com)
2. Sign in with your account

#### Step 2: Select Your Project
1. Click on your **foot-holics** project
2. Go to **Settings** tab
3. Click on **Domains** in the left sidebar

#### Step 3: Add Your Custom Domain
1. Click **Add Domain**
2. Enter: `footholics.in`
3. Click **Add**
4. Vercel will show you DNS configuration instructions

#### Step 4: Add www Subdomain (Optional but Recommended)
1. Click **Add Domain** again
2. Enter: `www.footholics.in`
3. Click **Add**

---

### **PART 2: GoDaddy DNS Configuration**

#### Step 1: Log in to GoDaddy
1. Go to [https://godaddy.com](https://godaddy.com)
2. Sign in to your account
3. Go to **My Products**
4. Find **footholics.in** and click **DNS**

#### Step 2: Configure DNS Records

**You need to add the following DNS records:**

##### Option A: Using A Records (Recommended for Root Domain)

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | 76.76.21.21 | 600 |
| CNAME | www | cname.vercel-dns.com | 600 |

##### Option B: Using CNAME (Alternative Method)

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | @ | cname.vercel-dns.com | 600 |
| CNAME | www | cname.vercel-dns.com | 600 |

**⚠️ Note:** Some domain providers don't support CNAME for root domain (@). If you get an error, use Option A with A records.

#### Step 3: Remove Conflicting Records
1. **IMPORTANT:** Delete any existing A or CNAME records for @ and www
2. GoDaddy often adds default "Domain Parking" records - remove these
3. Keep only the records you added above

---

### **PART 3: Verification**

#### Step 1: Wait for DNS Propagation
- DNS changes can take **10 minutes to 48 hours** to propagate
- Usually takes **15-30 minutes** with GoDaddy

#### Step 2: Check Status in Vercel
1. Go back to Vercel → Your Project → Settings → Domains
2. You should see:
   - `footholics.in` - ✅ Valid Configuration
   - `www.footholics.in` - ✅ Valid Configuration

#### Step 3: Test Your Domain
1. Open a browser in incognito/private mode
2. Visit: `https://footholics.in`
3. Visit: `https://www.footholics.in`
4. Both should load your website with HTTPS

---

## 🔍 Detailed DNS Configuration Steps for GoDaddy

### Visual Guide:

1. **Navigate to DNS Management**
   ```
   GoDaddy → My Products → Domains → footholics.in → DNS
   ```

2. **Add A Record** (for footholics.in)
   - Click "Add" button
   - Type: Select "A"
   - Name: Enter "@" (this represents your root domain)
   - Value: Enter "76.76.21.21" (Vercel's IP)
   - TTL: 600 seconds (or leave as default)
   - Click "Save"

3. **Add CNAME Record** (for www.footholics.in)
   - Click "Add" button again
   - Type: Select "CNAME"
   - Name: Enter "www"
   - Value: Enter "cname.vercel-dns.com"
   - TTL: 600 seconds
   - Click "Save"

4. **Delete Parking Records**
   - Look for records with values like "parked" or GoDaddy's parking servers
   - Click the trash icon to delete them
   - Confirm deletion

---

## ⚡ Alternative: Nameserver Method (Advanced)

If you want Vercel to fully manage your DNS:

### Step 1: Get Vercel Nameservers
1. In Vercel, go to Domains
2. Click on your domain
3. Click "Use Vercel Nameservers"
4. Copy the nameserver addresses (usually 2-4 addresses like `ns1.vercel-dns.com`)

### Step 2: Change Nameservers in GoDaddy
1. Go to GoDaddy → My Products → Domains
2. Click on **footholics.in**
3. Click **Manage DNS**
4. Scroll down to **Nameservers**
5. Click **Change**
6. Select **Custom**
7. Enter Vercel's nameservers
8. Click **Save**

**⚠️ Warning:** This method gives Vercel full DNS control. Use only if you're comfortable with this.

---

## 🐛 Troubleshooting

### Problem: "Invalid Configuration" in Vercel

**Solution:**
1. Double-check DNS records in GoDaddy
2. Make sure you deleted all conflicting records
3. Wait 30 minutes and check again
4. Run DNS check: `nslookup footholics.in` in terminal

### Problem: "SSL Certificate Not Issued"

**Solution:**
1. Wait 24 hours - Vercel automatically issues SSL
2. In Vercel, go to Domains and click "Refresh" next to your domain
3. If still not working after 24h, try removing and re-adding the domain

### Problem: www not working

**Solution:**
1. Make sure you added CNAME record for "www"
2. Check that CNAME value is exactly: `cname.vercel-dns.com`
3. In Vercel, make sure both domains are added

### Problem: Website shows "404 Not Found"

**Solution:**
1. Your domain is connected, but Vercel project is not deployed
2. In Vercel, go to Deployments tab
3. Make sure latest deployment is successful
4. Redeploy if needed

---

## ✅ Verification Checklist

After setup, verify these:

- [ ] `footholics.in` loads your website
- [ ] `www.footholics.in` loads your website
- [ ] Both URLs show HTTPS (secure padlock icon)
- [ ] SSL certificate is valid (click padlock → should show "Connection is secure")
- [ ] Old URLs redirect properly (if applicable)
- [ ] All pages load correctly
- [ ] Ads are working
- [ ] Social media share buttons use correct domain

---

## 📊 DNS Propagation Checker

Check if your DNS changes have propagated globally:
- [https://dnschecker.org](https://dnschecker.org)
- Enter: `footholics.in`
- Check: A record should show `76.76.21.21`
- Check: www CNAME should show `cname.vercel-dns.com`

---

## 🔄 Updating Your Website URLs

After domain is live, update these files:

1. **Canonical URLs in all HTML files:**
   ```html
   <link rel="canonical" href="https://footholics.in/[page].html">
   ```

2. **Open Graph URLs:**
   ```html
   <meta property="og:url" content="https://footholics.in/[page].html">
   ```

3. **Google Analytics / Search Console:**
   - Add new domain property
   - Submit sitemap with new domain

---

## 📞 Need Help?

### Vercel Support
- Docs: https://vercel.com/docs/custom-domains
- Support: https://vercel.com/support

### GoDaddy Support
- Help: https://www.godaddy.com/help
- Phone: Check GoDaddy dashboard for your region's number

---

## 🎉 Success!

Once everything is working:
1. Update all internal links to use `footholics.in`
2. Set up 301 redirects from old domain (if applicable)
3. Update social media profiles
4. Update Google Search Console
5. Celebrate! 🎊

---

**Last Updated:** December 2025
**Domain:** footholics.in
**Platform:** Vercel
**Registrar:** GoDaddy
