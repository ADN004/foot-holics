import { readFile } from 'fs/promises';
import { join } from 'path';

export default async function handler(req, res) {
  // CORS headers for cross-subdomain fetch
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');
  res.setHeader('Cache-Control', 'public, s-maxage=300, stale-while-revalidate=600');

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const indexPath = join(process.cwd(), 'articles', 'index.json');
    const raw = await readFile(indexPath, 'utf8');
    const articles = JSON.parse(raw);

    // Always return newest first (already sorted by convention, but enforce it)
    articles.sort((a, b) => new Date(b.date) - new Date(a.date));

    return res.status(200).json(articles);
  } catch (err) {
    // If file doesn't exist yet, return empty array
    if (err.code === 'ENOENT') {
      return res.status(200).json([]);
    }
    console.error('articles API error:', err);
    return res.status(500).json({ error: 'Failed to load articles' });
  }
}
