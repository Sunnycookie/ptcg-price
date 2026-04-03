"""
遊々亭价格代理服务 v2 - 带内存缓存（5分钟TTL）
端口：8766
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, urllib.parse, re, json, time, threading

CACHE = {}  # {keyword: (timestamp, results)}
CACHE_TTL = 300  # 5分钟缓存
CACHE_LOCK = threading.Lock()

HEADERS_OUT = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json; charset=utf-8',
}

def fetch_yuyutei(keyword: str, limit: int = 20) -> list:
    encoded = urllib.parse.quote(keyword)
    url = f'https://yuyu-tei.jp/sell/poc/s/search?search_word={encoded}'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0',
        'Accept-Language': 'ja,en;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode('utf-8')

    results = []
    blocks = re.split(r'class="text-primary fw-bold">', html)

    for i, block in enumerate(blocks[1:], 1):
        try:
            name_match = re.search(r'^([^<]+)', block)
            if not name_match:
                continue
            card_name = name_match.group(1).strip()
            if not card_name or len(card_name) > 60:
                continue

            price_match = re.search(r'<strong[^>]*>\s*([\d,]+)\s*円', block[:400])
            if not price_match:
                continue
            price_jpy = int(price_match.group(1).replace(',', ''))

            stock_match = re.search(r'在庫\s*:\s*([^\n<]{1,20})', block[:600])
            stock = '有货'
            if stock_match:
                s = stock_match.group(1).strip()
                if '×' in s:
                    stock = '售罄'
                elif '◯' in s:
                    stock = '有货'
                else:
                    m = re.search(r'(\d+)', s)
                    stock = f'{m.group(1)}件' if m else '有货'

            prev_tail = blocks[i - 1][-500:]
            link_match = re.search(r'href="(https://yuyu-tei\.jp/sell/poc/card/[^"]+)"', prev_tail)
            link = link_match.group(1) if link_match else ''

            results.append({
                'name': card_name,
                'price_jpy': price_jpy,
                'stock': stock,
                'url': link,
                'source': 'yuyu-tei',
            })
            if len(results) >= limit:
                break
        except Exception:
            continue

    return results


def get_cached(keyword, limit):
    cache_key = f'{keyword}:{limit}'
    with CACHE_LOCK:
        if cache_key in CACHE:
            ts, results = CACHE[cache_key]
            if time.time() - ts < CACHE_TTL:
                return results, True  # (data, from_cache)
    # 缓存未命中，实时抓取
    results = fetch_yuyutei(keyword, limit)
    with CACHE_LOCK:
        CACHE[cache_key] = (time.time(), results)
    return results, False


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in HEADERS_OUT.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = params.get('name', [''])[0]
        limit = int(params.get('limit', ['20'])[0])
        exact = params.get('exact', [''])[0]  # 精确卡名过滤（日文）

        try:
            if name:
                results, from_cache = get_cached(name, limit)
                # 精确匹配：只返回卡名完全一致的结果
                if exact:
                    results = [r for r in results if r['name'] == exact]
            else:
                results, from_cache = [], True

            body = json.dumps({
                'results': results,
                'total': len(results),
                'cached': from_cache,
            }, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
        except Exception as e:
            body = json.dumps({'error': str(e), 'results': [], 'total': 0}).encode('utf-8')
            self.send_response(200)  # 返回200避免前端报错

        for k, v in HEADERS_OUT.items():
            self.send_header(k, v)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8766), Handler)
    print('遊々亭价格服务 v2（带缓存）运行在 http://0.0.0.0:8766')
    server.serve_forever()
