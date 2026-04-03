/**
 * Cloudflare Worker: 遊々亭 PTCG 价格爬虫
 * GET /?name=リザードン&limit=20
 */

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,OPTIONS',
  'Content-Type': 'application/json; charset=utf-8',
};

export default {
  async fetch(request) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS });
    }

    const url = new URL(request.url);
    const name = url.searchParams.get('name') || '';
    const limit = parseInt(url.searchParams.get('limit') || '20');

    if (!name) {
      return new Response(JSON.stringify({ error: 'name required' }), { status: 400, headers: CORS });
    }

    try {
      const encoded = encodeURIComponent(name);
      const targetUrl = `https://yuyu-tei.jp/sell/poc/s/search?search_word=${encoded}`;

      const res = await fetch(targetUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0',
          'Accept': 'text/html',
          'Accept-Language': 'ja,en;q=0.9',
        },
      });

      const html = await res.text();
      const results = parseYYT(html, limit);

      return new Response(
        JSON.stringify({ results, total: results.length, source: 'yuyu-tei.jp' }, null, 0),
        { headers: CORS }
      );
    } catch (e) {
      return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: CORS });
    }
  }
};

function parseYYT(html, limit) {
  const results = [];

  // 按卡片块切割 — 用正则匹配（class 内容可能有空格/换行）
  const blocks = html.split(/class="text-primary fw-bold">/);

  for (let i = 1; i < blocks.length; i++) {
    const block = blocks[i];
    try {
      // 卡名
      const nameMatch = block.match(/^([^<]+)/);
      if (!nameMatch) continue;
      const cardName = nameMatch[1].trim();

      // 编号（向前找 span 里的 xxx/xxx 格式）
      const prevBlock = blocks[i - 1].slice(-300);
      const numberMatch = prevBlock.match(/(\d+\/\d+)(?!.*\d+\/\d+)/);
      const cardNumber = numberMatch ? numberMatch[1] : '';

      // 价格
      const priceMatch = block.match(/<strong[^>]*>\s*([\d,]+)\s*円/);
      if (!priceMatch) continue;
      const priceJpy = parseInt(priceMatch[1].replace(/,/g, ''));

      // 在庫
      const stockMatch = block.match(/在庫\s*:\s*([^\n<]{1,20})/);
      let stock = '有货';
      if (stockMatch) {
        const s = stockMatch[1].trim();
        if (s.includes('×')) stock = '售罄';
        else if (s.includes('◯')) stock = '有货';
        else {
          const m = s.match(/(\d+)/);
          if (m) stock = `${m[1]}件`;
        }
      }

      // 链接（在前一块的末尾）
      const prevTail = blocks[i - 1].slice(-500);
      const linkMatch = prevTail.match(/href="(https:\/\/yuyu-tei\.jp\/sell\/poc\/card\/[^"]+)"/);
      const link = linkMatch ? linkMatch[1] : '';

      results.push({ name: cardName, number: cardNumber, price_jpy: priceJpy, stock, url: link, source: 'yuyu-tei' });

      if (results.length >= limit) break;
    } catch (e) {
      continue;
    }
  }

  return results;
}
