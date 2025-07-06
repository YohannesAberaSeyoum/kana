from flask import Flask, request, Response, send_file
from urllib.parse import quote_plus, unquote
import os
import socket
import requests
import subprocess
import threading
import time
from tqdm import tqdm
from pynput import keyboard
import sys
from bs4 import BeautifulSoup
import json
import subprocess
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

app = Flask(__name__)

VIDEO_DIRECTORY = "/home/etech/Mine/john/kana/videos"

os.makedirs(VIDEO_DIRECTORY, exist_ok=True)

# Track downloads
active_downloads = {}

HEADERS = {
    "accept": "*/*",
    "accept-language": "am,en-US;q=0.9,en;q=0.8",
    "dnt": "1",
    "if-range": "Tue, 04 Feb 2025 17:14:12 GMT",
    "priority": "i",
    "referer": "https://us.smarthabesha.com/",
    "sec-ch-ua": '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "video",
    "sec-fetch-mode": "no-cors",
    "sec-fetch-site": "cross-site",
    "sec-fetch-storage-access": "active",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
}


def get_remote_file_size(url):
    headers = {
        "Range": "bytes=0-0",
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers, stream=True)
    if 'Content-Range' in response.headers:
        return int(response.headers['Content-Range'].split('/')[-1])
    elif 'Content-Length' in response.headers:
        return int(response.headers['Content-Length'])
    return -1

def is_file_downloaded(file_path, expected_size):
    """Check if file exists and is the correct size."""
    if not os.path.exists(file_path):
        return False
    return os.path.getsize(file_path) == expected_size

def download_file(url, dest):
    """Download file with resume support and progress bar."""
    headers = HEADERS.copy()

    # Check for existing file to resume
    downloaded = 0
    if os.path.exists(dest):
        downloaded = os.path.getsize(dest)
        headers['Range'] = f'bytes={downloaded}-'

    # Make request with Range header
    with requests.get(url, headers=headers, stream=True) as r:
        if r.status_code not in (200, 206):
            r.raise_for_status()

        # Determine total file size for progress bar
        total = int(r.headers.get('Content-Range', 'bytes 0-0/0').split('/')[-1]) \
            if 'Content-Range' in r.headers else int(r.headers.get('Content-Length', 0))

        # Write to file (append if resuming)
        mode = 'ab' if downloaded else 'wb'
        with open(dest, mode) as f, tqdm(
            desc=dest,
            total=total,
            initial=downloaded,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))

def checkIfDownloaded(video_url):
    """Check if the file is already downloaded, and prompt for confirmation if not."""
    videos_dir = './videos'
    os.makedirs(videos_dir, exist_ok=True)
    file_path = os.path.basename(video_url)
    dest = os.path.join(videos_dir, file_path)
    remote_size = get_remote_file_size(video_url)
    if not is_file_downloaded(dest, expected_size=remote_size):
        print(f"File '{dest}' not found or incomplete.")
        # confirm = input(f"Do you want to download '{file_path}'? (y/n): ")
        # if confirm.lower() == 'y':
        download_file(video_url, dest)
        print(f"Downloaded: {dest}")
        # else:
        #     print("Skipped download.")
        #     return False
    else:
        print(f"Already downloaded: {dest}")
    return True

def handleVideoDownload(m3u8_path="playlist.m3u8"):
    """Handle the download of videos listed in the m3u8 playlist."""
    if not os.path.exists(m3u8_path):
        print(f"{m3u8_path} not found.")
        return

    with open(m3u8_path, "r") as f:
        lines = f.readlines()

    # Group videos by their group-title
    video_groups = {}
    current_group = None

    for line in lines:
        line = line.strip()

        # Check for group-title in EXTINF metadata
        if line.startswith("#EXTINF"):
            group_title = None
            # Extract group-title
            if 'group-title' in line:
                group_title = line.split('group-title="')[1].split('"')[0]
            if group_title:
                current_group = group_title
            else:
                current_group = "Unknown"
        # Find actual video URL and group by group-title
        elif line.startswith("http://"):
            real_video_url = line.split('/habesha/', 1)[1]
            if current_group not in video_groups:
                video_groups[current_group] = []
            video_groups[current_group].append(real_video_url)
    # Prompt the user to download videos grouped by group-title
    for group_title, video_urls in video_groups.items():
        print(f"\nGroup: {group_title}")
        # Ask the user if they want to download all videos in the group
        group_confirm = input(f"Do you want to download all videos in group '{group_title}'? (y/n): ")
        if group_confirm.lower() == 'y':
            for video_url in reversed(video_urls):
                if not is_youtube_url(video_url) and not checkIfDownloaded(video_url):
                    break  # Stop the group if the user skips any download
        else:
            print(f"Skipped group '{group_title}'.")

def parse_m3u(m3u_text):
    local_ip = "192.168.1.24"
    """Parse M3U content into a list of (title, url) tuples."""
    lines = m3u_text.strip().splitlines()
    entries = []
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF:"):
            title = lines[i].split(",")[-1]
            url = lines[i + 1].strip().replace(f"http://{local_ip}:5000/habesha/", "") if (i + 1) < len(lines) else ""
            entries.append((title.strip(), url))
    return entries

def search_entries(entries, keyword):
    """Filter entries by keyword (case-insensitive)."""
    return [(i, title, url) for i, (title, url) in enumerate(entries) if keyword.lower() in title.lower()]

def interactive_download(m3u_text):
    entries = parse_m3u(m3u_text)
    titles = [title for title, _ in entries]
    title_completer = WordCompleter(titles, ignore_case=True, match_middle=True)

    while True:
        search = prompt("Search video (or 'exit'): ", completer=title_completer).strip()
        if search.lower() == "exit":
            break

        matches = [(t, u) for (t, u) in entries if search.lower() in t.lower()]
        if not matches:
            print("No results found.")
            continue

        print("\nMatching results:")
        for i, (t, _) in enumerate(matches):
            print(f"[{i}] {t}")

        try:
            index = int(input("Enter number to download: ").strip())
            title, url = matches[index]
            checkIfDownloaded(url)
        except Exception as e:
            print(f"Invalid selection: {e}")


def handleInteractiveVideoDownload(m3u8_path="playlist.m3u8"):
    with open(m3u8_path, "r", encoding="utf-8") as f:
        m3u_data = f.read()
        interactive_download(m3u_data)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP

def is_youtube_url(url):
    return "youtube.com" in url or "youtu.be" in url

