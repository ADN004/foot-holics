import { readFile } from 'fs/promises';
import { join } from 'path';

export default async function handler(req, res) {
  // CORS — allow live.footholics.in to fetch from this API
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');
  res.setHeader('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=120');

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const eventsPath = join(process.cwd(), 'data', 'events.json');
    const raw = await readFile(eventsPath, 'utf8');
    const events = JSON.parse(raw);

    // Newest first
    events.sort((a, b) => {
      const da = new Date(`${a.date}T${a.time || '00:00'}:00`);
      const db = new Date(`${b.date}T${b.time || '00:00'}:00`);
      return db - da;
    });

    return res.status(200).json(events);
  } catch (err) {
    if (err.code === 'ENOENT') {
      return res.status(200).json([]);
    }
    console.error('events API error:', err);
    return res.status(500).json({ error: 'Failed to load events' });
  }
}
