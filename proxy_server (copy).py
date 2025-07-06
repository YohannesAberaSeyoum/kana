from flask import Flask, request, Response
from urllib.parse import quote_plus, unquote 
import socket
import requests
# from android.permissions import Permission, request_permissions
# request_permissions([Permission.READ_EXTERNAL_STORAGE,Permission.WRITE_EXTERNAL_STORAGE])

app = Flask(__name__)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't need to be reachable
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP

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
        api_url = f"https://us.smarthabesha.com/_next/data/D1fGS-dsahxrhWL1Lqvaf/SmartPlaylist.json?title={encoded_title}"

        # Custom headers from the original cURL request
        headers = {
            'accept': '*/*',
            'accept-language': 'am,en-US;q=0.9,en;q=0.8',
            'dnt': '1',
            'priority': 'u=1, i',
            'referer': f'https://us.smarthabesha.com/SmartPlaylist?title={encoded_title}',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            'x-nextjs-data': '1'
        }

        # Send the GET request to the API
        response = requests.get(api_url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            # Extract video information from the response
            videos = self._parse_habesha_response(data)
            return videos
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            return []

    def _parse_habesha_response(self, data):
        local_ip = get_local_ip()
        # Parse the response to extract video information
        # This is just a basic example, adapt this based on the actual API response structure.
        videos = []
        for item in data.get('pageProps', {}).get('VideoList', []):
            main_title = item.get('main_title', 'Habesh')
            video_url = f"http://{local_ip}:5000/habesha/{item.get('video_url', '')}"
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

playlists = [Playlist("Yewef Gojo", "habesha", ""), Playlist("Anqets S2", "habesha", "")]

def generate_m3u8_content():
    playlistsFile = ""
    for playlist in playlists:
        playlistsFile += playlist.getPlaylistFile()

    m3u8_content = f"""#EXTM3U
{playlistsFile}
    """
    return m3u8_content

@app.route("/playlist.m3u8")
def serve_m3u8():
    content = generate_m3u8_content()  # Update/generate content just in time
    return Response(content, mimetype='application/vnd.apple.mpegurl')

@app.route("/habesha/<path:video_url>")
def proxy_video(video_url):
    range_header = request.headers.get("Range", None)
    headers = HEADERS.copy()
    if range_header:
        headers["Range"] = range_header

    remote_response = requests.get(unquote(video_url), headers=headers, stream=True)

    def generate():
        for chunk in remote_response.iter_content(chunk_size=8192):
            yield chunk

    return Response(
        generate(),
        status=remote_response.status_code,
        headers=dict(remote_response.headers),
        content_type=remote_response.headers.get("Content-Type", "video/mp4")
    )

if __name__ == "__main__":
    app.run(port=5000, debug=True, host='0.0.0.0')

