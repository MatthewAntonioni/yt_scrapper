import yt_dlp;

class main:

    options={

        'quiet':True,
        'skip_download': True,
        'extract_flat': False

    }

    with yt_dlp.YoutubeDL(options) as ydl:

        results = ydl.extract_info(

            "ytsearch5:markiplier",
            download=False

        )

    for video in results['entries']:
        if video is None:
            continue

        print("Title", video.get('title'))
        print("Views", video.get('view_count'))
        print("channel", video.get('uploader'))
        print("Date", video.get('upload_date'))
        print("Description", video.get('description'))
        print("------------------------------------")