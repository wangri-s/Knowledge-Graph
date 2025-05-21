import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 全局线程锁，用于线程安全的写入操作
lock = threading.Lock()

def get_description_from_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")

            # 更稳健的描述提取方式
            desc_container = soup.find("div", class_="artwork__intro__desc")
            if desc_container:
                paragraphs = desc_container.find_all("p")
                full_desc = " ".join(p.get_text(strip=True) for p in paragraphs)
                return full_desc if full_desc else "无描述信息"
            else:
                return "无描述信息"
        else:
            print(f"请求失败: {url}，状态码: {response.status_code}")
            return "请求失败"
    except Exception as e:
        print(f"抓取异常: {url}，错误: {str(e)}")
        return "抓取异常"


def crawl_descriptions(input_file, output_file, max_threads=5):
    df = pd.read_csv(input_file)

    results = []
    
    def process_row(idx, row):
        custom_id = row['Object ID']
        url = row['Object URL']
        print(f"正在处理自定义 ID {custom_id}，URL: {url}")

        desc = get_description_from_url(url)
        
        # 记录当前行的所有信息和描述
        result_row = row.to_dict()
        result_row['Description'] = desc
        return result_row
    
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = {executor.submit(process_row, idx, row): idx for idx, row in df.iterrows()}
        
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result_row = future.result()
                results.append(result_row)

                # 每 20 条保存一次
                if (idx + 1) % 20 == 0:
                    print(f"保存第 {idx + 1} 条记录……")
                    with lock:  # 使用锁保证写入时的线程安全
                        pd.DataFrame(results).to_csv(output_file, index=False, encoding='utf-8-sig', mode='a', header=not os.path.exists(output_file))
                    results.clear()  # 清空暂存列表
            except Exception as e:
                print(f"处理失败: {e}")

    # 保存剩余的数据（不足20条的部分）
    if results:
        with lock:
            pd.DataFrame(results).to_csv(output_file, index=False, encoding='utf-8-sig', mode='a', header=not os.path.exists(output_file))
        print(f"已保存剩余 {len(results)} 条记录。")

    print(f"抓取完成！输出文件已保存为：{output_file}")


# 示例调用
crawl_descriptions("1.csv", "object_links_with_descriptions.csv", max_threads=10)
