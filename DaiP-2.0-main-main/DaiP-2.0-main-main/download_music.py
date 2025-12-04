import requests

# 下载示例音乐文件
def download_music():
    url = 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3'
    save_path = 'static/music/SoundHelix-Song-1.mp3'
    
    print(f'正在从 {url} 下载音乐文件...')
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()  # 检查请求是否成功
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        
        print(f'音乐文件下载完成，保存到 {save_path}')
    except requests.exceptions.RequestException as e:
        print(f'下载失败: {e}')

if __name__ == '__main__':
    download_music()