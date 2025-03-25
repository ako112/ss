import requests
import subprocess
import time
import os
from concurrent.futures import ThreadPoolExecutor

class TestResult:
    def __init__(self, delay, channel, url, quality_score):
        self.delay = delay
        self.channel = channel
        self.url = url
        self.quality_score = quality_score

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

def get_quality_score(url):
    url = url.lower()
    scores = {"4k": 40, "2160p": 40, "1080p": 30, "720p": 20, "hd": 10}
    return max([v for k, v in scores.items() if k in url], default=10)

def test_url(channel_url):
    channel, url = channel_url
    if "127.0.0.1" in url:
        return TestResult(0, channel, url, get_quality_score(url))
    start = time.time()
    try:
        subprocess.run(
            ["ffmpeg", "-i", url, "-t", "3", "-f", "null", "-", "-loglevel", "quiet"],
            timeout=10, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        delay = int((time.time() - start) * 1000)
        print(f"测试 {url} 成功，延迟: {delay}ms")
        return TestResult(delay, channel, url, get_quality_score(url))
    except Exception as e:
        print(f"测试 {url} 失败: {e}")
        return TestResult(float("inf"), channel, url, get_quality_score(url))

def main():
    sources = [
        "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.txt",
        "https://raw.githubusercontent.com/alantang1977/JunTV/refs/heads/main/output/result.txt"
    ]
    sort_url = "https://raw.githubusercontent.com/ako112/cct/main/demo.txt"

    # 获取数据
    all_lines = []
    for url in sources:
        all_lines.extend(fetch_source(url))
    sort_list = fetch_source(sort_url)
    if not all_lines or not sort_list:
        print("数据获取失败，退出")
        return

    # 组织频道
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

    # 测试并排序
    output = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for ch, urls in channels.items():
            print(f"测试频道 {ch}，共 {len(urls)} 个 URL")
            results = list(executor.map(test_url, [(ch, url) for url in urls]))
            valid = sorted([r for r in results if r.delay != float("inf")],
                          key=lambda x: (-x.quality_score, x.delay))[:8]
            print(f"频道 {ch} 有效 URL 数: {len(valid)}")
            output.extend([(r.channel, r.url) for r in valid])

    # 按排序列表顺序输出
    sort_dict = {ch: i for i, ch in enumerate(sort_list)}
    output.sort(key=lambda x: sort_dict.get(x[0], float("inf")))

    # 写入文件
    os.makedirs("gd/output", exist_ok=True)
    with open("gd/output/result.txt", "w", encoding="utf-8") as f:
        for ch, url in output:
            f.write(f"{ch},{url}\n")
    print(f"完成: {len(output)} 个直播源")

if __name__ == "__main__":
    main()
