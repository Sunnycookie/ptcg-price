"""
Vercel Function: 遊々亭 PTCG 价格爬虫
GET /api/yuyutei?name=リザードン&limit=20
"""
from http.server import BaseHTTPRequestHandler
import urllib.request, urllib.parse, re, json

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0',
    'Accept': 'text/html',
    'Accept-Language': 'ja,en;q=0.9',
}

def fetch_yuyutei(keyword: str, limit: int = 20) -> list:
    encoded = urllib.parse.quote(keyword)
    url = f'https://yuyu-tei.jp/sell/poc/s/search?search_word={encoded}'
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8')

    results = []

    # 解析每张卡片块：找卡名、编号、价格、链接
    # 结构: <h4 class="text-primary fw-bold">卡名</h4> ... 价格 円
    blocks = re.split(r'<h4\s+class="text-primary fw-bold">', html)

    for block in blocks[1:]:  # 跳过第一个（头部）
        try:
            # 卡名
            name_match = re.search(r'^([^<]+)', block)
            if not name_match:
                continue
            card_name = name_match.group(1).strip()

            # 编号（在卡名前的 span 里，往前找）
            number_match = re.search(r'<span[^>]*>(\d+/\d+)</span>', block[:200])
            card_number = number_match.group(1) if number_match else ''

            # 价格（紧跟在卡名后的 strong 标签）
            price_match = re.search(r'<strong[^>]*>\s*([\d,]+)\s*円', block[:500])
            if not price_match:
                continue
            price_yen = int(price_match.group(1).replace(',', ''))

            # 链接
            link_match = re.search(r'href="(https://yuyu-tei\.jp/sell/poc/card/[^"]+)"', block[:300])
            link = link_match.group(1) if link_match else ''

            # 在庫状況
            stock_match = re.search(r'在庫\s*:\s*([^\n<]+)', block[:600])
            stock_raw = stock_match.group(1).strip() if stock_match else ''
            if '×' in stock_raw:
                stock = '售罄'
            elif '◯' in stock_raw:
                stock = '有货'
            else:
                m = re.search(r'(\d+)\s*点', stock_raw)
                stock = f'{m.group(1)}件' if m else '有货'

            results.append({
                'name': card_name,
                'number': card_number,
                'price_jpy': price_yen,
                'stock': stock,
                'url': link,
                'source': 'yuyu-tei',
            })

            if len(results) >= limit:
                break

        except Exception:
            continue

    return results


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            name = params.get('name', [''])[0]
            limit = int(params.get('limit', ['20'])[0])

            if not name:
                self._respond(400, {'error': 'name parameter required'})
                return

            data = fetch_yuyutei(name, limit)
            self._respond(200, {'results': data, 'total': len(data), 'source': 'yuyu-tei.jp'})

        except Exception as e:
            self._respond(500, {'error': str(e)})

    def _respond(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass
