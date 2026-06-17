// Cloudflare Pages Function - View Counter API
// KV binding: VIEW_COUNTER
// GET  /api/views?id=xxx        → { id, views }
// GET  /api/views?ids=a,b,c     → { data: [{id, views}, ...] }
// POST /api/views?id=xxx        → { id, views } (increment by 1)

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

export async function onRequestOptions() {
  return new Response(null, { headers: CORS_HEADERS });
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const id = url.searchParams.get('id');
  const ids = url.searchParams.get('ids');

  try {
    // Batch: ?ids=a,b,c
    if (ids) {
      const idList = ids.split(',').filter(Boolean);
      const results = await Promise.all(
        idList.map(async (wid) => {
          const raw = await env.VIEW_COUNTER.get(wid);
          return { id: wid, views: raw ? parseInt(raw) : 0 };
        })
      );
      return new Response(JSON.stringify({ data: results }), {
        headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
      });
    }

    // Single: ?id=xxx
    if (id) {
      const raw = await env.VIEW_COUNTER.get(id);
      const views = raw ? parseInt(raw) : 0;
      return new Response(JSON.stringify({ id, views }), {
        headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
      });
    }

    return new Response(JSON.stringify({ error: 'Missing id parameter' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
    });
  }
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const id = url.searchParams.get('id');

  if (!id) {
    return new Response(JSON.stringify({ error: 'Missing id parameter' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
    });
  }

  try {
    // Read current value
    const raw = await env.VIEW_COUNTER.get(id);
    const current = raw ? parseInt(raw) : 0;
    const newCount = current + 1;

    // Write back
    await env.VIEW_COUNTER.put(id, String(newCount));

    return new Response(JSON.stringify({ id, views: newCount }), {
      headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
    });
  }
}
