import requests

def fetch_source(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        lines = [line.strip() for line in resp.text.splitlines() if "," in line]
        print(f"从 {url} 获取到 {len(lines)} 条数据")
        return lines
    except Exception as e:
        print(f"获取 {url} 失败: {e}")
        return []

def main():
    sources = [
        "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.txt",
        "https://raw.githubusercontent.com/alantang1977/JunTV/refs/heads/main/output/result.txt"
    ]
    sort_url = "https://raw.githubusercontent.com/ako112/cct/main/demo.txt"

    all_lines = []
    for url in sources:
        all_lines.extend(fetch_source(url))
    sort_list = fetch_source(sort_url)

    print("all_lines 前5条:", all_lines[:5])
    print("sort_list 前5条:", sort_list[:5])

    channels = {}
    for line in all_lines:
        try:
            ch, url = line.split(",", 1)
            if ch in sort_list:
                channels.setdefault(ch, []).append(url)
        except Exception as e:
            print(f"解析 {line} 失败: {e}")
            continue
    print(f"匹配到的频道数: {len(channels)}")
    print("匹配的频道示例:", list(channels.keys())[:5])

if __name__ == "__main__":
    main()
