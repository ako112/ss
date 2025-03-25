import requests
import subprocess
import time
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Dict
from dataclasses import dataclass

@dataclass
class TestResult:
    delay: float
    channel: str
    url: str
    quality_score: int

def fetch_source(url: str) -> List[str]:
    """获取直播源内容"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        lines = [line.strip() for line in response.text.splitlines() if line.strip() and "," in line]
        print(f"从 {url} 获取到 {len(lines)} 行数据")
        return lines
    except requests.RequestException as e:
        print(f"警告: 获取 {url} 失败: {e}")
        return []

def fetch_sort_list(url: str) -> List[str]:
    """获取排序列表"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # GitHub Blob 页面是 HTML，需提取 raw 内容，这里假设直接用 raw URL
        channels = [line.strip() for line in response.text.splitlines() if line.strip() and not line.startswith("#")]
        print(f"排序列表包含 {len(channels)} 个频道")
        return channels
    except requests.RequestException as e:
        print(f"警告: 获取排序列表 {url} 失败: {e}")
        return []

def get_quality_score(url: str) -> int:
    """计算清晰度和码率分数"""
    url_lower = url.lower()
    quality_keywords = {
        "4k": 40, "2160p": 40, "1080p": 30, "1080i": 28,
        "720p": 20, "720i": 18, "high": 15, "hd": 10, "sd": 5, "low": 2
    }
    bitrate_keywords = {
        "8000k": 20, "5000k": 15, "3000k": 10, "2000k": 8, "1000k": 5, "500k": 2
    }
    quality = max((value for key, value in quality_keywords.items() if key in url_lower), default=0)
    bitrate = max((value for key, value in bitrate_keywords.items() if key in url_lower), default=0)
    return quality + bitrate or 10

def test_url_with_ffmpeg(channel_url: Tuple[str, str]) -> TestResult:
    """使用 FFmpeg 测试 URL 延迟"""
    channel, url = channel_url
    if "127.0.0.1" in url:
        return TestResult(0, channel, url, get_quality_score(url))
    
    start_time = time.time()
    try:
        cmd = [
            "ffmpeg",
            "-i", url,
            "-t", "3",           # 测试 3 秒
            "-f", "null",        # 输出到空设备
            "-",                 # 标准输出
            "-loglevel", "quiet" # 静默模式
        ]
        subprocess.run(cmd, timeout=10, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        delay = int((time.time() - start_time) * 1000)
        return TestResult(delay, channel, url, get_quality_score(url))
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        print(f"测试 {url} 失败: {e}")
        return TestResult(float("inf"), channel, url, get_quality_score(url))

def process_channels(channel_urls: Dict[str, List[str]], sort_order: List[str]) -> List[Tuple[str, str]]:
    """合并、过滤、测速并排序"""
    output = []
    debug_log = []
    
    # 将排序列表转为集合和顺序字典
    sort_set = set(sort_order)
    sort_dict = {channel: idx for idx, channel in enumerate(sort_order)}
    
    # 过滤不在排序列表中的频道
    filtered_channels = {ch: urls for ch, urls in channel_urls.items() if ch in sort_set}
    print(f"过滤后保留 {len(filtered_channels)} 个频道")
    
    for channel, urls in filtered_channels.items():
        debug_log.append(f"\n测试频道: {channel} ({len(urls)} 个 URL)")
        with ThreadPoolExecutor(max_workers=min(8, len(urls))) as executor:
            results = list(executor.map(test_url_with_ffmpeg, [(channel, url) for url in urls]))
        
        valid_results = [r for r in results if r.delay != float("inf")]
        if not valid_results:
            debug_log.append(f"  {channel}: 无可用 URL")
            continue
        
        # 按清晰度优先、延迟次优排序
        sorted_results = sorted(valid_results, key=lambda x: (-x.quality_score, x.delay))
        top_8 = sorted_results[:8]  # 保留最优 8 个
        for result in top_8:
            output.append((channel, result.url))
            debug_log.append(f"  选择: {result.url} #delay={result.delay}ms #quality={result.quality_score}")
    
    # 按排序列表顺序排列
    output.sort(key=lambda x: sort_dict.get(x[0], float("inf")))
    
    with open("debug_log.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(debug_log))
    return output

def main():
    # 直播源 URL
    source_urls = [
        "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.txt",
        "https://raw.githubusercontent.com/alantang1977/JunTV/refs/heads/main/output/result.txt"
    ]
    # 排序列表 URL（需使用 raw URL）
    sort_url = "https://raw.githubusercontent.com/ako112/cct/main/demo.txt"  # 修改为 raw URL
    
    # 获取直播源数据
    all_lines = []
    for url in source_urls:
        lines = fetch_source(url)
        all_lines.extend(lines)
    
    if not all_lines:
        print("错误: 所有直播源都不可用，退出")
        return
    
    # 获取排序列表
    sort_order = fetch_sort_list(sort_url)
    if not sort_order:
        print("错误: 无法获取排序列表，退出")
        return
    
    # 组织频道数据
    channel_urls: Dict[str, List[str]] = {}
    for line in all_lines:
        try:
            channel, url = line.split(",", 1)
            channel_urls.setdefault(channel.strip(), []).append(url.strip())
        except ValueError:
            continue
    
    print(f"合并后加载了 {len(channel_urls)} 个唯一频道")
    
    # 处理频道
    output = process_channels(channel_urls, sort_order)
    
    # 写入结果
    output_file = "gd/output/result.txt"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for channel, url in output:
            f.write(f"{channel},{url}\n")
    
    print(f"处理完成: {len(output)} 个直播源已保存到 {output_file}")

if __name__ == "__main__":
    main()