def start_background_curl(url, output_path):
    def run():
        cmd = [
            "curl", "-o", output_path, url,
            "-H", "accept: */*",
            "-H", "accept-language: am,en-US;q=0.9,en;q=0.8",
            "-H", "dnt: 1",
            "-H", "priority: i",
            "-H", "range: bytes=0-",
            "-H", "referer: https://us.smarthabesha.com/",
            "-H", 'sec-ch-ua: "Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            "-H", "sec-ch-ua-mobile: ?0",
            "-H", 'sec-ch-ua-platform: "Linux"',
            "-H", "sec-fetch-dest: video",
            "-H", "sec-fetch-mode: no-cors",
            "-H", "sec-fetch-site: cross-site",
            "-H", "sec-fetch-storage-access: active",
            "-H", "user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        ]
        subprocess.run(cmd)
        active_downloads.pop(output_path, None)

    if output_path not in active_downloads:
        thread = threading.Thread(target=run, daemon=True)
        active_downloads[output_path] = thread
        thread.start()

class Video:
    def __init__(self, id, title, url, logo_url, group):
        self.title = title
        self.logo_url = logo_url
        self.id = id
        self.group = group
        self.url = url

    def getPlaylistVideo(self):
        singleVideo = f"""
#EXTINF:-1 tvg-id="{self.id}" tvg-logo="{self.logo_url}" group-title="{self.group}",{self.title}
{self.url}
        """
        return singleVideo

class Playlist:
    def __init__(self, title: str, playlist_type: str, url: str):
        if playlist_type not in ("youtube", "habesha"):
            raise ValueError("playlist_type must be either 'youtube' or 'habesha'")

        self.title = title
        self.playlist_type = playlist_type
        self.url = url

    def __str__(self):
        return f"Playlist(title='{self.title}', type='{self.playlist_type}', url='{self.url}')"

    def getVideos(self):
        if self.playlist_type == "youtube":
            self.videos = self._fetch_youtube_videos()
        elif self.playlist_type == "habesha":
            self.videos = self._fetch_habesha_videos()
        return self.videos

    def _fetch_youtube_videos(self):
        # Extract playlist ID from the URL
        playlist_id = self.url.split("list=")[-1]
        api_url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={playlist_id}&maxResults=50&key={self.YOUTUBE_API_KEY}"

        response = requests.get(api_url)
        data = response.json()

        videos = []
        for item in data.get('items', []):
            title = item['snippet']['title']
            video_id = item['snippet']['resourceId']['videoId']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            videos.append(Video(video_id, title, video_url, video_url, playlist_id))

        return videos

    def _fetch_habesha_videos(self):
        encoded_title = quote_plus(self.title)
        # Set the URL based on the encoded title
        api_url = f"https://us.smarthabesha.com/EthioPlaylist?title={encoded_title}"

        headers = {
            'accept': '*/*',
            'accept-language': 'am,en-US;q=0.9,en;q=0.8',
            'dnt': '1',
            'priority': 'u=1, i',
            'referer': f'https://us.smarthabesha.com/EthioPlaylist?title={encoded_title}',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            'x-nextjs-data': '1'
        }

        html = requests.get(api_url, headers=headers).text
        soup = BeautifulSoup(html, 'html.parser')

        script = soup.find('script', id='__NEXT_DATA__')
        data = json.loads(script.string)

        videos = data['props']

        if videos:
            videos = self._parse_habesha_response(videos)
            return videos
        else:
            print("Failed to fetch data. Status code")
            return []

    def _parse_habesha_response(self, data):
        local_ip = get_local_ip()
        videos = []
        for item in data.get('pageProps', {}).get('VideoList', []):
            url = item.get('video_url', '')
            main_title = item.get('main_title', 'Habesh')
            video_url = url if is_youtube_url(url) else f"http://{local_ip}:5000/habesha/{item.get('video_url', '')}"
            video_title = item.get('video_title', '')
            youtube_picture = item.get('youtube_picture', '')
            id = item.get('id', '')
            videos.append(Video(id, video_title, video_url, youtube_picture, main_title))
        return videos

    def getPlaylistFile(self):
        playlistFile = ""
        videos = self.getVideos()
        for video in videos:
            playlistFile += video.getPlaylistVideo()
        return playlistFile

playlists = [Playlist("Yewef Gojo", "habesha", ""), Playlist("Anqets S2", "habesha", ""), Playlist("Sinbit", "habesha", '')]

def parse_habesha_response(data):
    local_ip = get_local_ip()
    videos = []
    for item in data.get('pageProps', {}).get('VideoList', []):
        url = item.get('video_url', '')
        main_title = item.get('main_title', 'Habesh')
        video_url = url if is_youtube_url(url) else f"http://{local_ip}:5000/habesha/{item.get('video_url', '')}"
        video_title = item.get('video_title', '')
        youtube_picture = item.get('youtube_picture', '')
        id = item.get('id', '')
        videos.append(Video(id, video_title, video_url, youtube_picture, main_title))
    return videos

def getPlaylistFile(videos):
        playlistFile = ""
        for video in videos:
            playlistFile += video.getPlaylistVideo()
        return playlistFile

def getIndex():
    url = 'https://www.us.smarthabesha.com/_next/data/N3Ux9GJq1TQhUgFUB-abE/index.json'

    headers = {
        'accept': '*/*',
        'accept-language': 'am,en-US;q=0.9,en;q=0.8',
        'dnt': '1',
        'priority': 'u=1, i',
        'referer': 'https://www.us.smarthabesha.com/SmartPlayer?title=collection&episode=430',
        'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'x-nextjs-data': '1'
    }

    cookies = {
        '_ga': 'GA1.1.843926920.1746098538',
        '_ga_TNT09EHQLE': 'GS2.1.s1749751561$o12$g1$t1749751836$j51$l0$h0',
        '_ga_R571GCFF2B': 'GS2.1.s1749751561$o14$g1$t1749751836$j51$l0$h0',
        'FCNEC': '[["AKsRol9uzNaWwaJejzJLwBwaL_FM0fdcQQhQH5Y8JrwOkErWot2VgrO6qTd_JExFB127VYB0LpFdbC2msauzWbhHkF23VMe77W3W8BG6KanAK9jF95PsFls62oHcAvR7UyRHxYxrpYqjvPNEazVO50ZqTwlaPVKmxQ=="]]',
        '__gads': 'ID=ac63bb1fd4f77af7:T=1746098537:RT=1749752298:S=ALNI_MZV4zQZdbIxyYNqYbGRo7Nv-2VDUQ',
        '__gpi': 'UID=0000109d603c32df:T=1746098537:RT=1749752298:S=ALNI_Ma3VCb0Dg2_GtIb25_-87VD3c2hbA',
        '__eoi': 'ID=c6d29f2274961091:T=1746098537:RT=1749752298:S=AA-AfjZo8hLG3OUkZ6IFjC2ZNKrH'
    }

    response = requests.get(url, headers=headers, cookies=cookies)

    print(response.status_code)
    videos = parse_habesha_response(response.json())
    return getPlaylistFile(videos)

def generate_m3u8_content():
    playlistsFile = getIndex()
    # for playlist in playlists:
    #     playlistsFile += playlist.getPlaylistFile()

    m3u8_content = f"""#EXTM3U
{playlistsFile}
    """
    return m3u8_content

def stream_video(video_url):
    # Decode the URL
    video_url = unquote(video_url)

    # Extract filename from the URL
    filename = os.path.basename(video_url)

    # Create the full local path to the video file
    local_path = os.path.join(VIDEO_DIRECTORY, filename)
    print(f"Local path: {local_path}")

    # Check if the video file exists
    if not os.path.exists(local_path):
        return "Video not found", 404

    # Generate video stream in chunks
    def generate():
        with open(local_path, 'rb') as f:
            while True:
                chunk = f.read(8192)  # Read in 8 KB chunks
                if chunk:
                    yield chunk  # Yield the chunk to the client
                else:
                    break  # End of the file

    # Return the response as a video stream
    return Response(generate(), mimetype="video/mp4")

def generateM3U8(filename="playlist.m3u8"):
    content = generate_m3u8_content()
    with open(filename, "w") as f:
        f.write(content)

@app.route("/playlist.m3u8")
def serve_m3u8():
    return send_file("playlist.m3u8", mimetype='application/vnd.apple.mpegurl')

@app.route("/habesha/<path:video_url>")
def proxy_video(video_url):
    # Decode the URL
    video_url = unquote(video_url)

    # Extract the filename from the URL
    filename = os.path.basename(video_url)

    # Create the full local path to the video file
    local_path = os.path.join(VIDEO_DIRECTORY, filename)
    print(os.path.exists(local_path))

    # Check if the video file exists locally
    if os.path.exists(local_path):
        # Stream from local file
        return stream_local_video(local_path)

    # If the video doesn't exist locally, stream from the remote URL
    return stream_remote_video(video_url)

# def stream_local_video(local_path):
#     """Stream the video from a local file."""
#     def generate():
#         with open(local_path, 'rb') as f:
#             while True:
#                 chunk = f.read(8192)  # Read in 8 KB chunks
#                 if chunk:
#                     yield chunk  # Yield the chunk to the client
#                 else:
#                     break  # End of the file

#     return Response(
#         generate(),
#         mimetype="video/mp4",  # Assuming the video is in MP4 format
#         status=200
#     )

def stream_local_video(local_path):
    """Serve the entire MP4 video file at once."""
    return send_file(
        local_path,
        mimetype='video/mp4',
        conditional=True
    )

def stream_remote_video(video_url):
    """Stream the video from a remote server."""
    # Get the range header from the client request, if present
    range_header = request.headers.get("Range", None)

    headers = HEADERS.copy()
    if range_header:
        headers["Range"] = range_header  # Forward the range header to the remote server

    # Fetch the video from the remote server
    remote_response = requests.get(unquote(video_url), headers=headers, stream=True)

    if remote_response.status_code != 200:
        return f"Error: Unable to retrieve video from remote server. Status code: {remote_response.status_code}", remote_response.status_code

    def generate():
        for chunk in remote_response.iter_content(chunk_size=8192):
            yield chunk  # Yield each chunk to the client

    # Return the video stream as a response
    return Response(
        generate(),
        status=remote_response.status_code,
        headers=dict(remote_response.headers),
        content_type=remote_response.headers.get("Content-Type", "video/mp4")
    )

def on_press(key):
    try:
        if key.char == 'g':  # Trigger generateM3U8
            generateM3U8()
        elif key.char == 'd':  # Trigger handleVideoDownload
            handleVideoDownload()
    except AttributeError:
        # Handle special keys like 'shift', 'alt', etc.
        pass

def listen_for_key():
    # Start listening to key presses in the background
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

if __name__ == "__main__":
#    threading.Thread(target=listen_for_key, daemon=True).start()
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "generate":
            generateM3U8()
        elif command == "download":
            handleInteractiveVideoDownload()
        else:
            print(f"[ERROR] Unknown command: {command}")
    else:
        # No command: start Flask server
        app.run(port=5000, debug=True, host='0.0.0.0')
